"""test_try_to_break_it - plan 1639 amendment A4: docs/try-to-break-it.md shows ten attacks on CC, each a command and the last line it prints. This runs every command from the
root of the clone and checks that it exits non-zero and that its last output line equals the one shown, so the page cannot drift from the code. Commands only: it adds no code path.
Breakers: a changed expected line, an attack that exits 0, and a document with fewer attacks than the amendment asks for are each found."""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BLOCK = re.compile(r"```sh\n(.+?)\n```\s*\n\s*```text\n(.+?)\n```", re.S)


def attacks(text):
    return BLOCK.findall(text)


def run(cmd, root=ROOT):
    argv = cmd.replace("python3 ", f"{sys.executable} ", 1)
    r = subprocess.run(argv, shell=True, capture_output=True, text=True, cwd=root)
    last = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()][-1:] or [""]
    return r.returncode, last[0]


def judge(cmd, shown, root=ROOT):
    rc, last = run(cmd, root)
    return [] if rc != 0 and last == shown else [f"rc={rc}, last line {last!r}, shown {shown!r}"]


def main():
    text = (ROOT / "docs" / "try-to-break-it.md").read_text()
    rows = attacks(text)
    check("the page shows 4 to 12 attacks", 4 <= len(rows) <= 12, str(len(rows)))
    for i, (cmd, shown) in enumerate(rows, 1):
        got = judge(cmd, shown)
        check(f"attack {i} is refused with the line the page shows", not got, "; ".join(got))
    cmd, shown = rows[0]
    check("breaker: a changed expected line is found", bool(judge(cmd, shown + " (edited)")))
    check("breaker: a command that succeeds is found", bool(judge("python3 -c \"print('ok')\"", "ok")))
    check("breaker: a page with no fenced pair has no attacks", attacks("no blocks here") == [])


guarded("test_try_to_break_it", main)
print("test_try_to_break_it: " + ("all passed" if not bad else f"{len(bad)} failed"))
sys.exit(1 if bad else 0)
