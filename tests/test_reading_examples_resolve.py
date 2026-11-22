"""test_reading_examples_resolve - plan 1639 amendment A2: every `file:line` that docs/READING-THE-CODE.md, AGENTS.md and the "Why CC uses relational math" section of
KERNEL-IN-CC.md and the top of README.md name resolves at head. A visible `path:N` or `path:N-M` must have a row `ref path:N = keyword` in the comment at the end of READING-THE-CODE.md, the file must
exist, the lines must lie inside it and hold the keyword. A moved line fails here, by name. Breakers: a shifted reference, a missing row and a missing file are each found."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REF = re.compile(r"(?<![\w/.-])([A-Za-z][\w/.-]*\.(?:py|md)):(\d+)(?:-(\d+))?")
ROW = re.compile(r"(?m)^ref (\S+?):(\d+(?:-\d+)?) = (.+)$")


def visible(text):
    return text.split("<!-- refs")[0]


def problems(visible_text, sidecar_text, root=ROOT):
    """-> what does not resolve: a visible ref with no row, a missing file, lines outside it, a keyword that is not on the lines."""
    rows = {f"{p}:{n}": kw for p, n, kw in ROW.findall(sidecar_text)}
    out = []
    for m in REF.finditer(visible_text):
        key = f"{m.group(1)}:{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
        if key not in rows:
            out.append(f"{key}: no ref row")
    for key, kw in rows.items():
        path, span = key.rsplit(":", 1)
        lo, _, hi = span.partition("-")
        lo, hi = int(lo), int(hi or lo)
        f = Path(root) / path
        if not f.is_file():
            out.append(f"{key}: no such file")
            continue
        lines = f.read_text().splitlines()
        if not (1 <= lo <= hi <= len(lines)):
            out.append(f"{key}: lines outside the file ({len(lines)} lines)")
        elif kw not in "\n".join(lines[lo - 1:hi]):
            out.append(f"{key}: `{kw}` is not on those lines")
    return out


def main():
    reading = (ROOT / "docs" / "READING-THE-CODE.md").read_text()
    agents = (ROOT / "AGENTS.md").read_text()
    kern = (ROOT / "KERNEL-IN-CC.md").read_text()
    sec = kern[kern.index("## Why CC uses relational math"):kern.index("## Kernel V8 on one page")]
    side = reading.split("<!-- refs")[1]
    readme = (ROOT / "README.md").read_text().split("## Run a system by hand")[0]   # phase 5c: the claim near the top of the README
    text = visible(reading) + "\n" + agents + "\n" + sec + "\n" + readme
    n = len(REF.findall(text))
    check("there are references to resolve", n >= 20, f"{n}")
    got = problems(text, side)
    check("every file:line of READING-THE-CODE.md, AGENTS.md and the KERNEL-IN-CC.md section resolves at head, on its keyword", not got, "; ".join(got))
    rows = ROW.findall(side)
    p0, n0, k0 = rows[0]
    check("breaker: a reference shifted by one line is found", bool(problems(f"`{p0}:{int(n0.split('-')[0]) + 1}`", f"ref {p0}:{int(n0.split('-')[0]) + 1} = {k0}")))
    check("breaker: a reference with no row is found", bool(problems("`cc/admit.py:39`", "")))
    check("breaker: a missing file is found", bool(problems("`cc/nope.py:1`", "ref cc/nope.py:1 = x")))
    check("breaker: a line beyond the file is found", bool(problems("`cc/admit.py:99999`", "ref cc/admit.py:99999 = x")))
    check("breaker: a true reference is not flagged", not problems("`cc/admit.py:39`", "ref cc/admit.py:39 = cycle"))


guarded("test_reading_examples_resolve", main)
print("test_reading_examples_resolve: " + ("all passed" if not bad else f"{len(bad)} failed"))
sys.exit(1 if bad else 0)
