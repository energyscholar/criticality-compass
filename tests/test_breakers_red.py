"""test_breakers_red - every breaker's own mutation must turn test_breakers RED with that breaker's BROKEN line."""
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad, files = [], sorted((ROOT / "tests" / "breakers").glob("*.toml"))
for f in files:
    b = tomllib.loads(f.read_text())
    m = b["mutation"]
    cmd = [str(ROOT / "bin" / "cc"), "mutate", m["file"], "--py", m["py"], "--", "test_breakers"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    red, own = "RED   test_breakers" in r.stdout, f"BROKEN {b['id']}" in r.stdout
    note = "" if red and own else f" (red {red}, own line {own}): {r.stdout[-300:]}"
    print(("ok   " if red and own else "FAIL ") + f"{b['id']}: its mutation turns it red" + note)
    if not (red and own):
        bad.append(b["id"])
print("".join(f"FAILED {x}\n" for x in bad) + "test_breakers_red: " + ("FAILED" if bad or not files else "all passed"))
sys.exit(1 if bad or not files else 0)
