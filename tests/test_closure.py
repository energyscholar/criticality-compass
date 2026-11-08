"""test_closure - the measurement closure is DECLARED (checks.toml [closure.measure]) and its membership COMPUTED (plan 0886).
Prints the closure's file list (the entries plus every instrument module); asserts that no file declared `outside` is in it and that
cc/schema.py is. Prints, as information, how many stored v03 results are keyed to the current closure (a stale one is re-measured by
`bin/cc run --all --tables v03-rules`)."""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import schema  # noqa: E402


decl = tomllib.loads((ROOT / "checks.toml").read_text())["closure"]["measure"]
instruments = sorted(f"cc/instruments/{p.name}" for p in (ROOT / "cc" / "instruments").glob("*.py"))
closure = schema.import_closure(ROOT, decl["entries"] + instruments)
print(f"measurement closure: {len(closure)} files")
for f in sorted(closure):
    print(f"  {f}")
check("no file declared outside the measurement closure is in it", not (set(decl["outside"]) & set(closure)), str(sorted(set(decl["outside"]) & set(closure))))
check("cc/schema.py is in the closure", "cc/schema.py" in closure)
keyed = total = 0
for q in sorted((ROOT / "results").glob("*@v03-rules.json")):
    res = json.loads(q.read_text())
    mods = [tomllib.loads((ROOT / "instruments" / f"{n}.toml").read_text())["module"]
            for n in tomllib.loads((ROOT / "inputs" / res["input"] / "m.toml").read_text())["instruments"]]
    total += 1
    keyed += res.get("measure_hash") == schema.measure_hash(ROOT, mods)
# plan 0894 P5 (E371): docs/gen-verdicts.py has a declared role (plumbing) and its output IS docs/VERDICTS.md, byte for byte (VERDICTS.md is generated, never edited)
import subprocess  # noqa: E402
roles = tomllib.loads((ROOT / "checks.toml").read_text())["roles"]
check("docs/gen-verdicts.py is declared in checks.toml (plumbing)", "docs/gen-verdicts.py" in roles["plumbing"], str(sorted(r for rs in roles.values() for r in rs if "docs" in r)))
gen = subprocess.run([sys.executable, "docs/gen-verdicts.py", ".", "v08-rules", "90", "compact"], capture_output=True, text=True, cwd=ROOT)   # the invocation VERDICTS.md records
check("docs/gen-verdicts.py v08-rules 90 compact reproduces docs/VERDICTS.md byte for byte", gen.returncode == 0 and gen.stdout == (ROOT / "docs" / "VERDICTS.md").read_text(), gen.stderr[-200:])
print(f"stored v03 results keyed to the current closure: {keyed} of {total}")
print("test_closure: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
