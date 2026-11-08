"""family.py - a family of points: bracket, f1 and f2 read from a STORED result, then one partition lookup (plumbing).
Reads results/<input>@<set>.json and .npz only; it never re-runs an instrument. Nulls are plumbing: an edge or a pair
that touches a null point reads that null, and only ranked codes go to the maths (cc/fingerprint.py)."""
import itertools
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import declare
import detect
import door
import fingerprint
import readout
import registry
import schema
import view

ROOT = Path(__file__).resolve().parent.parent
SIDE_KEYS = declare.SIDE_KEYS


def low(xs, rank):
    """The lowest-ranked of the codes present (rank is a declared list, lowest first)."""
    return min(xs, key=rank.index)


def bracket_of(fam, res, nulls):
    """(code, [(a, b, edge codes)]) over ALL points of the input in declared order, on the signature column `reads`.
    One code per declared edge axis (descent; plan 0871 E1 adds ascent), each combined over the edges, then one total table."""
    b, labels = fam["bracket"], [s["point"] for s in res["signature"]]
    codes = [s[b["reads"]] for s in res["signature"]]
    ij = fingerprint.chain_pairs(len(labels))   # plan 0892: the differences are computed inside C, over index pairs (an external verifier (ruling Q19))
    pairs = [(labels[i], labels[j]) for i, j in ij]
    steps = fingerprint.code_steps([b["rank"].get(c, 0) for c in codes], ij)   # a null point's rank is a placeholder
    ends = [[c for c in codes[k:k + 2] if c in nulls] for k in range(len(steps))]   # the null endpoints of each edge
    axes = declare.bracket_axes(b)
    edges = [[low(n, rank) if n else code[st] for _, code, rank in axes] for n, st in zip(ends, steps)]   # one code per axis
    mid = low([c if c in nulls else b["point_code"][c] for c in codes], b["mid_rank"])
    over = [low([e[i] for e in edges], axes[i][2]) for i in range(len(axes))]
    return b["table"][",".join([*over, mid])], [(*p, ",".join(e)) for p, e in zip(pairs, edges)]


def _f1_resampled(d, iv, eps):
    """Block and iid: the percentile interval of the resample rows (d[0] the estimate row) at the input's level."""
    est, lo, hi, cell = readout.reading(d, iv["level"], eps)
    return f"{est:+.3f} [{lo:+.3f}, {hi:+.3f}] {cell}", cell


def _f1_chains(d, iv, eps):
    """Plan 0978 R2: chain k's difference d_k = y_k(j) - y_k(i), rows 1..m (row 0 is a copy of chain 0 and is excluded by readout.chains): the order statistics
    [d_(r), d_(m+1-r)] of m iid values, T18-B. The estimand is median_k(d_k) (R5), not the difference of the two medians."""
    est, lo, hi, cell = readout.chains(d, iv["r"], eps)
    return f"{est:+.3f} [{lo:+.3f}, {hi:+.3f}] {cell}", cell


def _f1_gamma(d, iv, eps):
    """Plan 0978 R3: the linearised rows of method gamma are not replicates, so no per-row difference vector exists: a declared null, not an exception."""
    return "the linearised rows are not replicates: no per-row difference vector exists", "NOT-EVALUATED"


F1_READOUT = {"block": _f1_resampled, "iid": _f1_resampled, "gamma": _f1_gamma, "chains": _f1_chains}   # [interval] method -> f1's readout of one pair-difference column (plan 0978 R3); total over cc.toml alphabets.interval_method (tests/test_0978.py)


def f1_of(fam, decl, res, z, m, nulls):
    """(code, [(a, b, text, code)]) over the interior points; NOT-MEASURED unless the input declares the instrument."""
    f, (inst, _, col) = fam["f1"], fam["f1"]["reads"].partition(".")
    if inst not in m["instruments"]:
        return "NOT-MEASURED", []
    pair = detect.instrument(inst)[0]["unit"] == "pair"   # plan 0877: a pair instrument is read at the consecutive interior pairs (control edges), one unit per pair
    rows = {"->".join(r["unit"]["pair"]) if pair else r["unit"]["point"]: r for r in res["pair_readings" if pair else "readings"] if (r["instrument"], r["column"]) == (inst, col)}
    pts = ["->".join(u) for u in zip(decl["interior"], decl["interior"][1:])] if pair else decl["interior"]
    zero = np.zeros(max([len(z[r["vector_key"]]) for r in rows.values() if r["vector_key"]] + [1]))   # plan 0978 R5: the placeholder has the stored vectors' row count, whatever the interval method
    y = np.stack([z[rows[p]["vector_key"]] if rows[p]["vector_key"] else zero for p in pts], axis=1)   # [rows, n]
    ij = fingerprint.all_pairs(len(pts))
    pairs = [(pts[i], pts[j]) for i, j in ij]
    diff, out = fingerprint.pair_differences(y, ij), []
    codes = {**{n: n for n in nulls}, **f["code"]}   # a null cell is its own code (as f2_of)
    for e, (a, c) in enumerate(pairs):
        nul = [rows[p]["cell"] for p in (a, c) if rows[p]["cell"] in nulls]
        if nul:
            out.append((a, c, "a point reads null", low(nul, f["rank"])))
            continue
        text, cell = F1_READOUT[res["interval"]["method"]](diff[:, e], res["interval"], m["eps"][f["eps"]])
        out.append((a, c, text, codes[cell]))
    return low([o[3] for o in out], f["rank"]), out


def f2_of(fam, decl, res, m, nulls):
    """(code, [(a, b, cell, code)]) over the consecutive interior pairs; NOT-MEASURED unless the input declares the instrument."""
    f = fam["f2"]
    if f["reads"] not in m["instruments"]:
        return "NOT-MEASURED", []
    cell = {tuple(r["unit"]["pair"]): r["cell"] for r in res["pair_readings"] if r["instrument"] == f["reads"]}
    out = [(a, c, cell[(a, c)], cell[(a, c)] if cell[(a, c)] in nulls else f["code"][cell[(a, c)]])
           for a, c in zip(decl["interior"], decl["interior"][1:])]
    return low([o[3] for o in out], f["rank"]), out


def points_of(fam, decl, res):
    """(code, [(point, geometry, code)]): LINE only when EVERY interior point reads per-point LINE (the geometry after the probe)."""
    p, sg = fam["points"], {s["point"]: s for s in res["signature"]}
    cells = [(pt, sg[pt][p["reads"]], p["code"][sg[pt][p["reads"]]]) for pt in decl["interior"]]
    return low([c for *_, c in cells], p["rank"]), cells


def side_of(fam, decl, res, nulls, lines, which):
    """(code, detail) of one side of the declared interior (plan 0871 E2, G3). Walking outward from the interior's edge point, the boundary is
    the last point of the contiguous run that reads MID (the edge point itself when it does not); the beyond points are the points of
    axes.point past it, nearest first. Beyond needles and beyond orders are each COMBINED by a declared rank whose last member (NONE) is read
    only when the side is empty; one total table then codes the side. A MID that re-appears after a sink point stays in beyond: NO-END."""
    pts, e = [s["point"] for s in res["signature"]], fam["side"]
    sg, inner = {s["point"]: s for s in res["signature"]}, decl["interior"]
    edge = pts.index(inner[0] if which == "lower" else inner[-1])
    out = pts[:edge + 1][::-1] if which == "lower" else pts[edge:]          # the edge point, then outward
    run = list(itertools.takewhile(lambda q: e["needle_code"].get(sg[q]["needle"]) == "MID", out))
    boundary = (run or out[:1])[-1]
    k = pts.index(boundary)
    beyond = pts[:k][::-1] if which == "lower" else pts[k + 1:]
    yn = low([c if c in nulls else e["needle_code"][c] for c in (sg[q]["needle"] for q in beyond)] + ["NONE"], e["needle_rank"])
    yo = low([e["order_code"][f"{sg[q]['order']},{sg[q]['two_start']}"] for q in beyond] + ["NONE"], e["order_rank"])
    key = dict(zip(SIDE_KEYS, (sg[boundary]["needle"], sg[boundary]["flow"], yn, yo)))
    code, _, line, why = detect.verdict_of(key, SimpleNamespace(verdict={"row": fam["side_row"], "refuse": []}, lines=lines))
    return code, {"boundary": boundary, "beyond": beyond, "key": key, "line": line, "why": why}


def load_decl(root, fid):
    p = Path(root) / "families" / f"{fid}.toml"
    return tomllib.loads(p.read_text()) if p.is_file() else None


def interior_of(decl, res, fam, m):
    """(interior list, None) or (None, reason): the interior a declaration names. A list is returned as declared. The rule "mid-run-open" (plan 0879)
    reads ONLY the per-point `needle` code through the set's [side] needle_code: ONE maximal contiguous MID run in axes.point order; on each side the
    run's end point is dropped iff ANY point beyond the run reads SINK (a null beyond is not a sink). < 2 points left, no or several runs, a set
    with no [side] needle_code, or an interior pair that is not an edge of relations.control is a null: a reason, never a default cell."""
    if isinstance(decl["interior"], list):
        return decl["interior"], None
    code = fam.get("side", {}).get("needle_code")
    if code is None:
        return None, "its family.toml has no [side] needle_code to read the needle codes through"
    pts, sg = m["axes"]["point"], {s["point"]: s for s in res["signature"]}
    reads = [code.get(sg[q]["needle"]) for q in pts]
    runs = [list(g) for hit, g in itertools.groupby(range(len(pts)), key=lambda i: reads[i] == "MID") if hit]
    if len(runs) != 1:
        return None, f"interior rule found {len(runs)} runs of MID points, it needs exactly one"
    run = runs[0]
    keep = run[int("SINK" in reads[:run[0]]):len(run) - int("SINK" in reads[run[-1] + 1:])]
    if len(keep) < 2:
        return None, f"interior rule found {len(keep)} points (the MID run of {len(run)}, less the ends that a sink lies beyond), it needs at least 2"
    inner = [pts[i] for i in keep]
    edges = {tuple(e) for e in door.control_pairs(m)} if "control" in m.get("relations", {}) else None
    off = [f"{a}->{b}" for a, b in zip(inner, inner[1:]) if edges is not None and (a, b) not in edges]
    return (None, f"interior rule found {off[0]}, which is not an edge of relations.control") if off else (inner, None)


def compute(decl, res, z, fam, text, m, nulls):
    """The family verdict from one stored result: one code per declared column (+ cells), then verdict, class, line, why.
    A set whose family.toml lists the column `points` also reads the interior's geometry and the two sides (plan 0871).
    The interior is resolved FIRST through interior_of; a null there returns {"interior": None, "refusal": reason} and nothing else."""
    inner, why = interior_of(decl, res, fam, m)
    if inner is None:
        return {"interior": None, "refusal": why}
    decl = {**decl, "interior": inner, "rule": decl["interior"] if isinstance(decl["interior"], str) else None}
    out = {"bracket": bracket_of(fam, res, nulls), "f1": f1_of(fam, decl, res, z, m, nulls), "f2": f2_of(fam, decl, res, m, nulls)}
    side_lines = declare.row_lines(text, "side_row")
    if "points" in fam["columns"]:
        out["points"] = points_of(fam, decl, res)
        out |= {w: side_of(fam, decl, res, nulls, side_lines, w) for w in ("lower", "upper")}
    codes = {c: v[0] for c, v in out.items()}
    verdict, cls, line, why = detect.verdict_of(codes, SimpleNamespace(verdict=fam, lines=declare.row_lines(text)))
    sides = [(w, out[w][0], out[w][1]) for w in ("lower", "upper") if w in out and out[w][0] in fam["side"]["ends"]]   # plan 0871 E3: the sides that END a line
    ends = [e for _, _, e in sides]
    named = {"end_point": [e["boundary"] for e in ends], "end_bracket": [[e["boundary"], e["beyond"][0]] for e in ends],
             "ends": [{"point": e["boundary"], "side": w, "kind": k} for w, k, e in sides]} if "points" in out else {}   # plan 0872 F3: each end point, named with its side and kind
    return {**codes, **named, "interior": inner, "rule": decl["rule"], "cells": {c: v[1] for c, v in out.items()}, "verdict": verdict, "class": cls, "line": line, "why": why}


class Null(str):
    """A refusal that is a DECLARED NULL (the family reads NOT-EVALUATED), not an error: printed like any message, but it is not a failure (plan 0894 P3)."""


def run(root, fid, tables):
    """(refusal text, None) or (None, (decl, result dict, set name)): every refusal names its Next line."""
    root = Path(root)
    if isinstance(e := registry.lookup("family", registry.ANY, root), registry.Refuse):   # plan 1016: the gate, through the one reader
        return f"family {fid}: refused by the registry: {e.reason}\n  Next: bin/cc validate", None
    decl = load_decl(root, fid)
    names = " ".join(sorted(p.stem for p in (root / "families").glob("*.toml")))
    if decl is None:
        return f"no family '{fid}'. Families: {names}\n  Next: bin/cc family <one of these>   (or bin/cc new family {fid})", None
    found = declare.check_file(root / "families" / f"{fid}.toml", root)
    ft = root / "tables" / tables / "family.toml"
    if not ft.is_file():
        return (f"tables/{tables} has no family.toml, so it has no rule for family {fid}.\n"
                f"  Next: copy tables/v01-rules/family.toml into tables/{tables}/ (a family rule is table-set data)"), None
    found += declare.check_file(ft, root)
    if found:
        return "\n".join(declare.fmt(f) for f in found), None
    p = schema.result_path(root, decl['input'], tables)
    if not p.is_file():
        return f"no result for {decl['input']} under {tables} yet.\n  Next: bin/cc run {decl['input']} --tables {tables}", None
    res = json.loads(p.read_text())
    if view.stale(res, root):
        return view.stale(res, root), None
    fam, nulls = tomllib.loads(ft.read_text()), declare.Ctx(root).alpha["nulls"]
    m = detect.load_input(decl["input"])
    with np.load(root / res["vectors"]) as z:
        out = compute(decl, res, z, fam, ft.read_text(), m, nulls)
    if out["interior"] is None:
        return Null(f"family {fid} reads NOT-EVALUATED: {out['refusal']}.\n  Next: bin/cc show {decl['input']} --tables {tables} (the needle column), "
                    f"then declare the points the family covers, or measure more points"), None
    return None, (decl, out, tables)


def end_notes(root, res):
    """{point: [(family id, END-kind)]} for a STORED result: the end points of the families that read its input (plan 0872 F3). Empty when the set has
    no family rule with sides, the input has no family, or the result's vectors are not stored (a dry run): the note is read from the stored family, never invented."""
    root, notes = Path(root), {}
    ft = root / "tables" / res["tables"] / "family.toml"
    if not ft.is_file() or not (root / "families").is_dir() or not (root / res["vectors"]).is_file():
        return notes
    fam = tomllib.loads(ft.read_text())
    if "points" not in fam["columns"]:
        return notes
    nulls = declare.Ctx(root).alpha["nulls"]
    for f in sorted((root / "families").glob("*.toml")):
        decl = load_decl(root, f.stem)
        if decl["input"] == res["input"]:
            with np.load(root / res["vectors"]) as z:
                got = compute(decl, res, z, fam, ft.read_text(), detect.load_input(res["input"]), nulls)
            for e in got.get("ends", []):
                notes.setdefault(e["point"], []).append((decl["id"], e["kind"]))
    return notes


def note_lines(notes, pt, pad="  "):
    """The F3 line(s) under one point: it ends a LINE run of a family."""
    return [f"{pad}end of a LINE run (family {fid}, {kind})" for fid, kind in notes.get(pt, [])]


def show(decl, out, tables):
    """The printed family: each fingerprint with its cells, then the verdict and the row's why."""
    c = out["cells"]
    lines = [f"family {decl['id']}   rules: {tables}   input: {decl['input']}   interior: {' '.join(out['interior'])}{' (rule ' + out['rule'] + ')' if out['rule'] else ''}",
             f"  bracket {out['bracket']}"] + [f"    edge {a}->{b} {e}" for a, b, e in c["bracket"]]
    lines += [f"  f1      {out['f1']}"] + [f"    {a}->{b} y_last {t}  -> {k}" for a, b, t, k in c["f1"]]
    lines += [f"  f2      {out['f2']}"] + [f"    {a}->{b} along {t}  -> {k}" for a, b, t, k in c["f2"]]
    lines += [x for k in ("points",) if k in c for x in [f"  points  {out['points']}"] + [f"    {pt} geometry {g}  -> {q}" for pt, g, q in c["points"]]]
    lines += [x for w in ("lower", "upper") if w in c for x in (
        f"  {w:<7} {out[w]}   boundary {c[w]['boundary']}, beyond {' '.join(c[w]['beyond']) or '(none)'}",
        f"    reads {', '.join(f'{k} {v}' for k, v in c[w]['key'].items())}  -> family.toml side_row line {c[w]['line']}",
        f"    why: {c[w]['why']}")]
    lines += [f"  end     {', '.join(f'{q} (bracket {a} .. {z})' for q, (a, z) in zip(out[k], out['end_bracket'])) or '(none)'}" for k in ("end_point",) if k in out]
    lines += [f"    {e['point']}: end of a LINE run ({e['side']} side, {e['kind']})" for e in out.get("ends", [])]
    return lines + [f"  => family report {out['verdict']}   class {out['class']}, family.toml line {out['line']}",
                    f"     report: {registry.config(view.ROOT)['report']['family']}",
                    *[f"     {x}" for x in registry.scope_lines(["family"], view.ROOT)],   # plan 1016: the pinned registry and the family reader's scope   # plan 0892 (an external verifier (ruling Q19)): the declared label, cc.toml [report] family
                    f"     why: {out['why']}"]
