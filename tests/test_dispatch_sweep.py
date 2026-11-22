"""test_dispatch_sweep - plan 1644 D5, T8: every bool-keyed dict site of cc/, bin/cc and manual/ is a row of release/dispatch-sweep.toml with a category and a ruling.
A new site, or a site whose category moved, is not a row: the file fails naming file:line. The table is the BASE sweep; at head every REWRITE row is gone and every KEEP row is still there."""
import collections
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "release"))
from lib import bad, check, guarded  # noqa: E402

import dispatch_rewrite as D  # noqa: E402

CATEGORIES = {"K-named-table", "K-inline-signature", "X-inline-partial-signature", "X-eager-arms", "X-other", "R-lazy-if", "R-pure-ternary"}


def table():
    return tomllib.loads((ROOT / "release" / "dispatch-sweep.toml").read_text())["row"]


def sig(r):
    return (r["file"], r["scope"], r["category"], r["ruling"])


def unlisted(root, rows):
    """Sites of `root` that are not rows: (file:line, why). A group may have fewer sites than the table (a REWRITE row rewritten), never more."""
    want = collections.Counter(sig(r) for r in rows)
    got = collections.Counter()
    out = []
    for r in D.sweep(root):
        got[sig(r)] += 1
        if got[sig(r)] > want[sig(r)]:
            out.append((f"{r['file']}:{r['line']}", f"no row for {sig(r)[1:]}"))
    return out


def t8():
    rows = table()
    check("T8 the table has a row per site of the base sweep (244)", len(rows) == 244, str(len(rows)))
    check("T8 every row has a known category and a ruling", all(r["category"] in CATEGORIES and r["ruling"] in ("KEEP", "REWRITE") and r["reason"] for r in rows), "")
    check("T8 every site of the tree is a row", unlisted(ROOT, rows) == [], str(unlisted(ROOT, rows)[:5]))
    check("T8 the sites of head that remain are KEEP rows (no REWRITE row stays)", all(r["ruling"] == "KEEP" for r in D.sweep(ROOT)), "")
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "cc").mkdir()
        (Path(d) / "cc" / "planted.py").write_text("x = 3\nd = {True: 1, False: 2}[x > 1]\n")
        (Path(d) / "checks.toml").write_text('[roles]\nmaths = []\n')
        got = unlisted(Path(d), rows)
        check("T8 breaker: a planted `{True: 1, False: 2}[x > 1]` is found, naming file:line", got and got[0][0] == "cc/planted.py:2", str(got))


guarded("T8", t8)
print("test_dispatch_sweep: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
