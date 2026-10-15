"""view.py - show and explain: one result printed as BASIC (a declared projection) or ADVANCED (every field).
Pure over the result: a view never changes it. Plumbing."""
import json
import tomllib
from pathlib import Path
import numpy as np
import declare
import detect
import door
import registry
import sign
from reverdict import cells_of   # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
UNRES_REASON = "interval straddles 0 and a margin edge"   # sign.py's meaning of UNRES


def config():
    return tomllib.loads((ROOT / "cc.toml").read_text())


def stale(res, root=ROOT):
    """The refusal text for a result whose recorded `read` hashes no longer match, else None."""
    c = declare.Ctx(root)
    for k, h in res["read"].items():
        p = c.physical(k)
        if not p.is_file() or declare.sha(p) != h:
            return (f"REFUSED: {k} changed since {res['run_id']} was run.\n"
                    f"  Next: bin/cc run {res['input']} --tables {res['tables']} (or restore the file)")
    return None


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


def label_of(r):
    """The name an instrument gives its pairs' door value (door_label), 'door' when it declares none."""
    return detect.instrument(r["instrument"])[0].get("door_label", "door")


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
        if celled and r["cell"] is not None:   # a per-size / per-pair reading holds its cells in per_size
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
    for r in rs:
        if r["per_size"]:
            items.append(("per_size", ("per pair: " if "->" in str(r["per_size"][0]["size"]) else "per size: ")
                          + "; ".join(f"{q['size']} {q['cell']} {q['code']}" + (f" [{label_of(r)} {q['door']}]" if "door" in q else "") for q in r["per_size"])))
    if sig["flags"].get(col):
        items.append(("flags", "flags: " + words(sig["flags"][col], cfg)))
    if r0["vector_key"] and len(rs) == 1:
        items.append(("vector_key", f"vector {r0['vector_key']}"))
    return f"  {col:<10} " + join_line(items, mode, cfg)


def conventional_lines(res, pt, mode, cfg, pad="  "):
    """The readings of the instruments cc.toml [conventional] labels (plan 0881 P2.3): the column stays printed and the declared
    label rides with it. The label is one string in cc.toml, never a per-command edit."""
    out = []
    for r in res["readings"]:
        label = cfg.get("conventional", {}).get(r["instrument"])
        if label is None or r["unit"].get("point") != pt:
            continue
        items = [("column", f"{r['column']} ({label})")]
        if r["estimate"] is not None:
            items += [("estimate", f"{r['estimate']:.4g}"), ("lo", f"[{r['lo']:.4g},"), ("hi", f"{r['hi']:.4g}]")]
        items += [("cell", shown(r["cell"], r["reason"], mode, cfg)), ("eps", f"eps {r['eps_key']}={r['eps']}")] if r["cell"] is not None else []
        items += [("reason", f"({r['reason']})")] if r["reason"] and not (mode == "basic" and r["cell"] in cfg["basic"]["blank"]) else []
        out.append(f"{pad}{r['instrument']:<10} " + join_line(items, mode, cfg))
    return out


def verdict_lines(sig, mode, cfg, pad="  "):
    blank = mode == "basic" and cfg["basic"]["blank_refuse"] and sig["verdict_class"] == "REFUSE"
    v = f"BLANK ({sig['verdict']})" if blank else sig["verdict"]
    adv = f"  class {sig['verdict_class']}, verdict.toml line {sig['row_line']}"
    return [f"{pad}=> verdict {v}" + adv * (mode == "advanced"), f"{pad}   why: {sig['why']}"]


def axes_lines(sig, mode, cfg, pad="  "):
    """The two axes beside the verdict (only a result of a set that has them): BASIC keeps their values, ADVANCED the rows."""
    if "geometry" not in sig:
        return []
    ln = sig["axis_lines"]
    pl = f", probe.toml line {ln['probe']}" if "probe" in ln else ""
    items = [("geometry", f"geometry {sig['geometry']},"), ("order", f"order {sig['order']}"),
             ("axis_lines", f"  (geometry.toml line {ln['geometry']}{pl}, order.toml line {ln['order']}, compose.toml line {ln['compose']})")]
    return [f"{pad}   axes: " + join_line(items, mode, cfg)]


def witnesses(T, res):
    """The code columns the order axis reads that no signature column is: its witnesses (fluct)."""
    return [c for c in T.axes["order"][0]["columns"] if c not in res["signature_columns"]] if T.axes else []


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
        row = next((q for q in res["pairs"] if q["pair"] == [a, b]), {})
        items += [("pairs", f"{label_of(r)} {row[label_of(r)]}")] if label_of(r) in row else []   # plan 0874: the pair's basis (TRANSFORMED / RAW), shown, read by no verdict row
        items += [("reason", f"({r['reason']})")] if r["reason"] and not blank else []
        items += [("flags", "flags: " + words(r["flags"], cfg))]
        items += [("vector_key", f"vector {r['vector_key']}")] if r["vector_key"] else []
        out.append("  " + join_line(items, mode, cfg))
    return out


def identity(key, sha):
    """What a `read` line prints for one read file: its sha12, except for a stored RESULT, whose bytes move whenever anything it was
    measured with is refreshed. A result prints its stable identity: its input@set (its name) and the measure_hash it carries."""
    if not key.startswith("results/"):
        return sha[:12]
    mh = json.loads((ROOT / key).read_text()).get("measure_hash")
    return f"measure_hash {mh[:12]}" if mh else "measure_hash none"


def units_of(res):
    """The registry units a result used, in order of first appearance: its instruments (readings, pair readings, reports) and its interval method."""
    inst = dict.fromkeys(r["instrument"] for r in [*res.get("readings", []), *res.get("pair_readings", []), *res.get("reports", [])])
    return [*(f"instrument.{n}" for n in inst), f"interval.{res['interval']['method']}"]


def show(res, join, mode, note="", tables_dir=None):
    """Every point of a result: a header, one line per signature column, a verdict line and its why."""
    bad = stale(res)
    if bad:
        return bad.splitlines()
    cfg, T = config(), detect.load_tables(res["tables"], tables_dir)
    cols, iv = declare.code_cols(T.codes), res["interval"]
    out = [f"{res['input']}   rules: {res['tables']}   result: results/{res['run_id']}.json {note}".rstrip(),
           f"report: {cfg['report']['verdict']}",   # plan 0893 R1: what every verdict below IS, once per result (cc.toml [report])
           *registry.scope_lines(units_of(res), ROOT)]   # plan 1016: the pinned registry and the scope of each unit, from the CURRENT projection (the stored result is not edited)
    if mode == "advanced":
        files = [k for k in res["read"] if not k.startswith(cfg["data"]["name"] + "/")]
        out += [f"  interval: {iv['method']} " + cfg["interval_fields"][iv["method"]]["show"].format(**iv),
                f"  code_commit: {res['code_commit']}",
                *[f"  read {k} {identity(k, res['read'][k])}" for k in files],
                f"  read {len(res['read']) - len(files)} data files, sha256 match the pinned manifest"]
    import family   # plan 0872 F3: lazy (family imports view)
    notes = family.end_notes(ROOT, res)
    for sig in res["signature"]:
        pt, case = sig["point"], (join or {}).get(sig["point"])
        tag = "" if case is None else f"   case {'' if case == 'none' or (ROOT / 'cases' / (case + '.toml')).is_file() else '?'}{case}"
        out.append(f"point {pt}{tag}" + (f"   obtained: {sig['obtained']}" if mode == "advanced" else ""))
        out += [column_line(c, feeders(res, pt, c, cols), sig, mode, cfg) for c in res["signature_columns"]]
        wit = detect.codes_of(cells_of(res, pt), T)
        out += [column_line(c, feeders(res, pt, c, cols), {**sig, c: wit[c]}, mode, cfg) for c in witnesses(T, res)]
        out += conventional_lines(res, pt, mode, cfg) + verdict_lines(sig, mode, cfg) + axes_lines(sig, mode, cfg) + family.note_lines(notes, pt)
    return out + pair_lines(res, mode, cfg)


# ------------------------------------------------------------------ explain
def ascii_relation(m, name):
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        return " <- ".join(str(v) for v in ax[r["axis"]])
    if r["template"] == "pair":
        return " ; ".join(f"{a} <- {b}" for a, b in r["pairs"])
    if r["template"] == "matched-chain":
        return " ; ".join(f"big {b} vs small {sm}" for b, sm in r["pairs"]) + "   (each pair as a matched relation, laid end to end)"
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


def step_labels(inst, cfg):
    """(step-3 label per relation name, the step-4 label): cc.toml [step_labels] by NAME, and the distinct [step_labels.operator] words
    of the instrument's relations in declared order, joined by "+" (plan 0893 P1, R2)."""
    lab = cfg["step_labels"]
    ops = list(dict.fromkeys(lab["operator"][lab[n]] for n in inst["relations"]))
    return {n: lab[n] for n in inst["relations"]}, "+".join(ops)


def trace(m, res, r, sz):
    """Steps 1-4 of one instrument unit: the data, what reduce computed at row 0, the declared comparisons and relations, the operator."""
    inst, mod = detect.instrument(r["instrument"])
    pt, ctx = r["unit"]["point"], detect.context_for(res["input"], r["instrument"], r["unit"]["point"], sz)
    blocks = dict(door.load_blocks(m, (cx := declare.Ctx(ROOT)).data_root, cx.file))
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
    three, four = step_labels(inst, config())
    out += [(3, three[n], f"{n}: {m['relations'][n]['template']}, {m['relations'][n]['provenance']}   "
                          f"{ascii_relation(m, n)}") for n in inst["relations"]]
    x = x0[None]
    for step in inst["pipeline"][1:]:
        kind, _, fn = step.partition(":")
        x = getattr(door if kind == "door" else mod, fn)(x, ctx)
        if isinstance(x, door.Null):
            return out + [(4, four, f"{step} refused: {x.value} ({x.reason})")]
    ops, rels = "/".join(inst["operators"]), ", ".join(inst["relations"])
    return out + [(4, four, f"operator {ops} over {rels}; row 0: " + "; ".join(f"{k} {nums(v[0])}" for k, v in x.items()))]


def read_steps(q, r, lv, text, dcol, mode, cfg):
    """Steps 5-7 of one reading (or one size of a point-size reading): interval, sign cell, code."""
    if q["estimate"] is None:
        return [(5, "READING", shown(q["cell"] or r["cell"], r["reason"], mode, cfg))]
    e, (bl, bu) = r["eps"], (int(v) for v in sign.position(q["lo"], q["hi"], r["eps"]))
    return [(5, "READING", f"{r['column']} {q['estimate']:.4g}  interval [{q['lo']:.4g}, {q['hi']:.4g}]  "
                           f"({door.COVERAGE[lv['method']](lv) * 100:g} %, {cfg['interval_fields'][lv['method']]['read'].format(**lv)})"),
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
    for c in res["signature_columns"] + witnesses(T, res):
        rs, sig = feeders(res, pt, c, cols), {**sig, c: codes[c]}
        live = [r for r in rs if r["cell"] != "NOT-MEASURED"]
        if not live:
            out.append(column_line(c, rs, sig, mode, cfg)[2:])
            cp = tomllib.loads((ROOT / "inputs" / res["input"] / "couplings.toml").read_text()) if c in declare.declared_cols(T.codes) else None
            out += [f"  declared in inputs/{res['input']}/couplings.toml: couplings {cp['names']}, probed by across {cp['probes']}"] if cp else []
            continue
        out.append(c)
        for r in live:
            dcol = direct[f"{r['instrument']}.{r['column']}"]
            for q in r["per_size"] or [r]:
                if r["per_size"] and detect.instrument(r["instrument"])[0]["unit"] == "pair":   # plan 0872: a per_point pair reading is one cell per control pair
                    steps = [("1-4", "SEE", f"bin/cc explain {res['input']} {q['size']}")] + read_steps(q, r, lv, text, dcol, mode, cfg)
                    out += [f"  {n} {w:<9} pair {q['size']} {t_}" for n, w, t_ in steps]
                    continue
                tag = f"L{q['size']} " if r["per_size"] else ""
                sz = q["size"] if r["per_size"] else None
                key, head = (r["instrument"], sz), []
                if q["estimate"] is not None:
                    head = [("1-4", "SAME", f"as under {traced[key]}")] if key in traced else trace(m, res, r, sz)
                    traced.setdefault(key, c)
                steps = head + read_steps(q, r, lv, text, dcol, mode, cfg)
                out += [f"  {n} {w:<9} {tag}{t}" for n, w, t in steps]
            if r["per_size"]:
                top, agree, pref = (cols[dcol]["combine"].get(k) for k in ("top_only", "agree", "prefer_door"))
                out.append(f"  7 CODE      combine.rank {' > '.join(cols[dcol]['combine']['rank'])} (first wins)"
                           + (f"; {', '.join(top)} counts only when the largest size reads it" if top else "")
                           + (f"; only the items read on door value {pref} combine when there is one" if pref else "")
                           + (f"; {', '.join(agree)} count only when every item reads them, else {cols[dcol]['combine']['disagree']}" if agree else "") + " -> "
                           f"{shown(codes[c], None, mode, cfg)}")
        for d in chain(c):
            a, b = cols[d]["from"]
            ln = map_line(text, d, f"{codes[a]},{codes[b]}")
            out.append(f"  7 CODE      {d} = {shown(codes[d], None, mode, cfg)} from {a} {codes[a]} and {b} {codes[b]}"
                       + f"  (codes.toml line {ln})" * bool(ln))
    out += conventional_lines(res, pt, mode, cfg)
    row = T.verdict["row"][T.lines.index(sig["row_line"])]
    out.append(f"8 VERDICT   verdict.toml line {sig['row_line']}: "
               + "; ".join(f"when.{k} = [{', '.join(v)}]" for k, v in row["when"].items()))
    out += verdict_lines(sig, mode, cfg, pad="            ")
    import family   # plan 0872 F3: lazy (family imports view)
    note = family.note_lines(family.end_notes(ROOT, res), pt, "")
    names = ["GEOMETRY", *["PROBE"] * ("probe" in T.axes), "ORDER", "COMPOSE"]
    for num, name in ((str(9 + i), n) for i, n in enumerate(names)) if "geometry" in sig else ():
        tab, lines = T.axes[name.lower()]
        row = tab["row"][lines.index(sig["axis_lines"][name.lower()])]
        got = row["verdict"].replace("@geometry", f"{sig['geometry']} (the geometry)") if name in ("COMPOSE", "PROBE") else row["verdict"]
        out.append(f"{num:<3}{name:<8}  {name.lower()}.toml line {sig['axis_lines'][name.lower()]}: "
                   + "; ".join(f"when.{k} = [{', '.join(v)}]" for k, v in row["when"].items()) + f"  => {got}")
    return out + note


def f2_code_line(text):
    """Line number of the `code =` map inside [f2] of a family.toml (0 when absent)."""
    head = ""
    for i, ln in enumerate(text.splitlines()):
        head = ln if ln.startswith("[") else head
        if head.startswith("[f2]") and ln.startswith("code ="):
            return i + 1
    return 0


def stored(res, instrument, pair):
    """The vectors an instrument reported for one pair, name -> value, read from the stored result (nothing is re-measured)."""
    pre = f"{instrument}/"
    return {q["name"]: q["estimate"] for q in res["reports"] if q["vector_key"].startswith(pre) and q["vector_key"].endswith(f"/pair={pair}")}


def pair_section(res, r, pair, mode, cfg, T, m, text, code_map):
    """One instrument's numbered trace of one control pair: membership door, the stored vectors, the kernel steps its own
    declared operators run, the interval against eps, the cell, the family's code. Every number is the stored one."""
    a, b = pair.split("->")
    sig, rule = {s["point"]: s for s in res["signature"]}, T.membership.get(r["instrument"])   # plan 0872: across_delta has no membership rule
    out = [f"{r['instrument']}   (pair {pair})"]
    if rule:
        got = [(pt, sig[pt][rule["reads"]], rule["map"][sig[pt][rule["reads"]]]) for pt in (a, b)]
        mem = door.member(T.membership, r["instrument"], (a, b), sig)
        out.append(f"  1 MEMBER    membership.toml [{r['instrument']}] reads {rule['reads']}: "
                   + ", ".join(f"{p} {c} -> {x}" for p, c, x in got) + f"; lowest rank decides -> door {mem['door']}"
                   + (f"   flags: {words(r['flags'], cfg)}" if r["flags"] else ""))
    if r["estimate"] is None:
        return out + [f"  2 READING   {shown(r['cell'], r['reason'], mode, cfg)}"]
    vec, e, lv = stored(res, r["instrument"], pair), r["eps"], res["interval"]
    ops = tomllib.loads((ROOT / "instruments" / f"{r['instrument']}.toml").read_text())["operators"]
    delta = vec.pop("delta", None)
    if delta is not None:
        sizes = ", ".join(f"{s} {d:.4g}" for s, d in zip(m["axes"]["size"], delta))
        out.append(f"  2 DELTA     A over the control edge {a}->{b}, row 0: {sizes}")
    if delta is not None and "B" in ops:   # the instrument declares B: A over the size chain, then B at the top edge, is its own reading
        ctx, ln = detect.context_for(res["input"], r["instrument"], None), np.log(np.abs(delta))
        steps = np.diff(ln)
        lab = cfg["step_labels"]
        out.append(f"  3 {lab['operator'][lab['size']]:<9} ln|Delta| {nums(ln)}; A over size {nums(steps)}; B at the top edge {steps.sum():.4g}; "
                   f"over the log span {ctx.log_span:.4g}: {steps.sum() / ctx.log_span:.4g}")
    elif vec:
        out.append("  3 REPORTED  " + "; ".join(f"{k} {nums(v) if isinstance(v, list) else f'{v:.4g}'}" for k, v in vec.items()))
    bl, bu = (int(v) for v in sign.position(r["lo"], r["hi"], e))
    code = code_map.get(r["cell"])
    return out + [
        f"  4 READING   {r['column']} {r['estimate']:.4g}  interval [{r['lo']:.4g}, {r['hi']:.4g}]  "
        f"({door.COVERAGE[lv['method']](lv) * 100:g} %, {cfg['interval_fields'][lv['method']]['read_pair'].format(**lv)})",
        f"  5 SIGN      cuts {-e:g} 0 +{e:g} (eps {r['eps_key']}): bL {bl}, bU {bu} -> {shown(r['cell'], None, mode, cfg)}",
        "  6 CODE      " + (f"family.toml line {f2_code_line(text)} [f2.code]: {r['cell']} -> {code}" if code else
                            "no family code for this cell in this set (a family's [f2.code] codes a pair)")]


def explain_pair(res, pair, mode, tables_dir=None):
    """The numbered trace of one control pair (a label `a->b`): one section per instrument that reads the pair, each from its
    own stored vectors. Read from the stored result; nothing is re-measured."""
    bad = stale(res)
    if bad:
        return bad.splitlines()
    cfg, T, m = config(), detect.load_tables(res["tables"], tables_dir), detect.load_input(res["input"])
    a, b = pair.split("->")
    fam = T.paths[0].parent / "family.toml"
    text = fam.read_text() if fam.is_file() else ""
    code_map = tomllib.loads(text).get("f2", {}).get("code", {}) if text else {}
    out = [f"explain {res['input']} {pair}   rules: {res['tables']}"]
    for r in (q for q in res["pair_readings"] if q["unit"]["pair"] == [a, b]):
        out += pair_section(res, r, pair, mode, cfg, T, m, text, code_map)
    return out
