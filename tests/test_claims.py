"""test_claims - plan 0932 P3: every evidence cell of CLAIMS.md resolves to an existing stored result with that sha256.
Cells read `root:path@<64 hex>`; root cc = this repository, root toolset = $CC_TOOLSET, else the parent of $CC_DATA_ROOT.
A5: a planted row whose hash names no stored result fails (seen red below); a wrong path fails; a malformed cell fails; a table row with no cell fails.
A toolset that is absent makes its cells UNCHECKED, printed loudly, never silently passed; CC_REQUIRE_TOOLSET=1 turns that into a failure."""
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CELL = re.compile(r"`([a-z]+):([^`\s]+)@([0-9a-f]{64})`")
ANYTICK = re.compile(r"`[a-z]+:[^`]*@[^`]*`")
STATUS = ("blind", "development", "provisional")


def toolset_root():
    given = os.environ.get("CC_TOOLSET") or (str(Path(os.environ["CC_DATA_ROOT"]).parent) if os.environ.get("CC_DATA_ROOT") else "")
    return Path(given or "/nonexistent-toolset")   # no toolset named: its cells are UNCHECKED, loudly


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_text(text, roots):
    """-> (problems, resolved, unchecked). One problem per bad cell / bad row."""
    problems, resolved, unchecked = [], 0, []
    for ln in text.splitlines():
        for tick in ANYTICK.findall(ln):
            if not CELL.fullmatch(tick):
                problems.append(f"malformed evidence cell {tick}")
        for root, path, want in CELL.findall(ln):
            base = roots.get(root)
            if base is None:
                problems.append(f"unknown root '{root}' in {root}:{path}")
            elif not base.is_dir():
                unchecked.append(f"{root}:{path}")
            elif not (base / path).is_file():
                problems.append(f"no stored result at {root}:{path}")
            elif sha(base / path) != want:
                problems.append(f"{root}:{path} hashes to {sha(base / path)[:16]}, CLAIMS.md says {want[:16]}")
            else:
                resolved += 1
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.startswith("| ") and len(cells) == 5 and cells[0] != "class":
            if cells[1] not in STATUS:
                problems.append(f"claims row '{cells[0]}' has status '{cells[1]}', outside {list(STATUS)}")
            if not CELL.search(cells[4]):
                problems.append(f"claims row '{cells[0]}' has no evidence cell")
    return problems, resolved, unchecked


from lib import bad, check  # noqa: E402


roots = {"cc": ROOT, "toolset": toolset_root()}
text = (ROOT / "CLAIMS.md").read_text()
probs, n, unchecked = check_text(text, roots)
check("every evidence cell of CLAIMS.md resolves to a stored result with that sha256", not probs, "; ".join(probs[:3]))
check("CLAIMS.md has evidence cells at all", n + len(unchecked) >= 10, f"{n + len(unchecked)}")
rows = [ln for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith("| class")]
check("the table covers all three statuses", {r.split("|")[2].strip() for r in rows} == set(STATUS), str({r.split('|')[2].strip() for r in rows}))
for lim in ("Detector intervals under-cover", "located, not identified", "T15 is synthetic-only", "no real-data confirmatory test", "row K4 -0.10", "development readings only", "are false positives"):
    check(f"known limit present: {lim}", lim.lower() in text.lower())
# plan 1012b: tonight's results are in, and the stale statements are gone
low = text.lower()
for stale in ("no input has yet been read under v10", "no real-input verdict under v10 yet", "27 contracts are drafted"):
    check(f"stale statement absent: {stale}", stale not in low)
for need in ("TAX-T6B-REAL-1.txt", "TAX-T7B-v4.txt", "NAV2-MAPS-N2-M5.txt", "NAV-M5-BAND-M160.txt", "0978-k4m1.txt", "0978-at-m1-rerun.txt", "L8-first-reading.txt"):
    check(f"CLAIMS cites {need}", need in text)

if unchecked:
    print(f"UNCHECKED: {len(unchecked)} toolset cells (no toolset at {roots['toolset']}); set CC_TOOLSET")
    check("toolset present when required (CC_REQUIRE_TOOLSET=1)", os.environ.get("CC_REQUIRE_TOOLSET") != "1", "toolset absent")

# A5 red: planted rows (a cc-side cell is always checkable)
cc_cell = next(m for m in CELL.finditer(text) if m.group(1) == "cc")
r, p, h = cc_cell.groups()


def plant(s, status="blind"):
    return f"| x | {status} | d | c | {s} |"


pr, _, _ = check_text(plant(f"`cc:{p}@{'0' * 64}`"), roots)
check("A5 RED: a planted row whose hash names no stored result fails, naming it", len(pr) == 1 and p in pr[0], str(pr))
pr, _, _ = check_text(plant(f"`cc:no/such/file.txt@{h}`"), roots)
check("A5 RED: a planted row naming a missing file fails", len(pr) == 1 and "no/such/file.txt" in pr[0], str(pr))
pr, _, _ = check_text(plant(f"`cc:{p}@{h}`"), roots)
check("A5 green: the same row with its true hash passes", pr == [], str(pr))
pr, _, _ = check_text(plant("none"), roots)
check("A5 RED: a row with no evidence cell fails", len(pr) == 1, str(pr))
pr, _, _ = check_text(plant(f"`cc:{p}@{h}`", "tested"), roots)
check("A5 RED: a status outside blind/development/provisional fails", any("status" in x for x in pr), str(pr))
pr, _, _ = check_text(plant("`cc:README.md@abc`"), roots)
check("A5 RED: a malformed cell fails", any("malformed" in x for x in pr), str(pr))

print("test_claims: " + ("FAIL " + str(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
