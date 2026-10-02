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


def low(xs, rank):
    """The lowest-ranked of the codes present (rank is a declared list, lowest first)."""
    return min(xs, key=rank.index)


def relation(kind, labels):
    """(declared relation, its (a, b) label pairs in edge order) over the family's labels, built by the door."""
    m = {"axes": {"p": list(labels)}, "relations": {"r": {"template": kind, "axis": "p", "provenance": "Continuation"}}}
    return door.relations_for(m, "r"), door.control_pairs(m, "r")


def bracket_of(fam, res, nulls):
    """(code, [(a, b, edge code)]) over ALL points of the input in declared order, on the signature column `reads`."""
    b, labels = fam["bracket"], [s["point"] for s in res["signature"]]
    codes = [s[b["reads"]] for s in res["signature"]]
    rel, pairs = relation("chain", labels)
    steps = fingerprint.code_steps(admit.nodefield([b["rank"].get(c, 0) for c in codes]), rel)   # a null point's rank is a placeholder
    ends = [[c for c in codes[k:k + 2] if c in nulls] for k in range(len(steps))]   # the null endpoints of each edge
    edges = [low(n, b["descent_rank"]) if n else b["edge_code"][st] for n, st in zip(ends, steps)]
    mid = low([c if c in nulls else b["point_code"][c] for c in codes], b["mid_rank"])
    return b["table"][f"{low(edges, b['descent_rank'])},{mid}"], [(*p, e) for p, e in zip(pairs, edges)]


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


def load_decl(root, fid):
    p = Path(root) / "families" / f"{fid}.toml"
    return tomllib.loads(p.read_text()) if p.is_file() else None


def compute(decl, res, z, fam, lines, m, nulls):
    """The family verdict from one stored result: {bracket, f1, f2, cells, verdict, class, line, why}."""
    bracket, be = bracket_of(fam, res, nulls)
    f1, c1 = f1_of(fam, decl, res, z, m, nulls)
    f2, c2 = f2_of(fam, decl, res, m, nulls)
    verdict, cls, line, why = detect.verdict_of({"bracket": bracket, "f1": f1, "f2": f2},
                                                SimpleNamespace(verdict=fam, lines=lines))
    return {"bracket": bracket, "f1": f1, "f2": f2, "cells": {"bracket": be, "f1": c1, "f2": c2},
            "verdict": verdict, "class": cls, "line": line, "why": why}


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
        return None, (decl, compute(decl, res, z, fam, declare.row_lines(ft.read_text()), m, nulls), tables)


def show(decl, out, tables):
    """The printed family: each fingerprint with its cells, then the verdict and the row's why."""
    c = out["cells"]
    lines = [f"family {decl['id']}   rules: {tables}   input: {decl['input']}   interior: {' '.join(decl['interior'])}",
             f"  bracket {out['bracket']}"] + [f"    edge {a}->{b} {e}" for a, b, e in c["bracket"]]
    lines += [f"  f1      {out['f1']}"] + [f"    {a}->{b} y_last {t}  -> {k}" for a, b, t, k in c["f1"]]
    lines += [f"  f2      {out['f2']}"] + [f"    {a}->{b} along {t}  -> {k}" for a, b, t, k in c["f2"]]
    return lines + [f"  => family verdict {out['verdict']}   class {out['class']}, family.toml line {out['line']}",
                    f"     why: {out['why']}"]
