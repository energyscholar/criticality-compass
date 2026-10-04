"""family.py - a family of points: bracket, f1 and f2 read from a STORED result, then one partition lookup (plumbing).
Reads results/<input>@<set>.json and .npz only; it never re-runs an instrument. Nulls are plumbing: an edge or a pair
that touches a null point reads that null, and only ranked codes go to the maths (cc/fingerprint.py)."""
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import admit
import declare
import detect
import door
import fingerprint
import readout
import view

ROOT = Path(__file__).resolve().parent.parent
SIDE_KEYS = declare.SIDE_KEYS


def low(xs, rank):
    """The lowest-ranked of the codes present (rank is a declared list, lowest first)."""
    return min(xs, key=rank.index)


def relation(kind, labels):
    """(declared relation, its (a, b) label pairs in edge order) over the family's labels, built by the door."""
    m = {"axes": {"p": list(labels)}, "relations": {"r": {"template": kind, "axis": "p", "provenance": "Continuation"}}}
    return door.relations_for(m, "r"), door.control_pairs(m, "r")


def bracket_of(fam, res, nulls):
    """(code, [(a, b, edge codes)]) over ALL points of the input in declared order, on the signature column `reads`.
    One code per declared edge axis (descent; plan 0871 E1 adds ascent), each combined over the edges, then one total table."""
    b, labels = fam["bracket"], [s["point"] for s in res["signature"]]
    codes = [s[b["reads"]] for s in res["signature"]]
    rel, pairs = relation("chain", labels)
    steps = fingerprint.code_steps(admit.nodefield([b["rank"].get(c, 0) for c in codes]), rel)   # a null point's rank is a placeholder
    ends = [[c for c in codes[k:k + 2] if c in nulls] for k in range(len(steps))]   # the null endpoints of each edge
    axes = declare.bracket_axes(b)
    edges = [[low(n, rank) if n else code[st] for _, code, rank in axes] for n, st in zip(ends, steps)]   # one code per axis
    mid = low([c if c in nulls else b["point_code"][c] for c in codes], b["mid_rank"])
    over = [low([e[i] for e in edges], axes[i][2]) for i in range(len(axes))]
    return b["table"][",".join([*over, mid])], [(*p, ",".join(e)) for p, e in zip(pairs, edges)]


def f1_of(fam, decl, res, z, m, nulls):
    """(code, [(a, b, text, code)]) over the interior points; NOT-MEASURED unless the input declares the instrument."""
    f, (inst, _, col) = fam["f1"], fam["f1"]["reads"].partition(".")
    if inst not in m["instruments"]:
        return "NOT-MEASURED", []
    rows = {r["unit"]["point"]: r for r in res["readings"] if (r["instrument"], r["column"]) == (inst, col)}
    pts = decl["interior"]
    zero = np.zeros(res["interval"]["resamples"] + 1)
    y = np.stack([z[rows[p]["vector_key"]] if rows[p]["vector_key"] else zero for p in pts], axis=1)   # [R+1, n]
    rel, pairs = relation("all-pairs", pts)
    diff, out = fingerprint.pair_differences(admit.nodefield(y), rel), []
    for e, (a, c) in enumerate(pairs):
        nul = [rows[p]["cell"] for p in (a, c) if rows[p]["cell"] in nulls]
        if nul:
            out.append((a, c, "a point reads null", low(nul, f["rank"])))
            continue
        est, lo, hi, cell = readout.reading(diff[:, e], res["interval"]["level"], m["eps"][f["eps"]])
        out.append((a, c, f"{est:+.3f} [{lo:+.3f}, {hi:+.3f}] {cell}", f["code"][cell]))
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
    """(code, detail) of one side of the declared interior (plan 0871 E2). The boundary is the interior point nearest the side; the
    beyond points are the points of axes.point on that side, nearest first. Beyond needles and beyond orders are each COMBINED by a declared
    rank whose last member (NONE) is read only when the side is empty; one total table then codes the side."""
    pts, e = [s["point"] for s in res["signature"]], fam["side"]
    sg, inner = {s["point"]: s for s in res["signature"]}, decl["interior"]
    boundary = inner[0] if which == "lower" else inner[-1]
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


def compute(decl, res, z, fam, text, m, nulls):
    """The family verdict from one stored result: one code per declared column (+ cells), then verdict, class, line, why.
    A set whose family.toml lists the column `points` also reads the interior's geometry and the two sides (plan 0871)."""
    out = {"bracket": bracket_of(fam, res, nulls), "f1": f1_of(fam, decl, res, z, m, nulls), "f2": f2_of(fam, decl, res, m, nulls)}
    side_lines = declare.row_lines(text, "side_row")
    if "points" in fam["columns"]:
        out["points"] = points_of(fam, decl, res)
        out |= {w: side_of(fam, decl, res, nulls, side_lines, w) for w in ("lower", "upper")}
    codes = {c: v[0] for c, v in out.items()}
    verdict, cls, line, why = detect.verdict_of(codes, SimpleNamespace(verdict=fam, lines=declare.row_lines(text)))
    ends = [out[w][1] for w in ("lower", "upper") if w in out and out[w][0] in fam["side"]["ends"]]   # plan 0871 E3: the sides that END a line
    named = {"end_point": [e["boundary"] for e in ends], "end_bracket": [[e["boundary"], e["beyond"][0]] for e in ends]} if "points" in out else {}
    return {**codes, **named, "cells": {c: v[1] for c, v in out.items()}, "verdict": verdict, "class": cls, "line": line, "why": why}


def run(root, fid, tables):
    """(refusal text, None) or (None, (decl, result dict, set name)): every refusal names its Next line."""
    root = Path(root)
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
    rid = f"{decl['input']}@{tables}"
    p = root / "results" / f"{rid}.json"
    if not p.is_file():
        return f"no result for {decl['input']} under {tables} yet.\n  Next: bin/cc run {decl['input']} --tables {tables}", None
    res = json.loads(p.read_text())
    if view.stale(res, root):
        return view.stale(res, root), None
    fam, nulls = tomllib.loads(ft.read_text()), declare.Ctx(root).alpha["nulls"]
    m = detect.load_input(decl["input"])
    with np.load(root / res["vectors"]) as z:
        return None, (decl, compute(decl, res, z, fam, ft.read_text(), m, nulls), tables)


def show(decl, out, tables):
    """The printed family: each fingerprint with its cells, then the verdict and the row's why."""
    c = out["cells"]
    lines = [f"family {decl['id']}   rules: {tables}   input: {decl['input']}   interior: {' '.join(decl['interior'])}",
             f"  bracket {out['bracket']}"] + [f"    edge {a}->{b} {e}" for a, b, e in c["bracket"]]
    lines += [f"  f1      {out['f1']}"] + [f"    {a}->{b} y_last {t}  -> {k}" for a, b, t, k in c["f1"]]
    lines += [f"  f2      {out['f2']}"] + [f"    {a}->{b} along {t}  -> {k}" for a, b, t, k in c["f2"]]
    lines += [x for k in ("points",) if k in c for x in [f"  points  {out['points']}"] + [f"    {pt} geometry {g}  -> {q}" for pt, g, q in c["points"]]]
    lines += [x for w in ("lower", "upper") if w in c for x in (
        f"  {w:<7} {out[w]}   boundary {c[w]['boundary']}, beyond {' '.join(c[w]['beyond']) or '(none)'}",
        f"    reads {', '.join(f'{k} {v}' for k, v in c[w]['key'].items())}  -> family.toml side_row line {c[w]['line']}",
        f"    why: {c[w]['why']}")]
    lines += [f"  end     {', '.join(f'{q} (bracket {a} .. {z})' for q, (a, z) in zip(out[k], out['end_bracket'])) or '(none)'}" for k in ("end_point",) if k in out]
    return lines + [f"  => family verdict {out['verdict']}   class {out['class']}, family.toml line {out['line']}",
                    f"     why: {out['why']}"]
