"""test_dispatch_keep - plan 1651 item 3 (F-R1): the sweep is the authority. `release/dispatch_rewrite.py` leaves the site of every KEEP row of release/dispatch-sweep.toml
stays a table (its keys, its key expression and whether it is called with arguments are unchanged; what sits in its arms is its own rows). Input: the BASE text (git show of the base commit) of each row's file; the site is the dict's call (or subscript) found at the row's `line` with the row's `text`.
A KEEP site the tool rewrote anyway is named file:line. The base commit must be in the clone: a clone without it FAILS with a Next line (never skips)."""
import ast
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "release"))
from lib import bad, check, guarded  # noqa: E402

import dispatch_rewrite as D  # noqa: E402

BASE = "209dda85f554ea91c2b31400b4343980d42b5a3f"   # the TREE of the plan-1639-dist tip 55eba02 this plan branched from (D0): a tree sha survives the public rewrite, a commit sha does not


def base_text(rel):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{rel}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"the base tree {BASE} is not in this clone: {r.stderr.strip()[:120]}\n  Next: fetch the plan-1639-dist history (git fetch), then rerun")
    return r.stdout


def tables_of(src):
    """{(keys, slice, called with arguments): count} of the bool-keyed dict tables of `src` that are indexed in place: what a KEEP site IS, whatever sits in its arms."""
    t = ast.parse(src)
    parent = {c: p for p in ast.walk(t) for c in ast.iter_child_nodes(p)}
    out = {}
    for n in ast.walk(t):
        if isinstance(n, ast.Dict) and n.keys and None not in n.keys:
            sub = parent.get(n)
            if isinstance(sub, ast.Subscript) and sub.value is n:
                call = parent.get(sub)
                k = (tuple(ast.unparse(x) for x in n.keys), ast.unparse(sub.slice), isinstance(call, ast.Call) and call.func is sub)
                out[k] = out.get(k, 0) + 1
    return out


def site_key(src, row):
    """The `tables_of` key of the KEEP row's site (the dict at the row's line with the row's text), or None when no unique indexed dict matches."""
    t = ast.parse(src)
    parent = {c: p for p in ast.walk(t) for c in ast.iter_child_nodes(p)}
    found = [n for n in ast.walk(t) if isinstance(n, ast.Dict) and n.lineno == row["line"] and ast.unparse(n)[:100] == row["text"]]
    sub = parent.get(found[0]) if len(found) == 1 else None
    if not (isinstance(sub, ast.Subscript) and sub.value is found[0]):
        return None
    call = parent.get(sub)
    return (tuple(ast.unparse(x) for x in found[0].keys), ast.unparse(sub.slice), isinstance(call, ast.Call) and call.func is sub)


def moved(rows, rewrite):
    """KEEP rows whose indexed table no longer stands in the rewritten base text (a site the tool rewrote). A row that is not an indexed table (a named table) is not a site of the rewriter."""
    out, cache = [], {}
    for r in rows:
        if r["ruling"] != "KEEP":
            continue
        rel = r["file"]
        if rel not in cache:
            src = base_text(rel)
            cache[rel] = (src, tables_of(rewrite(rel, src)[0]))
        src, now = cache[rel]
        k = site_key(src, r)
        if k is not None and now.get(k, 0) < 1:
            out.append(f"{rel}:{r['line']}")
    return out


def t13():
    rows = tomllib.loads((ROOT / "release" / "dispatch-sweep.toml").read_text())["row"]
    got = moved(rows, D.rewrite_source)
    check("T13 the rewriter leaves every KEEP site of the sweep unchanged", got == [], "; ".join(got[:8]) + f" ({len(got)})")
    check("T13 the sweep has KEEP rows to check", len([r for r in rows if r["ruling"] == "KEEP"]) > 100, "")
    probe = {"line": 1, "text": "{True: p.a, False: p.b}"}
    src = "{True: p.a, False: p.b}[k](1, 2)\n"
    check("T13 breaker: the site of a planted row is found in its source", site_key(src, probe) == (("True", "False"), "k", True), str(site_key(src, probe)))
    check("T13 breaker: the planted site, rewritten, is not found", site_key(src, probe) not in tables_of("(p.a if k else p.b)(1, 2)\n"), "")

guarded("T13", t13)
print("test_dispatch_keep: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
