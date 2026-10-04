"""The QUICK tier of `bin/cc check --quick`: the HEAVY CASES a test may read from storage instead of re-measuring.

The list is DATA (cc.toml [check.quick]): a per-case budget, and under each test stem the cases (inputs, or golden case
ids) with the seconds they took to re-measure. A case is heavy only when that figure is over the budget. Quick drops
nothing else: every test script still runs. Every dropped case is written to $CC_QUICK_LOG so `check` prints it."""
import json
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"test_run_all": ("inputs",), "test_golden": ("cases",), "test_needle_o_start": ("inputs",)}   # which kind of case each test can drop


def declared(root=ROOT):
    return tomllib.loads((Path(root) / "cc.toml").read_text())["check"].get("quick", {})


def on():
    return os.environ.get("CC_QUICK") == "1"


def heavy(test, kind, root=ROOT):
    """{case: seconds} the test drops; empty unless this is a quick check."""
    return dict(declared(root).get(test, {}).get(kind, {})) if on() else {}


def note(test, kind, name, secs, root=ROOT):
    """Say what was dropped and why (stdout, and $CC_QUICK_LOG so `check` can print it whatever a test's tail holds)."""
    line = f"quick: dropped {test} {kind[:-1]} {name}: re-measure took {secs} s, over the {declared(root)['case_budget_s']} s case budget"
    if os.environ.get("CC_QUICK_LOG"):
        with open(os.environ["CC_QUICK_LOG"], "a") as f:
            f.write(line + "\n")
    print(line)


def findings(root=ROOT, q=None):
    """Every problem with [check.quick] (`q`, else the repo's own): a list of (field, message, next)."""
    root, out = Path(root), []
    q = declared(root) if q is None else q
    if not q:
        return out
    budget = q.get("case_budget_s")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool):
        return [("check.quick.case_budget_s", "must be a number of seconds", "set case_budget_s = 10")]
    stems = {Path(t).stem for t in tomllib.loads((root / "checks.toml").read_text())["roles"]["tests"]}
    have = {"inputs": {p.name for p in (root / "inputs").iterdir() if p.is_dir()},
            "cases": {c["id"] for c in tomllib.loads((root / "tests" / "golden" / "golden.toml").read_text())["case"]}}
    for test, body in sorted((k, v) for k, v in q.items() if k != "case_budget_s"):
        where = f"check.quick.{test}"
        if test not in stems or test not in KINDS or not isinstance(body, dict):
            out.append((where, f"'{test}' is not a test that can drop a heavy case ({', '.join(KINDS)})", "name one of those"))
            continue
        for kind, cases in sorted(body.items()):
            if kind not in KINDS[test] or not isinstance(cases, dict):
                out.append((f"{where}.{kind}", f"'{kind}' is not a case kind of {test} ({', '.join(KINDS[test])})",
                            "write a table of name = seconds"))
                continue
            for name, secs in sorted(cases.items()):
                if name not in have[kind]:
                    out.append((f"{where}.{kind}.{name}", f"'{name}' is not among the {kind} that exist", "remove it or fix its spelling"))
                elif not isinstance(secs, (int, float)) or isinstance(secs, bool) or secs <= budget:
                    out.append((f"{where}.{kind}.{name}", f"{secs!r} is not a re-measure time over the {budget} s budget",
                                "list only cases that are over the budget"))
    return out


def stored(root, name, tables):
    """(result, derived_from, problem) for input `name` under `tables`, from results/ alone: the stored result of that
    set, else a stored result of another set re-verdicted by cc/score.py from its sign cells. A stale or refused one
    is a problem (text), never a result: quick cannot read it, so the check fails and says why."""
    import detect
    import score
    import view
    root = Path(root)
    f = root / "results" / f"{name}@{tables}.json"
    other = sorted(root.joinpath("results").glob(f"{name}@*.json"))
    if not f.is_file() and not other:
        return None, None, f"no stored result of {name} in results/"
    res = json.loads((f if f.is_file() else other[0]).read_text())
    problem = view.stale(res)
    if problem or f.is_file():
        return (None, None, problem) if problem else (res, None, None)
    problem = score.reverdict_refusal(res, tables, root)
    if problem:
        return None, None, problem
    return score.reverdict_result(res, detect.load_tables(tables)), res["run_id"], None
