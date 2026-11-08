"""score.py - the ONLY reader of class_truth: tabulate, the collisions, --diff, the verdict-table page. Plumbing."""
import html
import tomllib
from pathlib import Path
import numpy as np
import declare
import detect
import family
import view
from reverdict import membership_of, reverdict_refusal, recode, reverdict_result   # noqa: F401  (plan 0876 B: they live where the measurement key can follow them)

ROOT = Path(__file__).resolve().parent.parent


def join(input_id, root=ROOT):
    """point -> case id from inputs/<id>/points.toml (None when the input has no join file)."""
    p = Path(root) / "inputs" / input_id / "points.toml"
    return tomllib.loads(p.read_text())["points"] if p.is_file() else None


def truths(root=ROOT):
    return {f.stem: declare.load_truth(f) for f in sorted((Path(root) / "cases").glob("*.toml"))}


def order_truths(root=ROOT):
    return {f.stem: declare.load_order_truth(f) for f in sorted((Path(root) / "cases").glob("*.toml"))}


def agreement(pairs):
    """{agree, refused, disagree} over (reading class, truth class) pairs; a reading class REFUSE is refused."""
    got = ["refused" if r == "REFUSE" else "agree" if r == t else "disagree" for r, t in pairs]
    return {k: got.count(k) for k in ("agree", "refused", "disagree")}


def axis_tallies(rows, T, tr, otr):
    """The per-axis agreement lines of one table set whose results carry geometry and order. Order is read against
    order_truth through the set's [score] map; geometry against class_truth, over the points whose order_truth is not
    FIRST-ORDER (a first-order point has no geometry class to be right about). Points with no case are not scored."""
    sc, g = T.axes["order"][0]["score"], T.axes.get("probe", T.axes["geometry"])[0]   # the geometry as the declared probe lets it stand
    cls = lambda v: "REFUSE" if v in g["refuse"] else g.get("class_of", {}).get(v, v)  # noqa: E731
    both = [(sig, case) for sig, case, _ in rows if case != "none" and case in tr]
    o = agreement([(sc[sig["order"]], otr[case]) for sig, case in both])
    ge = agreement([(cls(sig["geometry"]), tr[case]) for sig, case in both if otr[case] != "FIRST-ORDER"])
    return [f"Order against order_truth: " + ", ".join(f"{n} {k}" for k, n in o.items()),
            f"Geometry against class_truth (order_truth not FIRST-ORDER): " + ", ".join(f"{n} {k}" for k, n in ge.items())]


def end_scores(out, points, truth):
    """[(point, agree | refused | disagree)] for every point whose truth class is BKT-END (plan 0871 E3). An end read from a grid is a
    BRACKET, not a point: AGREE when the family reads BKT-END and the point lies inside one of its end_brackets (grid order, ends included);
    a family that refuses is refused (a miss, never an agreement); any other family class, or a BKT-END read that misses the point, disagrees."""
    pos = {p: i for i, p in enumerate(points)}
    inside = lambda p: any(min(pos[a], pos[b]) <= pos[p] <= max(pos[a], pos[b]) for a, b in out["end_bracket"])   # noqa: E731
    return [(p, "refused" if out["class"] == "REFUSE" else "agree" if out["class"] == "BKT-END" and inside(p) else "disagree")
            for p in points if truth.get(p) == "BKT-END"]


def family_ends(tset, inputs, tr, joins, root, findings):
    """The `## Family ends` section of one set: each family of this set that names an end and joins a BKT-END truth point, the family
    class read at that point. A family that cannot be read is a finding, never a silent skip. [] when no family has such a point."""
    got, tally, lines = [], {"agree": 0, "refused": 0, "disagree": 0}, []
    for f in sorted((Path(root) / "families").glob("*.toml")):
        decl = family.load_decl(root, f.stem)
        if decl and decl["input"] in inputs and (Path(root) / "tables" / tset / "family.toml").is_file():
            msg, ran = family.run(root, f.stem, tset)
            findings += [msg] * (ran is None)
            got += [ran] * (ran is not None and "end_bracket" in ran[1])
    for decl, out, _ in got:
        jn = (joins or {}).get(decl["input"]) or join(decl["input"], root) or {}
        res = end_scores(out, detect.load_input(decl["input"])["axes"]["point"], {p: tr.get(c) for p, c in jn.items()})
        lines += (res and [f"- `{decl['id']}`: family {out['verdict']} (class {out['class']}), end_point {out['end_point']}, end_bracket {out['end_bracket']}"]
                  + [f"  - point {p} (case `{jn[p]}`, truth BKT-END): {k}" for p, k in res]) or []
        for _, k in res:
            tally[k] += 1
    rep = f"report: {view.config()['report']['family']}"   # plan 0892 R5: the declared label, cc.toml [report] family
    return (["", f"## Family ends ({tset})", rep, ""] + lines
            + ["", "Family end against truth: " + ", ".join(f"{n} {k}" for k, n in tally.items()) + f"   ({rep})"]) * bool(lines)


def sizes_of(input_id, root):
    p = declare.input_path(root, input_id)
    return tomllib.loads(p.read_text())["axes"]["size"] if p.is_file() else []


def table_rows(res, tr, jn, root, findings):
    """One row per point: the case from the join, the truth from the case file (UNJOINED + a finding if unknown)."""
    rows = []
    for sig in res["signature"]:
        case = (jn or {}).get(sig["point"], "none")
        if case != "none" and case not in tr:
            findings.append(declare.fmt(declare.F(
                f"inputs/{res['input']}/points.toml:points.\"{sig['point']}\"", f"unknown case '{case}'",
                f'create it with bin/cc new case {case}, or map the point to an existing case or "none"')))
        rows.append((sig, case, tr.get(case, "none" if case == "none" else "UNJOINED")))
    return rows


def tabulate(results, root=ROOT, joins=None):
    """(SIGNATURE-TABLE.md text, findings): rows grouped by table set, then that set's collisions."""
    tr, findings, by = truths(root), [], {}
    for res in results:
        bad = view.stale(res, root)
        if bad:
            findings.append(bad)
        else:
            by.setdefault(res["tables"], []).append(res)
    out = ["# Signature table", "", "Written by `bin/cc tabulate`. Truth is joined here only (cc/score.py); "
           "no result file holds it.", ""]
    for tset, rs in sorted(by.items()):
        cols, groups, tally = rs[0]["signature_columns"], {}, {"agree": 0, "refused": 0, "disagree": 0, "no truth": 0}
        ax, scored = ["geometry", "order"] * ("geometry" in rs[0]["signature"][0]), []
        out += [f"## Rules: {tset}", f"report: {view.config()['report']['verdict']}", "", "| run | point | case | truth | sizes | " + " | ".join(cols) + " | verdict | class |"
                + "".join(f" {a} |" for a in ax), "|" + "---|" * (len(cols) + 7 + len(ax))]
        for res in sorted(rs, key=lambda r: r["run_id"]):
            jn = (joins or {}).get(res["input"]) or join(res["input"], root)
            for sig, case, truth in table_rows(res, tr, jn, root, findings):
                codes = [sig[c] + (f" ({''.join(sig['flags'][c])})" if sig["flags"].get(c) else "") for c in cols]
                out.append(f"| {res['run_id']} | {sig['point']} | `{case}` | {truth} | "
                           f"{' '.join(map(str, sizes_of(res['input'], root)))} | {' | '.join(codes)} | "
                           f"{sig['verdict']} | {sig['verdict_class']} |" + "".join(f" {sig[a]} |" for a in ax))
                scored.append((sig, case, truth))
                groups.setdefault(tuple(sig[c] for c in cols), {}).setdefault(truth, []).append(f"{res['input']}:{sig['point']}")
                kind = ("no truth" if truth in ("none", "UNJOINED") else "refused" if sig["verdict_class"] == "REFUSE"
                        else "agree" if sig["verdict_class"] == truth else "disagree")
                tally[kind] += 1
        out += ["", f"Verdict class against truth: " + ", ".join(f"{n} {k}" for k, n in tally.items())]
        out += axis_tallies(scored, detect.load_tables(tset), tr, order_truths(root)) if ax else []
        out += ["", f"## Collisions ({tset})", ""]
        clash = [(k, g) for k, g in groups.items() if len({t for t in g if t not in ("none", "UNJOINED")}) > 1]
        out += [f"- `{', '.join(f'{c}={v}' for c, v in zip(cols, k))}`: "
                + " vs ".join(f"{t} ({', '.join(p)})" for t, p in sorted(g.items()) if t not in ("none", "UNJOINED"))
                for k, g in clash] or ["none"]
        out += family_ends(tset, {r["input"] for r in rs}, tr, joins, root, findings)
        out.append("")
    return "\n".join(out) + "\n", findings


# ------------------------------------------------------------------ the MVT gate (clauses of catalogue/check.py)
DECOYS = (("POINT", "LINE"), ("FIRST-ORDER", "LINE"), ("FIRST-ORDER", "WALKING"))


def mvt(root=ROOT):
    """[(clause, passed, detail)]: the five MVT clauses over the imported cases, against CC's SIGNATURE-TABLE.md."""
    cs = {f.stem: tomllib.loads(f.read_text()) for f in sorted((Path(root) / "cases").glob("*.toml"))}
    tab = {k: c for k, c in cs.items() if c["status"] == "in-signature-table"}
    rep = []
    for cls in ("POINT", "LINE", "WALKING"):
        ids = sorted(k for k, c in tab.items() if c["class_truth"] == cls)
        mech = {tab[k]["mechanism"] for k in ids}
        rep.append((f"1 {cls}: >= 2 in-table cases with different mechanisms", len(mech) >= 2,
                    f"{len(ids)} case(s) {ids}, {len(mech)} distinct mechanism(s)"))
    for ct, dec in DECOYS:
        ids = sorted(k for k, c in tab.items() if c["class_truth"] == ct and c["decoy_of"] == dec)
        rep.append((f"2 decoy: a {ct} case imitating {dec}", bool(ids), f"{ids}"))
    bkt = sorted(k for k, c in tab.items() if c["class_truth"] == "BKT-END" and c.get("breaker_verdict"))
    rep.append(("3 BKT breaker run, pre-registered verdict scored", bool(bkt), f"{bkt}"))
    blind = sorted(k for k, c in cs.items() if c.get("blind_seal") and (Path(root) / c["blind_seal"]).is_file())
    rep.append(("4 >= 1 held-out case declared blind and run", bool(blind), f"{blind}"))
    t = (Path(root) / "SIGNATURE-TABLE.md").read_text() if (Path(root) / "SIGNATURE-TABLE.md").is_file() else ""
    miss = sorted(k for k in tab if f"`{k}`" not in t)
    coll = any(ln.startswith("## Collisions") for ln in t.splitlines())
    rep.append(("5 signature table enumerated over every in-table case, collisions listed",
                bool(tab) and coll and not miss,
                f"{len(tab)} in-table case(s); collisions section {'present' if coll else 'ABSENT'}; missing {miss}"))
    return rep


# ------------------------------------------------------------------ the partition as an array
def owners(T):
    """(columns, domains, owner): the index of the verdict row that holds every cell of the signature domain."""
    cols = T.verdict["columns"]
    dom = [declare.doms(T.codes, T.codes["null_rank"])[c] for c in cols]
    owner = np.full([len(d) for d in dom], -1)
    for k, row in enumerate(T.verdict["row"]):
        owner[np.ix_(*[[dom[i].index(v) for v in row["when"].get(c, dom[i])] for i, c in enumerate(cols)])] = k
    return cols, dom, owner


def verdict_cells(T, owner):
    return np.array([r["verdict"] for r in T.verdict["row"]])[owner]


def reverdict(res, pt, T):
    """The verdict one stored point would get under table set T (its stored sign cells, no data read)."""
    return detect.verdict_of(detect.signature_from_cells(view.cells_of(res, pt), T), T)[0]


def diff(ta, tb, ra=(), rb=()):
    """(lines, changed cells, changed fixture points): every cell whose verdict differs, as compressed patterns."""
    (cols, dom, oa), (cols_b, dom_b, ob) = owners(ta), owners(tb)
    da, db = dict(zip(cols, dom)), dict(zip(cols_b, dom_b))
    if any(da[c] != db[c] for c in da.keys() & db.keys()):
        return [f"{ta.name} and {tb.name} have different alphabets for a shared signature column: no cell diff"], 0, []
    cols, dom = list(dict.fromkeys(cols_b + cols)), [{**da, **db}[c] for c in dict.fromkeys(cols_b + cols)]   # a column one set lacks: its verdicts hold along it
    va, vb = np.broadcast_arrays(*(declare.lifted(verdict_cells(t, o), c, cols, dict(zip(cols, dom))) for t, o, c in ((ta, oa, list(da)), (tb, ob, list(db)))))
    lines, total = [], int((va != vb).sum())
    for a, b in sorted({(x, y) for x, y in zip(va[va != vb], vb[va != vb])}):
        free = (va == a) & (vb == b)
        boxes = declare.patterns(free, cols, dom)
        lines.append(f"{a} -> {b}: {int(free.sum())} cells in {len(boxes)} patterns")
        lines += ["  " + "; ".join(f"when.{c} = {v}".replace("'", '"') for c, v in box) for box in boxes[:20]]
    other = {r["run_id"].split("@")[0]: r for r in rb}
    moved = []
    for res in ra:
        new = other.get(res["input"])
        for sig in res["signature"]:
            nv = {s["point"]: s["verdict"] for s in new["signature"]}[sig["point"]] if new else reverdict(res, sig["point"], tb)
            moved += [(res["input"], sig["point"], sig["verdict"], nv)] * (nv != sig["verdict"])
    return ([f"{total} cells change verdict between {ta.name} and {tb.name}"] + lines
            + [f"{len(moved)} fixture points change verdict"] + [f"  {i}:{p}  {a} -> {b}" for i, p, a, b in moved], total, moved)


# ------------------------------------------------------------------ docs/verdict-table.html
CSS = ("body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:70rem;padding:1rem 16px;background:#fff;color:#1a1a1a}"
       "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #8884;padding:.25rem .5rem;text-align:left;"
       "vertical-align:top}code{font-size:13px}.never{opacity:.7}"
       "@media(prefers-color-scheme:dark){body{background:#16181c;color:#e6e6e6}}")


def page(results, tables_dir=None, diffs=()):
    """One static page: per table set, the verdict rows grouped by class with their cell counts and the points that hit them."""
    by, order = {}, declare.Ctx(ROOT).alpha["class_truth"] + ["REFUSE"]
    for res in results:
        by.setdefault(res["tables"], []).append(res)
    out = [f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Verdict table</title><style>{CSS}</style><h1>Verdict table</h1>"]
    for tset, rs in sorted(by.items()):
        T = detect.load_tables(tset, tables_dir)
        _, _, owner = owners(T)
        hits = {}
        for res in rs:
            for sig in res["signature"]:
                hits.setdefault(sig["row_line"], []).append(f"{res['input']}:{sig['point']}")
        rows = [(r, T.lines[k], int((owner == k).sum())) for k, r in enumerate(T.verdict["row"])]
        assert sum(n for _, _, n in rows) == owner.size, "the rows of a table must cover its domain exactly once"
        cls = lambda v: "REFUSE" if v in T.verdict["refuse"] else T.verdict.get("class_of", {}).get(v, v)  # noqa: E731
        out.append(f"<h2>Rules: {html.escape(tset)} ({owner.size} cells)</h2>")
        for c in sorted({cls(r["verdict"]) for r, _, _ in rows}, key=lambda c: order.index(c) if c in order else 99):
            out += [f"<h3>{html.escape(c)}</h3><table><tr><th>when<th>verdict<th>why<th>line<th>cells<th>hit by"]
            for r, line, n in (x for x in rows if cls(x[0]["verdict"]) == c):
                when = "; ".join(f"{k} = {', '.join(v)}" for k, v in r["when"].items())
                out.append(f"<tr data-cells=\"{n}\"><td><code>{html.escape(when)}</code><td>{html.escape(r['verdict'])}"
                           f"<td>{html.escape(r['why'])}<td>{line}<td>{n}<td>{html.escape(' '.join(hits.get(line, [])))}")
            out.append("</table>")
        out += ["<h3>Rows never hit by any result</h3><ul>"] + [
            f"<li class=never>line {line}: {html.escape(r['verdict'])}" for r, line, _ in rows if line not in hits] + ["</ul>"]
    for d in diffs:
        out += ["<h2>Diff</h2><pre>" + html.escape("\n".join(d)) + "</pre>"]
    return "\n".join(out) + "\n"
