"""detect.py - input -> resample plan -> instruments -> codes -> signature -> verdict (plumbing; methods).
The staged entry points the breakers and the scoreboard call are the same functions `run` is built from."""
import functools
import importlib
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import declare
import door
import readout

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "cc" / "instruments") not in sys.path:
    sys.path.insert(0, str(ROOT / "cc" / "instruments"))


@dataclass
class Reading:
    estimate: float
    lo: float
    hi: float
    cell: str
    eps_key: str = None
    eps: float = None
    reason: str = None
    vector: object = None


@dataclass
class Tables:
    name: str
    codes: dict
    verdict: dict
    lines: list
    paths: tuple


def refused(msg, nxt):
    return ValueError(f"{msg}\n  Next: {nxt}")


@functools.lru_cache(maxsize=None)
def instrument(name):
    d = tomllib.loads((ROOT / "instruments" / f"{name}.toml").read_text())
    return d, importlib.import_module(d["module"])


def load_input(input_id):
    p = ROOT / "inputs" / input_id / "m.toml"
    if not p.is_file():
        names = " ".join(sorted(q.parent.name for q in (ROOT / "inputs").glob("*/m.toml")))
        raise refused(f"no input '{input_id}'. Inputs: {names}", "bin/cc show <one of these>")
    return tomllib.loads(p.read_text())


def load_tables(name, tables_dir=None):
    d = Path(tables_dir or ROOT / "tables") / name
    if not d.is_dir():
        sets = " ".join(sorted(p.name for p in (ROOT / "tables").glob("*")))
        raise refused(f"no table set '{name}'. Sets: {sets}", "bin/cc tables fork verdict-x-rules <name>")
    bad = declare.check_file(d / "codes.toml", ROOT) + declare.check_file(d / "verdict.toml", ROOT)
    if bad:
        raise ValueError("\n".join(declare.fmt(f) for f in bad))
    texts = [(d / f).read_text() for f in ("codes.toml", "verdict.toml")]
    return Tables(name, tomllib.loads(texts[0]), tomllib.loads(texts[1]), declare.row_lines(texts[1]),
                  (d / "codes.toml", d / "verdict.toml"))


def context_for(input_id, instrument_name, point, size=None):
    return door.context(load_input(input_id), instrument(instrument_name)[0], size)


def read_vector(instrument_name, column, v, ctx):
    """The readout of one resampled column: estimate, interval and sign cell against its declared eps."""
    est, lo, hi, cell = readout.reading(np.asarray(v, float), ctx.level, ctx.eps[column])
    eps_key = instrument(instrument_name)[0]["columns"][column]
    return Reading(float(est), float(lo), float(hi), cell, eps_key, ctx.eps[column], None, np.asarray(v))


def after(name, x, ctx):
    """The declared door and stage steps after stage:reduce, then readout: (readings by column, reports)."""
    inst, mod = instrument(name)
    for step in inst["pipeline"][1:]:
        kind, _, fn = step.partition(":")
        x = getattr(door if kind == "door" else mod, fn)(x, ctx)
        if isinstance(x, door.Null):
            return {c: Reading(None, None, None, x.value, k, ctx.eps[c], x.reason)
                    for c, k in inst["columns"].items()}, {}
    return {c: read_vector(name, c, x[c], ctx) for c in inst["columns"]}, {r: x[r] for r in inst["reports"]}


def after_reduce(name, x, ctx):
    return after(name, x, ctx)[0]


def codes_of(cells, tables):
    """Every helper and signature column for one point; nulls pass through; a point-size source is combined."""
    cols, nulls = declare.code_cols(tables.codes), tables.codes["null_rank"]
    memo = {}

    def one(name, cell):
        return cell if cell in nulls else cols[name]["map"][cell]

    def val(name):
        if name not in memo:
            c, src = cols[name], cols[name]["from"]
            if isinstance(src, str):
                raw = cells.get(src, "NOT-MEASURED")
                if isinstance(raw, list):
                    memo[name] = min((one(name, x) for x in raw), key=c["combine"]["rank"].index)
                else:
                    memo[name] = one(name, raw)
            else:
                a, b = val(src[0]), val(src[1])
                hit = [x for x in nulls if x in (a, b)]
                memo[name] = hit[0] if hit else c["map"][f"{a},{b}"]
        return memo[name]
    return {n: val(n) for n in cols}


def signature_from_cells(cells, tables):
    codes = codes_of(cells, tables)
    return {n: codes[n] for n in tables.codes["columns"]["signature"]}


def verdict_of(signature, tables):
    """(verdict, verdict class, line of the matching row, its why): the rows partition, so one row matches."""
    for k, row in enumerate(tables.verdict["row"]):
        if all(signature[c] in v for c, v in row["when"].items()):
            v = row["verdict"]
            cls = "REFUSE" if v in tables.verdict["refuse"] else tables.verdict.get("class_of", {}).get(v, v)
            return v, cls, tables.lines[k], row["why"]
    raise ValueError(f"no verdict row contains {signature}")


def sources(name, cols):
    """The registry columns ('<instrument>.<column>') a code column is derived from."""
    src = cols[name]["from"]
    return {src} if isinstance(src, str) else sources(src[0], cols) | sources(src[1], cols)


def gather(cache, blocks, idx, bi, array):
    """One block's array cut to this row's index set, once per row however many instruments read it."""
    if (bi, array) not in cache:
        cache[(bi, array)] = blocks[bi][1][array][idx[bi]]
    return cache[(bi, array)]


def read_hashes(m, input_id, tables, T, c):
    """sha256 of exactly the files a run reads; a data file that differs from its pin is refused."""
    name = f"inputs/{input_id}/m.toml"
    read = {name: declare.sha(ROOT / name)}
    for n in m["instruments"]:
        read[f"instruments/{n}.toml"] = declare.sha(ROOT / "instruments" / f"{n}.toml")
    for path, f in zip(T.paths, ("codes", "verdict")):
        read[f"tables/{tables}/{f}.toml"] = declare.sha(path)
    mf = ROOT / "fixtures" / "data" / f"{input_id}.toml"
    if not mf.is_file():
        raise refused(f"no data manifest fixtures/data/{input_id}.toml", f"bin/cc data add {input_id}")
    read[f"fixtures/data/{input_id}.toml"] = declare.sha(mf)
    pinned = tomllib.loads(mf.read_text())["files"]
    for b in m["data"]["files"]:
        key = f"{c.cfg['data']['root']}/{b['path']}"
        if key not in read:
            read[key] = declare.sha(c.data_root / b["path"])
            if pinned.get(b["path"]) != read[key]:
                raise refused(f"fixtures/data/{input_id}.toml: {b['path']} changed since it was pinned",
                              f"if intended, make a new input: bin/cc new input {input_id}-2 --like {input_id}, "
                              f"then bin/cc data add {input_id}-2")
    return read


def measure(m, c, reg):
    """The streaming pass: one resample plan; every unit of every declared instrument reduced row by row,
    then its door and stage steps and readout. Returns {(instrument, point, size): (readings, reports)}."""
    blocks = door.load_blocks(m, c.data_root)
    pos, sizes = {k: i for i, (k, _) in enumerate(blocks)}, m["axes"]["size"]
    units = [(n, pt, sz) for n in m["instruments"] for pt in m["axes"]["point"]
             for sz in (sizes if reg[n][0]["unit"] == "point-size" else [None])]
    ctxs = {(n, sz): door.context(m, reg[n][0], sz) for n, _, sz in units}
    acc = {u: [] for u in units}
    for idx in door.resample_plan(m, [len(next(iter(a.values()))) for _, a in blocks]):
        cache = {}
        for n, pt, sz in units:
            inst = reg[n][0]
            keys = door.unit_keys(m, inst, pt, sz)
            arrays = {a: [gather(cache, blocks, idx, pos[k], a) for k in keys] for a in inst["arrays"]}
            acc[(n, pt, sz)].append(reg[n][1].reduce(arrays, ctxs[(n, sz)]))
    return {u: after(u[0], np.stack(v), ctxs[(u[0], u[2])]) for u, v in acc.items()}


def point_rows(m, c, reg, out, pt):
    """Every registry column at one point as (instrument, column, eps key, flags, [(size, Reading)], source);
    an instrument this input does not declare reads NOT-MEASURED."""
    rows, flagmap = [], c.cfg["obtained_flag"]
    for n, (inst, _) in reg.items():
        on = n in m["instruments"]
        flags = sorted(set(inst["flags"]) | {flagmap[m["obtained"][pt]]}) if on else []
        sizes = m["axes"]["size"] if on and inst["unit"] == "point-size" else [None]
        for col, ek in inst["columns"].items():
            none = Reading(None, None, None, "NOT-MEASURED", ek, None, f"{n} is not declared on this input")
            per = [(sz, out[(n, pt, sz)][0][col] if on else none) for sz in sizes]
            rows.append((n, col, ek, flags, per, f"{n}.{col}"))
    return rows


def reading_dict(row, pt, codes, direct, cols):
    """One reading as the result JSON holds it; a point-size reading keeps its numbers per size."""
    n, col, ek, flags, per, src = row
    r0, point_size = per[0][1], len(per) > 1 or per[0][0] is not None
    per_size = [{"size": sz, "estimate": r.estimate, "lo": r.lo, "hi": r.hi, "cell": r.cell,
                 "code": cols[direct[src]]["map"].get(r.cell, r.cell)} for sz, r in per] if point_size else None
    full = None if point_size or r0.vector is None else f"{n}/{col}/point={pt}"
    return {"instrument": n, "column": col, "unit": {"point": pt}, "eps_key": ek, "eps": r0.eps,
            "estimate": None if point_size else r0.estimate, "lo": None if point_size else r0.lo,
            "hi": None if point_size else r0.hi, "cell": None if point_size else r0.cell,
            "code": codes.get(direct.get(src), r0.cell), "per_size": per_size, "flags": flags,
            "reason": r0.reason, "vector_key": full}


def run(input_id, tables, write, tables_dir=None):
    m, c, T = load_input(input_id), declare.Ctx(ROOT), load_tables(tables, tables_dir)
    reg = {n: instrument(n) for n in sorted(c.reg)}
    read, out = read_hashes(m, input_id, tables, T, c), measure(m, c, reg)
    cols = declare.code_cols(T.codes)
    direct = {s["from"]: n for n, s in cols.items() if isinstance(s["from"], str)}
    readings, reports, vectors, signature = [], [], {}, []
    for pt in m["axes"]["point"]:
        rows, cells = point_rows(m, c, reg, out, pt), {}
        for n, col, ek, flags, per, src in rows:
            point_size = len(per) > 1 or per[0][0] is not None
            cells[src] = [r.cell for _, r in per] if point_size else per[0][1].cell
            for sz, r in per:
                if r.vector is not None:
                    vectors[f"{n}/{col}/point={pt}" + (f",size={sz}" if sz else "")] = r.vector
        for n, (inst, _) in reg.items():
            for rn in inst["reports"] if n in m["instruments"] else []:
                v = out[(n, pt, None)][1].get(rn)
                if v is not None:
                    key = f"{n}/{rn}/point={pt}"
                    reports.append({"instrument": n, "name": rn, "unit": {"point": pt},
                                    "estimate": np.asarray(v)[0].tolist(), "vector_key": key})
                    vectors[key] = np.asarray(v)
        codes = codes_of(cells, T)
        sig = {n: codes[n] for n in T.codes["columns"]["signature"]}
        verdict, cls, line, why = verdict_of(sig, T)
        mine = [reading_dict(row, pt, codes, direct, cols) for row in rows]
        flags = {s: sorted({f for rd in mine if f"{rd['instrument']}.{rd['column']}" in sources(s, cols)
                            for f in rd["flags"]}) for s in sig}
        readings += mine
        signature.append({"point": pt, "obtained": m["obtained"][pt], **sig,
                          "flags": {s: f for s, f in flags.items() if f}, "verdict": verdict,
                          "verdict_class": cls, "row_line": line, "why": why})
    commit = "none"
    if write and (ROOT / ".git").exists():
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        commit = r.stdout.strip() or "none"
    rid = f"{input_id}@{tables}"
    res = {"schema": 1, "kind": "result", "run_id": rid, "input": input_id, "tables": tables,
           "derived_from": None, "code_commit": commit, "interval": dict(m["interval"]), "read": read,
           "vectors": f"results/{rid}.npz",
           "readings": readings, "reports": reports, "signature_columns": list(T.codes["columns"]["signature"]),
           "signature": signature}
    if write:
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / f"{rid}.json").write_text(json.dumps(res, indent=1) + "\n")
        np.savez(ROOT / "results" / f"{rid}.npz", **vectors)
    return res
