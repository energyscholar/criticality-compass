"""Plan 1561: one report over finished drift-ladder runs (contract/SCHEMA-1561.md section 5). It reads run directories and writes one
file; it makes no run. A directory name is a claim and the run's own config.json is the evidence: a run not made as its name says
is MISMATCH, never read into a ladder. A rung with no directory is MISSING, so a missing rung can never shorten a ladder into a
clean bracket."""
import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

from environment import drift_score as DS
from environment import drift_worlds as DW
from navigator.reader import Malformed

MODES = ("SET", "MID", "OFF")
# mode -> (the needle's shape, the needle steers, the needle settles): (needle_structure, "nudge" in ops, n_eq > 0)
NEEDLE = {"SET": ("hold-pair-v1", True, True), "MID": ("hold-pair-v1", True, False), "OFF": ("hold-pair-v1", False, True)}
_ABSENT = object()


def run_name(ladder, label, mode, seed):
    return f"{ladder}--{label}--{mode}--s{seed}"


def parse_name(name):
    """the inverse of run_name; None for any other name."""
    parts = name.split("--")
    ok = len(parts) == 4 and parts[2] in MODES and parts[3][:1] == "s" and parts[3][1:].isascii() and parts[3][1:].isdigit()
    return (parts[0], parts[1], parts[2], int(parts[3][1:])) if ok else None


def made_as(config, mode, rung, seed):
    """True when the run's own config says it was made as its name claims: the needle, the seed and every key the rung replaces."""
    needle, at = config["needle"], config["at"]
    made = (needle.get("needle_structure"), "nudge" in needle["ops"], needle["n_eq"] > 0)
    return (made == NEEDLE[mode] and at["seed"] == seed
            and all(at.get(k, _ABSENT) == v for k, v in rung.table.items()))


_UNREADABLE = (OSError, ValueError, KeyError, TypeError, IndexError)


def read_run(run_dir, mode, rung, seed):
    """-> (lock, motion | None, scorer | None). Only a run that was made as named, and finished, is evidence."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return "MISSING", None, None
    runs = sorted(p for p in (run_dir / "runs").glob("*") if p.is_dir())
    refused = any((p / "refused.json").exists() for p in runs)
    if len(runs) != 1 or refused:
        return ("REFUSED" if refused else "FAILED"), None, None
    d = runs[0]
    try:
        config = json.loads((d / "config.json").read_text())
        score = json.loads((d / "score.json").read_text())
        start = json.loads((d / "report.jsonl").read_text().splitlines()[0])
        if not made_as(config, mode, rung, seed):
            return "MISMATCH", None, None
        DS.rung_class(score["lock"])
        scorer = {"out_run": config["score"]["out_run"], "offset_K": config["score"]["offset_K"]}
        return score["lock"], DS.motion(score, start), scorer
    except _UNREADABLE:
        return "FAILED", None, None


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def read_perf(run_dir):
    """the run's perf.json totals {seconds, calls, by_op}, or a token: "no-perf" (no file), "unreadable-perf" (not that shape)."""
    run = next(p for p in sorted((Path(run_dir) / "runs").glob("*")) if p.is_dir())
    f = run / "perf.json"
    if not f.exists():
        return "no-perf"
    try:
        rows = [(c["op"], c["seconds"]) for c in json.loads(f.read_text())["calls"]]
    except (OSError, ValueError, KeyError, TypeError):
        return "unreadable-perf"
    if not all(isinstance(op, str) and _num(sec) for op, sec in rows):
        return "unreadable-perf"
    ops = sorted({op for op, _ in rows})
    return {"seconds": math.fsum(sec for _, sec in rows), "calls": len(rows),
            "by_op": {op: {"calls": sum(o == op for o, _ in rows), "seconds": math.fsum(sec for o, sec in rows if o == op)} for op in ops}}


def _cell(worlds, ladder, mode, seed, root):
    rungs = []
    for r in ladder.rungs:
        lock, motion, scorer = read_run(root / run_name(ladder.name, r.label, mode, seed), mode, r, seed)
        rungs.append({"label": r.label, "severity": r.severity, "lock": lock, "class": DS.rung_class(lock),
                      "motion": motion, "scorer": scorer,
                      "perf": None if motion is None else read_perf(root / run_name(ladder.name, r.label, mode, seed))})
    b = DS.breakpoint([(r["label"], r["class"]) for r in rungs])
    return {"ladder": ladder.name, "mode": mode, "seed": seed, "rungs": rungs,
            "break": {"kind": b.kind, "below": b.below, "above": b.above, "detail": list(b.detail)}}


def report(worlds, root):
    root = Path(root)
    declared = {(lad.name, r.label) for lad in worlds.ladders for r in lad.rungs}
    names = sorted(p.name for p in root.iterdir() if p.is_dir())
    parsed = {n: parse_name(n) for n in names}
    strays = [n for n in names if parsed[n] is None or parsed[n][:2] not in declared]
    seen = sorted({(p[0], p[2], p[3]) for n, p in parsed.items() if n not in strays})
    by_name = {lad.name: lad for lad in worlds.ladders}
    return {"schema": "compass-drift-ladders/1", "base": worlds.base,
            "cells": [_cell(worlds, by_name[name], mode, seed, root) for name, mode, seed in seen], "strays": strays}


def _refuse(why):
    print(f"refused: {why}", file=sys.stderr)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog="environment.ladder_report")
    ap.add_argument("--worlds", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        worlds = DW.parse_worlds(tomllib.loads(Path(a.worlds).read_text()))
    except (OSError, ValueError) as e:
        return _refuse(f"worlds: {e}")
    if isinstance(worlds, Malformed):
        return _refuse(f"worlds: field={worlds.field} {worlds.detail}")
    if not Path(a.root).is_dir():
        return _refuse(f"root: {a.root} is not a directory")
    Path(a.out).write_text(json.dumps(report(worlds, a.root), sort_keys=True, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
