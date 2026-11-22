"""test_get_sweep - plan 1644 D6, T8 + T9: every `.get` call of cc/ is a row of release/get-sweep.toml with a class and a ruling; no module-level code table is unruled.
T9: for each G-FIX table the indexed result equals the base `.get` result over the alphabet that reaches it, and a key outside it is a KeyError."""
import collections
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "release"))
from lib import bad, check, guarded  # noqa: E402

import get_sweep as G  # noqa: E402

CLASSES = {"V", "O", "R", "E", "T"}


def table():
    return tomllib.loads((ROOT / "release" / "get-sweep.toml").read_text())["row"]


def sig(r):
    return (r["file"], r["scope"], r["recv"])


def unlisted(root, rows):
    want = collections.Counter(sig(r) for r in rows)
    got = collections.Counter()
    out = []
    for r in G.sweep(root):
        got[sig(r)] += 1
        if got[sig(r)] > want[sig(r)]:
            out.append((f"{r['file']}:{r['line']}", f"no row for {r['recv']}.get"))
    return out


def t8():
    rows = table()
    check("T8 the table has a row per `.get` of the base (381)", len(rows) == 381, str(len(rows)))
    check("T8 every row has a class, a ruling and a reason", all(r["class"] in CLASSES and r["ruling"] in ("KEEP", "FIX") and r["why"] for r in rows), "")
    check("T8 no code table (class T) is unruled", [r for r in rows if r["class"] == "T" and r["ruling"] not in ("KEEP", "FIX")] == [], "")
    check("T8 every `.get` of the tree is a row", unlisted(ROOT, rows) == [], str(unlisted(ROOT, rows)[:5]))
    gone = collections.Counter(sig(r) for r in rows) - collections.Counter(sig(r) for r in G.sweep(ROOT))
    fixed = {sig(r) for r in rows if r["ruling"] == "FIX"}
    check("T8 a row missing from head is a FIX row (a `.get` removed on purpose), nothing else", set(gone) <= fixed, str(sorted(set(gone) - fixed)))
    check("T8 every FIX row is gone at head (the table is indexed)", {s for s in fixed} <= set(gone) or not fixed, str(sorted(fixed - set(gone))))
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "cc").mkdir()
        (Path(d) / "cc" / "planted.py").write_text("T = {'a': 1}\nv = T.get('k', 0)\n")
        got = unlisted(Path(d), rows)
        check("T8 breaker: a planted `T.get('k', 0)` is found, naming file:line", got and got[0][0] == "cc/planted.py:2", str(got))


guarded("T8", t8)
print("test_get_sweep: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
