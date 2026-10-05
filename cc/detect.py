"""detect.py - input -> resample plan -> instruments -> codes -> signature -> verdict (plumbing; methods).
The staged entry points the breakers and the scoreboard call are the same functions `run` is built from."""
import dataclasses
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
import resources

ROOT = Path(__file__).resolve().parent.parent
AXES = ("geometry", "order", "compose")
AXIS_FILES = ("geometry", "probe", "order", "compose")   # probe.toml (plan 0870) is optional: a projection of the geometry by the declared probe
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
    door: str = None          # a pair reading: the membership door value that decided whether its unit ran


@dataclass
class Tables:
    name: str
    codes: dict
    verdict: dict
    lines: list
    paths: tuple
    membership: dict = dataclasses.field(default_factory=dict)   # instrument name -> its rule (membership.toml)
    membership_path: object = None
    axes: dict = dataclasses.field(default_factory=dict)         # geometry / order / compose -> (table, row lines); empty for a set without them


def refused(msg, nxt):
    return ValueError(f"{msg}\n  Next: {nxt}")


@functools.lru_cache(maxsize=None)
def instrument(name):
    d = tomllib.loads((ROOT / "instruments" / f"{name}.toml").read_text())
    return d, importlib.import_module(d["module"])   # measure-key: seeded


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
    mp = d / "membership.toml"
    ax = [d / f"{n}.toml" for n in AXIS_FILES if (d / f"{n}.toml").is_file()]
    bad = [f for q in (d / "codes.toml", d / "verdict.toml", *[mp] * mp.is_file(), *ax) for f in declare.check_file(q, ROOT)]
    if bad:
        raise ValueError("\n".join(declare.fmt(f) for f in bad))
    texts = [(d / f).read_text() for f in ("codes.toml", "verdict.toml")]
    rules = {k: v for k, v in tomllib.loads(mp.read_text()).items() if isinstance(v, dict)} if mp.is_file() else {}
    axes = {q.stem: (tomllib.loads(q.read_text()), declare.row_lines(q.read_text())) for q in ax}
    return Tables(name, tomllib.loads(texts[0]), tomllib.loads(texts[1]), declare.row_lines(texts[1]),
                  (d / "codes.toml", d / "verdict.toml", *ax), rules, mp if mp.is_file() else None, axes)


def context_for(input_id, instrument_name, point, size=None):
    return door.context(load_input(input_id), instrument(instrument_name)[0], size)


def read_vector(instrument_name, column, v, ctx):
    """The readout of one resampled column: estimate, interval and sign cell against its declared eps."""
    est, lo, hi, cell = readout.reading(np.asarray(v, float), ctx.level, ctx.eps[column])
    eps_key = instrument(instrument_name)[0]["columns"][column]
    return Reading(float(est), float(lo), float(hi), cell, eps_key, ctx.eps[column], None, np.asarray(v))


def after(name, x, ctx):
    """The declared door and stage steps after stage:reduce, then readout: (readings by column, reports).
    A report is kept as soon as a stage has produced it, so a later refusal does not drop it."""
    inst, mod = instrument(name)
    seen = {}
    for step in inst["pipeline"][1:]:
        kind, _, fn = step.partition(":")
        x = getattr(door if kind == "door" else mod, fn)(x, ctx)
        if isinstance(x, door.Null):
            return {c: Reading(None, None, None, x.value, k, ctx.eps[c], x.reason, None, ctx.member and ctx.member["door"])
                    for c, k in inst["columns"].items()}, {r: seen[r] for r in inst["reports"] if r in seen}
        seen.update({k: v for k, v in x.items() if k in inst["reports"]} if isinstance(x, dict) else {})
    out = {c: read_vector(name, c, x[c], ctx) for c in inst["columns"]}
    for r in out.values():
        r.door = ctx.member and ctx.member["door"]
    return out, {r: seen[r] for r in inst["reports"]}


def after_reduce(name, x, ctx):
    return after(name, x, ctx)[0]


def preferred(got, doors, prefer):
    """The items read on the preferred door value when at least one is; else all of them (declared per column: combine.prefer_door; plan 0874)."""
    return [g for g, d in zip(got, doors) if d == prefer] or got


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
                    got = [one(name, x) for x in raw]    # sizes ascend: a code in top_only counts only when the LARGEST size reads it (plan 0870)
                    got = preferred(got, cells.get(src + "@door", [None] * len(got)), c["combine"].get("prefer_door"))   # plan 0874: only the pairs on the preferred door value, when there is one
                    best = min((v for i, v in enumerate(got) if v not in c["combine"].get("top_only", []) or i == len(got) - 1),
                               key=c["combine"]["rank"].index)
                    memo[name] = c["combine"]["disagree"] if best in c["combine"].get("agree", []) and set(got) != {best} else best   # plan 0872: an `agree` code counts only when EVERY item reads it
                else:
                    memo[name] = one(name, raw)
            else:
                a, b = val(src[0]), val(src[1])
                watch = () if c.get("nullable") == "either" else (a,) if c.get("nullable") else (a, b)   # nullable: a null of the 2nd source is a cell of the map; "either": of both (plan 0877 D2)
                hit = [x for x in nulls if x in watch]
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


def row_of(table, vals):
    """The index of the one row of a partition table whose `when` holds `vals` (the rows partition, so one matches)."""
    return next(k for k, row in enumerate(table["row"]) if all(vals[c] in v for c, v in row["when"].items()))


def composed(gv, ov, T):
    """(verdict, index of the compose row) for one (geometry, order): the row's verdict, or the geometry when it says @geometry."""
    cm, k = T.axes["compose"][0], row_of(T.axes["compose"][0], {"geometry": gv, "order": ov})
    v = cm["row"][k]["verdict"]
    return (gv if v == "@geometry" else v), k


def axes_of(codes, T):
    """The geometry and order of one point, and the lines of the three rows that gave them and the verdict:
    {} for a set without the axes. compose(geometry, order) is the verdict (validate proves it on every row)."""
    if not T.axes:
        return {}
    (g, gl), (o, ol), (_, cl) = (T.axes[n] for n in AXES)
    gk, ok = row_of(g, codes), row_of(o, codes)
    gv, ov = g["row"][gk]["verdict"], o["row"][ok]["verdict"]
    pl = {}
    if "probe" in T.axes:   # plan 0870: the geometry as the declared probe lets it stand
        (pt, pls), pk = T.axes["probe"], row_of(T.axes["probe"][0], {"probe": codes["probe"], "geometry": gv})
        gv, pl = (gv if pt["row"][pk]["verdict"] == "@geometry" else pt["row"][pk]["verdict"]), {"probe": pls[pk]}
    return {"geometry": gv, "order": ov, "axis_lines": {"geometry": gl[gk], **pl, "order": ol[ok],
                                                         "compose": cl[composed(gv, ov, T)[1]]}}


def used(T):
    """The registry columns ('<instrument>.<column>') some code column of this set reads."""
    cols = declare.code_cols(T.codes)
    return set().union(*(sources(n, cols) for n in cols))


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
    for path in T.paths:
        read[f"tables/{tables}/{path.name}"] = declare.sha(path)
    if any("door:off_manifold" in c.reg[n]["pipeline"] for n in m["instruments"]) and T.membership_path is None:
        raise refused(f"tables/{tables} has no membership.toml, and {input_id} declares an instrument whose "
                      "door reads one", f"copy tables/v01-rules/membership.toml into tables/{tables}/")
    if T.membership_path is not None and any({"door:off_manifold", "door:basis"} & set(c.reg[n]["pipeline"]) for n in m["instruments"]):   # plan 0874: door:basis reads a rule when the set has one
        read[f"tables/{tables}/membership.toml"] = declare.sha(T.membership_path)
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


def probe_of(m, cp):
    """The probe code of an input from its declaration: UNKNOWN when its couplings are unknown, NOT-MEASURED when it declares no
    across, else COMPLETE when every declared coupling is probed and INCOMPLETE when one is not."""
    return "NOT-MEASURED" if "across" not in m["instruments"] else (
        "UNKNOWN" if cp["names"] == "unknown" else ("COMPLETE", "INCOMPLETE")[not set(cp["names"]) <= set(cp["probes"])])


def declared_of(input_id, m, T):
    """{'declared.<kind>': cell} for the declared columns of the set (empty for a set with none); the file is read, never guessed."""
    if not declare.declared_cols(T.codes):
        return {}
    p = ROOT / "inputs" / input_id / "couplings.toml"
    if not p.is_file():
        raise refused(f"inputs/{input_id}/couplings.toml does not exist, and tables/{T.name} reads a declared column",
                      "write it: kind = \"couplings\", id, names (from the Hamiltonian) and probes (which of them across probes)")
    return {"declared.probe": probe_of(m, tomllib.loads(p.read_text()))}


def cells_of_rows(rows):
    """The sign cells of one point as `<instrument>.<column>` -> cell (a list per size for a point-size column)."""
    return {**{src: [r.cell for _, r in per] if len(per) > 1 or per[0][0] is not None else per[0][1].cell
               for _, _, _, _, per, src in rows},
            **{src + "@door": [r.door for _, r in per] for _, _, _, _, per, src in rows if per[0][1].door is not None}}   # plan 0874: the door value each pair read on, beside its cell


def measure(m, c, reg, T):
    """The streaming pass: one resample plan; every unit of every declared instrument reduced row by row,
    then its door and stage steps and readout. Two passes after the stream: instruments with empty `requires`
    first and coded, then the dependents, whose membership door reads those codes.
    Returns {(instrument, unit, size): (readings, reports)}."""
    blocks = door.load_blocks(m, c.data_root)
    pos = {k: i for i, (k, _) in enumerate(blocks)}
    units = [(n, u, sz) for n in m["instruments"] for u, sz in door.unit_labels(m, reg[n][0])]
    ctxs = {(n, sz): door.context(m, reg[n][0], sz) for n, _, sz in units}
    acc = {u: [] for u in units}
    for idx in door.resample_plan(m, [len(next(iter(a.values()))) for _, a in blocks]):
        cache = {}
        for n, u, sz in units:
            inst = reg[n][0]
            keys = door.unit_keys(m, inst, u, sz)
            arrays = {a: [gather(cache, blocks, idx, pos[k], a) for k in keys] for a in inst["arrays"]}
            acc[(n, u, sz)].append(reg[n][1].reduce(arrays, ctxs[(n, sz)]))
    first = {u: after(u[0], np.stack(v), ctxs[(u[0], u[2])]) for u, v in acc.items() if not reg[u[0]][0].get("requires")}
    wait = {n for n in m["instruments"] if reg[n][0].get("requires")}
    codes = {pt: codes_of(cells_of_rows(point_rows(m, c, reg, first, pt, used(T), wait)), T) for pt in m["axes"]["point"]}
    nc = ctxs.get(("needle_chain", None))   # plan 0874: the endpoints' resampled drift gives a TRANSFORMED pair its ratio r
    for u, v in acc.items():
        if reg[u[0]][0].get("requires"):
            inst, ctx = reg[u[0]][0], ctxs[(u[0], u[2])]
            mem = door.member_for(inst, T.membership, u[0], u[1], codes)
            ratio = door.ratio_of(mem["door"], lambda pt: first[("needle_chain", pt, None)][0]["drift"].vector, u[1],
                                  lambda: nc.log_ratio[nc.top], ctx.component_shape[0]) if "door:basis" in inst["pipeline"] else None
            first[u] = after(u[0], np.stack(v), dataclasses.replace(ctx, member=mem, ratio=ratio))
    return first


def labelled(m, inst, n, pt, on):
    """[(label, unit key)] one instrument is read at for one point: a point-size instrument at every size, a per_point pair instrument at
    every control pair that touches the point (label `a->b`), any other at the point alone (label None)."""
    if not on:
        return [(None, None)]
    if inst["unit"] == "pair":
        return [("->".join(p), (n, p, None)) for p in door.control_pairs(m) if pt in p]
    return [(sz, (n, pt, sz)) for sz in (m["axes"]["size"] if inst["unit"] == "point-size" else [None])]


def point_rows(m, c, reg, out, pt, use, pending=()):
    """Every registry column at one point that the table set reads (`use`) as (instrument, column, eps key, flags,
    [(label, Reading)], source); an instrument this input does not declare reads NOT-MEASURED; a pair instrument is
    read per point only when it declares per_point (plan 0872), one Reading per control pair that touches the point."""
    rows, flagmap = [], c.cfg["obtained_flag"]
    for n, (inst, _) in reg.items():
        if (inst["unit"] == "pair" and not inst.get("per_point")) or n in pending:
            continue   # a pair instrument has no point row: its readings are pair_readings; a `pending` instrument (its membership reads these codes) is not read yet
        on = n in m["instruments"]
        flags = sorted(set(inst["flags"]) | {flagmap[m["obtained"][pt]]}) if on else []
        labs = labelled(m, inst, n, pt, on)
        for col, ek in ((k, e) for k, e in inst["columns"].items() if f"{n}.{k}" in use):
            none = Reading(None, None, None, "NOT-MEASURED", ek, None, f"{n} is not declared on this input")
            lone = Reading(None, None, None, "NOT-EVALUATED", ek, None, f"no control pair touches point {pt}")   # a per_point instrument on a point no pair touches
            per = [(lab, out[key][0][col] if on else none) for lab, key in labs] or [(None, lone)]
            rows.append((n, col, ek, flags, per, f"{n}.{col}"))
    return rows


def ukey(unit):
    """The vector-key form of a unit: point=<label> or pair=<a>-><b>."""
    return "pair=" + "->".join(unit["pair"]) if "pair" in unit else f"point={unit['point']}"


def reading_dict(row, unit, codes, direct, cols):
    """One reading as the result JSON holds it; a point-size reading keeps its numbers per size."""
    n, col, ek, flags, per, src = row
    r0, point_size = per[0][1], len(per) > 1 or per[0][0] is not None
    per_size = [{"size": sz, "estimate": r.estimate, "lo": r.lo, "hi": r.hi, "cell": r.cell,
                 "code": cols[direct[src]]["map"].get(r.cell, r.cell), **({"door": r.door} if r.door is not None else {})}
                for sz, r in per] if point_size else None
    full = None if point_size or r0.vector is None else f"{n}/{col}/{ukey(unit)}"
    return {"instrument": n, "column": col, "unit": unit, "eps_key": ek, "eps": r0.eps,
            "estimate": None if point_size else r0.estimate, "lo": None if point_size else r0.lo,
            "hi": None if point_size else r0.hi, "cell": None if point_size else r0.cell,
            "code": codes.get(direct.get(src), r0.cell), "per_size": per_size, "flags": flags,
            "reason": r0.reason, "vector_key": full}


def pair_results(m, c, reg, out, vectors):
    """(pair_readings, pairs, reports) of every pair instrument: one reading per (pair, column), one summary row
    per pair. A pair takes the flags of both its points, the registry flags, and U when its membership was unchecked."""
    readings, pairs, reports, flagmap = [], [], [], c.cfg["obtained_flag"]
    for n, (inst, _) in reg.items():
        if n not in m["instruments"] or inst["unit"] != "pair":
            continue
        for pair in door.control_pairs(m):
            res, reps = out[(n, pair, None)]
            unit, first = {"pair": list(pair)}, res[next(iter(inst["columns"]))]
            flags = sorted(set(inst["flags"]) | {flagmap[m["obtained"][pt]] for pt in pair}
                           | ({"U"} if first.door == "RUN-FLAG-U" else set()))
            for col, ek in inst["columns"].items():
                readings.append(reading_dict((n, col, ek, flags, [(None, res[col])], f"{n}.{col}"), unit, {}, {}, {}))
                if res[col].vector is not None:
                    vectors[f"{n}/{col}/{ukey(unit)}"] = res[col].vector
            pairs.append({"pair": list(pair), n: first.cell, "flags": flags, **({inst["door_label"]: first.door} if "door_label" in inst else {})})
            for rn, v in reps.items():
                key = f"{n}/{rn}/{ukey(unit)}"
                reports.append({"instrument": n, "name": rn, "unit": unit, "estimate": np.asarray(v)[0].tolist(),
                                "vector_key": key})
                vectors[key] = np.asarray(v)
    return readings, pairs, reports


def keyed(st, read, mhash, own_tables=True):
    """True when stored result `st` has this run's key: the same read hashes (without the tables/* entries when `own_tables` is
    False) and the same measurement hash (plan 0876 B: the import closure of what measures, not all of cc/). A result without a measure hash has no key. A derived result also reads its parent's file:
    that must still hash as recorded."""
    parent = {k for k in st["read"] if k.startswith("results/")}
    take = lambda r: {k: h for k, h in r.items() if k not in parent and (own_tables or not k.startswith("tables/"))}   # noqa: E731
    return (st.get("measure_hash") == mhash and take(st["read"]) == take(read) and (ROOT / st.get("vectors", "")).is_file()
            and all((ROOT / k).is_file() and declare.sha(ROOT / k) == st["read"][k] for k in parent))


def stored(input_id, tables, read, mhash):
    """The stored result that IS this run's result (plan 0876), else None: the same key under the same set; or a measured result
    under another set whose key differs only in tables/* and whose membership decided nothing different, to be re-verdicted
    (`derived_from` set, nothing measured). Hash equality is the only policy."""
    import reverdict
    p = ROOT / "results" / f"{input_id}@{tables}.json"
    if p.is_file() and keyed(st := json.loads(p.read_text()), read, mhash):
        return st
    for q in sorted((ROOT / "results").glob(f"{input_id}@*.json")):
        st = json.loads(q.read_text())
        if (st["tables"] != tables and st.get("derived_from") is None and keyed(st, read, mhash, False)
                and reverdict.reverdict_refusal(st, tables) is None):
            return st
    return None


def run(input_id, tables, write, tables_dir=None, reuse=True):
    """The result of one input under one table set. `reuse=False` always measures (a replay test exists to re-measure)."""
    return run_keyed(input_id, tables, write, tables_dir, reuse)[0]


def run_keyed(input_id, tables, write, tables_dir=None, reuse=True):
    """(result, how): how is 'measured', 'stored' (the keyed stored result) or 're-verdicted' (from a stored result under another set)."""
    m, c, T = load_input(input_id), declare.Ctx(ROOT), load_tables(tables, tables_dir)
    reg = {n: instrument(n) for n in sorted(c.reg)}
    read, decl = read_hashes(m, input_id, tables, T, c), declared_of(input_id, m, T)
    read.update({f"inputs/{input_id}/couplings.toml": declare.sha(ROOT / "inputs" / input_id / "couplings.toml")} if decl else {})
    chash, rid = declare.code_hash(ROOT), f"{input_id}@{tables}"
    mhash = declare.measure_hash(ROOT, [reg[n][0]["module"] for n in m["instruments"]])
    if reuse and tables_dir is None and (st := stored(input_id, tables, read, mhash)) is not None:
        if st["tables"] == tables:
            return st, "stored"   # the stored result IS the result: nothing is re-written
        import reverdict
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() if write else ""
        res = reverdict.reverdict_result(st, T, git or "none")
        if write:
            (ROOT / "results" / f"{rid}.json").write_text(json.dumps(res, indent=1) + "\n")
        return res, "re-verdicted"
    resources.reset_peak()
    out = measure(m, c, reg, T)
    peak = resources.peak_mb()   # the high-water mark of this one input's measurement (plan 0881 P1.1)
    cols = declare.code_cols(T.codes)
    direct = {s["from"]: n for n, s in cols.items() if isinstance(s["from"], str)}
    readings, reports, vectors, signature = [], [], {}, []
    for pt in m["axes"]["point"]:
        rows = point_rows(m, c, reg, out, pt, used(T))
        cells = {**cells_of_rows(rows), **decl}
        for n, col, ek, flags, per, src in rows:
            for sz, r in per:
                if r.vector is not None:
                    vectors[f"{n}/{col}/point={pt}" + (f",size={sz}" if sz else "")] = r.vector
        for n, (inst, _) in reg.items():
            for rn in inst["reports"] if n in m["instruments"] and inst["unit"] != "pair" else []:
                v = out[(n, pt, None)][1].get(rn)
                if v is not None:
                    key = f"{n}/{rn}/point={pt}"
                    reports.append({"instrument": n, "name": rn, "unit": {"point": pt},
                                    "estimate": np.asarray(v)[0].tolist(), "vector_key": key})
                    vectors[key] = np.asarray(v)
        codes = codes_of(cells, T)
        sig = {n: codes[n] for n in T.codes["columns"]["signature"]}
        verdict, cls, line, why = verdict_of(sig, T)
        mine = [reading_dict(row, {"point": pt}, codes, direct, cols) for row in rows]
        flags = {s: sorted({f for rd in mine if f"{rd['instrument']}.{rd['column']}" in sources(s, cols)
                            for f in rd["flags"]}) for s in sig}
        readings += mine
        signature.append({"point": pt, "obtained": m["obtained"][pt], **sig,
                          "flags": {s: f for s, f in flags.items() if f}, "verdict": verdict,
                          "verdict_class": cls, "row_line": line, "why": why, **axes_of(codes, T)})
    pair_readings, pairs, pair_reports = pair_results(m, c, reg, out, vectors)
    commit = "none"
    if write and (ROOT / ".git").exists():
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        commit = r.stdout.strip() or "none"
    res = {"schema": 1, "kind": "result", "run_id": rid, "input": input_id, "tables": tables,
           "derived_from": None, "code_commit": commit, "code_hash": chash, "measure_hash": mhash, "peak_rss_mb": round(peak, 1), "interval": dict(m["interval"]), "read": read,
           "vectors": f"results/{rid}.npz",
           "readings": readings, "pair_readings": pair_readings, "reports": reports + pair_reports,
           "signature_columns": list(T.codes["columns"]["signature"]), "signature": signature, "pairs": pairs,
           **({"declared": {k.split(".", 1)[1]: v for k, v in decl.items()}} if decl else {})}
    if write:
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / f"{rid}.json").write_text(json.dumps(res, indent=1) + "\n")
        np.savez(ROOT / "results" / f"{rid}.npz", **vectors)
    return res, "measured"
