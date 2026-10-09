"""test_kernel_identity_key - a tripwire for plan 0929 blocker (d). Today NO production file imports kernel_rs (measurement runs the Python kernel.py only),
so a result's reuse key (measure_hash + read) needs no kernel identity. The day any file of cc/ or bin/cc imports kernel_rs, a Rust and a Python result
would share one key unless the kernel identity enters it: this test then FAILS, and its message says what to do (it is the declaration that must change,
not this test: put the kernel identity into schema.measure_hash / detect.keyed AND the result header, then name the importer in KNOWN below)."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWN = set()   # production files allowed to import kernel_rs, once the kernel identity is in the reuse key
files = [*sorted((ROOT / "cc").rglob("*.py")), ROOT / "bin" / "cc"]
hits = []
for f in files:
    for n in ast.walk(ast.parse(f.read_text())):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
        if any(m.split(".")[0] == "kernel_rs" for m in mods) and str(f.relative_to(ROOT)) not in KNOWN:
            hits.append(f"{f.relative_to(ROOT)}:{n.lineno}")
print("test_kernel_identity_key: " + (f"FAIL {hits} import kernel_rs, but the kernel identity is not in the reuse key.\n  Next: add it to measure_hash/keyed and the result header, then list the file in KNOWN" if hits
                                      else f"ok, {len(files)} production files, none imports kernel_rs"))
sys.exit(1 if hits else 0)
