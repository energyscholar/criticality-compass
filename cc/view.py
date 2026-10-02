"""view.py - show and explain: one result printed as BASIC (a declared projection) or ADVANCED (every field).
Pure over the result: a view never changes it. Plumbing."""
import tomllib
from pathlib import Path
import numpy as np
import declare
import detect
import door
import sign

ROOT = Path(__file__).resolve().parent.parent
UNRES_REASON = "interval straddles 0 and a margin edge"   # sign.py's meaning of UNRES


def config():
    return tomllib.loads((ROOT / "cc.toml").read_text())


def stale(res, root=ROOT):
    """The refusal text for a result whose recorded `read` hashes no longer match, else None."""
    for k, h in res["read"].items():
        p = Path(k).expanduser() if k.startswith("~") else Path(root) / k
        if not p.is_file() or declare.sha(p) != h:
            return (f"REFUSED: {k} changed since {res['run_id']} was run.\n"
                    f"  Next: bin/cc run {res['input']} --tables {res['tables']} (or restore the file)")
    return None


def cells_of(res, pt):
    """The sign cells of one point as `<instrument>.<column>` -> cell (a list per size for a point-size column)."""
    return {f"{r['instrument']}.{r['column']}": [q["cell"] for q in r["per_size"]] if r["per_size"] else r["cell"]
            for r in res["readings"] if r["unit"]["point"] == pt}


def feeders(res, pt, col, cols):
    src = detect.sources(col, cols)
    return [r for r in res["readings"] if r["unit"]["point"] == pt and f"{r['instrument']}.{r['column']}" in src]


def shown(v, reason, mode, cfg):
    """BASIC prints a don't-know value as BLANK (<value>: <reason>): the precise name is always inside."""
    return f"BLANK ({v}: {reason or UNRES_REASON})" if mode == "basic" and v in cfg["basic"]["blank"] else v


def words(flags, cfg):
    return ", ".join(cfg["flags"][f] for f in flags)


def join_line(items, mode, cfg):
    """The BASIC projection: only the fields cc.toml [basic].keeps; ADVANCED prints every item."""
    return " ".join(t for f, t in items if mode == "advanced" or f in cfg["basic"]["keeps"])


def column_line(col, rs, sig, mode, cfg):
    """One signature column: its readings (estimate, interval, cell), the code, and in ADVANCED the discarded fields."""
    code, items, late, celled = sig[col], [], [], False
    reason = next((r["reason"] for r in rs if r["reason"]), None)
    rs = [r for r in rs if r["estimate"] is not None or r["per_size"]]   # a null reading shows only as the BLANK
    for r in rs:
        if len(rs) > 1:
            items.append(("column", r["column"]))
        if r["estimate"] is not None:
            items += [("estimate", f"{r['estimate']:.4g}"), ("lo", f"[{r['lo']:.4g},"), ("hi", f"{r['hi']:.4g}]")]
        celled = len(rs) > 1 or r["cell"] not in (None, code)
        if celled:
            items.append(("cell", shown(r["cell"], None, mode, cfg)))
        if r["eps"] is not None:
            (items if celled else late).append(("eps", f"eps {r['eps_key']}={r['eps']}"))
    if celled:
        items.append(("code", "->"))
    items.append(("code", shown(code, reason, mode, cfg)))
    items += late
    if reason and not (mode == "basic" and code in cfg["basic"]["blank"]):
        items.append(("reason", f"({reason})"))
    r0 = rs[0] if rs else {"eps": None, "per_size": None, "vector_key": None}
    if r0["per_size"]:
        items.append(("per_size", "per size: " + "; ".join(f"{q['size']} {q['cell']} {q['code']}" for q in r0["per_size"])))
    if sig["flags"].get(col):
        items.append(("flags", "flags: " + words(sig["flags"][col], cfg)))
    if r0["vector_key"] and len(rs) == 1:
        items.append(("vector_key", f"vector {r0['vector_key']}"))
    return f"  {col:<10} " + join_line(items, mode, cfg)


def verdict_lines(sig, mode, cfg, pad="  "):
    blank = mode == "basic" and cfg["basic"]["blank_refuse"] and sig["verdict_class"] == "REFUSE"
    v = f"BLANK ({sig['verdict']})" if blank else sig["verdict"]
    adv = f"  class {sig['verdict_class']}, verdict.toml line {sig['row_line']}"
    return [f"{pad}=> verdict {v}" + adv * (mode == "advanced"), f"{pad}   why: {sig['why']}"]


def pair_lines(res, mode, cfg):
    """The control pairs of a result, one line per (pair, column); empty when the input declares no pair instrument."""
    out = ["pairs (each edge of the declared control relation)"] if res.get("pair_readings") else []
    for r in res.get("pair_readings", []):
        a, b = r["unit"]["pair"]
        items = [("pairs", f"pair {a}->{b}"), ("column", r["column"])]
        if r["estimate"] is not None:
            items += [("estimate", f"{r['estimate']:.4g}"), ("lo", f"[{r['lo']:.4g},"), ("hi", f"{r['hi']:.4g}]")]
        blank = mode == "basic" and r["cell"] in cfg["basic"]["blank"]
        items += [("cell", shown(r["cell"], r["reason"], mode, cfg)), ("eps", f"eps {r['eps_key']}={r['eps']}")]
        items += [("reason", f"({r['reason']})")] if r["reason"] and not blank else []
        items += [("flags", "flags: " + words(r["flags"], cfg))]
        items += [("vector_key", f"vector {r['vector_key']}")] if r["vector_key"] else []
        out.append("  " + join_line(items, mode, cfg))
    return out


def show(res, join, mode, note="", tables_dir=None):
    """Every point of a result: a header, one line per signature column, a verdict line and its why."""
    bad = stale(res)
    if bad:
        return bad.splitlines()
    cfg, T = config(), detect.load_tables(res["tables"], tables_dir)
    cols, iv = declare.code_cols(T.codes), res["interval"]
    out = [f"{res['input']}   rules: {res['tables']}   result: results/{res['run_id']}.json {note}".rstrip()]
    if mode == "advanced":
        files = [k for k in res["read"] if not k.startswith("~")]
        out += [f"  interval: {iv['method']} resamples {iv['resamples']}, level {iv['level']}, seed {iv['seed']}",
                f"  code_commit: {res['code_commit']}",
                *[f"  read {k} {res['read'][k][:12]}" for k in files],
                f"  read {len(res['read']) - len(files)} data files, sha256 match the pinned manifest"]
    for sig in res["signature"]:
        pt, case = sig["point"], (join or {}).get(sig["point"])
        tag = "" if case is None else f"   case {'' if case == 'none' or (ROOT / 'cases' / (case + '.toml')).is_file() else '?'}{case}"
        out.append(f"point {pt}{tag}" + (f"   obtained: {sig['obtained']}" if mode == "advanced" else ""))
        out += [column_line(c, feeders(res, pt, c, cols), sig, mode, cfg) for c in res["signature_columns"]]
        out += verdict_lines(sig, mode, cfg)
    return out + pair_lines(res, mode, cfg)


# ------------------------------------------------------------------ explain
def ascii_relation(m, name):
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        return " <- ".join(str(v) for v in ax[r["axis"]])
    if r["template"] == "pair":
        return " ; ".join(f"{a} <- {b}" for a, b in r["pairs"])
    nb = m["observable"]["levels"][ax["size"].index(r["big"])]
    return (f"big {r['big']}: L0..L{nb - 1}   small {r['small']}: L0..L{nb - 2}   edges: "
            + " ".join(f"({r['big']},L{k})->({r['small']},L{k - 1})" for k in range(1, nb)))


def map_line(text, name, key):
    """Line number of `"key" = ...` inside the [columns.*.<name>.map] section of codes.toml."""
    lines, head = text.splitlines(), None
    for i, ln in enumerate(lines):
        head = ln if ln.startswith("[") else head
        if head and head.endswith(f".{name}.map]") and ln.startswith(f'"{key}" ='):
            return i + 1
    return 0


def nums(v):
    return "[" + ", ".join(f"{x:.4g}" for x in np.atleast_1d(v)) + "]"


def trace(m, res, r, sz):
    """Steps 1-4 of one instrument unit: the data, what reduce computed at row 0, the relations, the kernel."""
    inst, mod = detect.instrument(r["instrument"])
    pt, ctx = r["unit"]["point"], detect.context_for(res["input"], r["instrument"], r["unit"]["point"], sz)
    blocks = dict(door.load_blocks(m, declare.Ctx(ROOT).data_root))
    keys = door.unit_keys(m, inst, pt, sz)
    files = [b for b in m["data"]["files"] if (b["point"], b["size"], b["start"]) in keys]
    arrays = {a: [blocks[k][a] for k in keys] for a in inst["arrays"]}
    x0 = mod.reduce(arrays, ctx)
    sizes = m["axes"]["size"]
    lab = sizes if len(x0) == len(sizes) else range(len(x0))
    keyed = ", ".join(f"{a} key {files[0]['arrays'][a]['key']}" for a in inst["arrays"])
    out = [(1, "DATA", f"{files[0]['path']} [{keyed}] ... {len(files)} blocks; sha256 matches "
                       f"fixtures/data/{res['input']}.toml"),
           (2, "REDUCE", "row 0: " + ", ".join(f"{k} {v:.4g}" for k, v in zip(lab, x0)))]
    out += [(3, "RELATION", f"{n}: {m['relations'][n]['template']}, {m['relations'][n]['provenance']}   "
                            f"{ascii_relation(m, n)}") for n in inst["relations"]]
    x = x0[None]
    for step in inst["pipeline"][1:]:
        kind, _, fn = step.partition(":")
        x = getattr(door if kind == "door" else mod, fn)(x, ctx)
        if isinstance(x, door.Null):
            return out + [(4, "KERNEL", f"{step} refused: {x.value} ({x.reason})")]
    ops, rels = "/".join(inst["operators"]), ", ".join(inst["relations"])
    return out + [(4, "KERNEL", f"operator {ops} over {rels}; row 0: " + "; ".join(f"{k} {nums(v[0])}" for k, v in x.items()))]


def read_steps(q, r, lv, text, dcol, mode, cfg):
    """Steps 5-7 of one reading (or one size of a point-size reading): interval, sign cell, code."""
    if q["estimate"] is None:
        return [(5, "READING", shown(q["cell"] or r["cell"], r["reason"], mode, cfg))]
    e, (bl, bu) = r["eps"], (int(v) for v in sign.position(q["lo"], q["hi"], r["eps"]))
    block = f", b {lv['b']}" if lv["method"] == "block" else ""
    return [(5, "READING", f"{r['column']} {q['estimate']:.4g}  interval [{q['lo']:.4g}, {q['hi']:.4g}]  "
                           f"({lv['level'] * 100:g} %, {lv['resamples']} {lv['method']} resamples{block})"),
            (6, "SIGN", f"cuts {-e:g} 0 +{e:g} (eps {r['eps_key']}): bL {bl}, bU {bu} -> {shown(q['cell'], None, mode, cfg)}"),
            (7, "CODE", f"{dcol}: codes.toml line {map_line(text, dcol, q['cell'])}: {q['cell']} -> "
                        f"{shown(q['code'], None, mode, cfg)}")]


def explain(res, pt, join, mode, tables_dir=None):
    """The numbered trace of one point: data, reduce, relation, kernel, reading, sign, code, verdict."""
    bad = stale(res)
    if bad:
        return bad.splitlines()
    cfg, T = config(), detect.load_tables(res["tables"], tables_dir)
    cols, m = declare.code_cols(T.codes), detect.load_input(res["input"])
    sig, text, lv = {s["point"]: s for s in res["signature"]}[pt], T.paths[0].read_text(), res["interval"]
    direct = {s["from"]: n for n, s in cols.items() if isinstance(s["from"], str)}
    codes = detect.codes_of(cells_of(res, pt), T)

    def chain(c):   # the derived columns a signature column is built from, parents first
        src = cols[c]["from"]
        return [] if isinstance(src, str) else chain(src[0]) + chain(src[1]) + [c]
    out, traced = [f"explain {res['input']} {pt}   rules: {res['tables']}"], {}
    for c in res["signature_columns"]:
        rs = feeders(res, pt, c, cols)
        live = [r for r in rs if r["cell"] != "NOT-MEASURED"]
        if not live:
            out.append(column_line(c, rs, sig, mode, cfg)[2:])
            continue
        out.append(c)
        for r in live:
            dcol = direct[f"{r['instrument']}.{r['column']}"]
            for q in r["per_size"] or [r]:
                tag = f"L{q['size']} " if r["per_size"] else ""
                sz = q["size"] if r["per_size"] else None
                key, head = (r["instrument"], sz), []
                if q["estimate"] is not None:
                    head = [("1-4", "SAME", f"as under {traced[key]}")] if key in traced else trace(m, res, r, sz)
                    traced.setdefault(key, c)
                steps = head + read_steps(q, r, lv, text, dcol, mode, cfg)
                out += [f"  {n} {w:<9} {tag}{t}" for n, w, t in steps]
            if r["per_size"]:
                out.append(f"  7 CODE      combine.rank {' > '.join(cols[dcol]['combine']['rank'])} (first wins) -> "
                           f"{shown(codes[c], None, mode, cfg)}")
        for d in chain(c):
            a, b = cols[d]["from"]
            ln = map_line(text, d, f"{codes[a]},{codes[b]}")
            out.append(f"  7 CODE      {d} = {shown(codes[d], None, mode, cfg)} from {a} {codes[a]} and {b} {codes[b]}"
                       + f"  (codes.toml line {ln})" * bool(ln))
    row = T.verdict["row"][T.lines.index(sig["row_line"])]
    out.append(f"8 VERDICT   verdict.toml line {sig['row_line']}: "
               + "; ".join(f"when.{k} = [{', '.join(v)}]" for k, v in row["when"].items()))
    return out + verdict_lines(sig, mode, cfg, pad="            ")
