"""test_registry - plan 1016: the registry gate (cc/registry.py, the ONE reader of registry.toml). Five tests of the draft (s3) and the table cells of Argus rulings R1-R3.
Each runs in a scratch copy of cc/, instruments/, cc.toml and a fixture registry.toml, in a subprocess, so no module of the live tree is imported or mutated.
  1. an unregistered id refuses: a built-not-registered row reads Refuse "mechanism not yet available", imports no module, and the run gate refuses before any reuse or measurement
  2. a registered-partial id carries its scope into the report lines
  3. a tampered registry.toml fails the pin: every unit reads Refuse "registry pin mismatch", and validate reports it with a Next line
  4. one reader: importlib.import_module / __import__ is called in cc/registry.py only
  5. a live id is unique: two non-superseded rows for one id fail the projection (and the reader)"""
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def py(root, code):
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path[:0] = [sys.argv[1] + '/cc']\n" + code, str(root)], capture_output=True, text=True, cwd=root)
    return r.stdout + r.stderr


def sha(path):
    sys.path.insert(0, str(ROOT / "cc"))
    import registry
    return registry.sha256_of(path)


def fixture(tmp, edit=lambda s: s):
    """A scratch root: the code, the instrument files, cc.toml and registry.toml with `edit` applied to its text and cc.toml's pin re-set to the edited file (a byte flip skips the re-pin)."""
    root = Path(tmp) / "repo"
    root.mkdir()
    for d in ("cc", "instruments"):
        shutil.copytree(ROOT / d, root / d, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "inputs" / "x8-ising-needle").mkdir(parents=True)
    shutil.copyfile(ROOT / "inputs" / "x8-ising-needle" / "m.toml", root / "inputs" / "x8-ising-needle" / "m.toml")
    (root / "registry.toml").write_text(edit((ROOT / "registry.toml").read_text()))
    for f in ("cc.toml", "checks.toml"):
        (root / f).write_text((ROOT / f).read_text())
    return root


def repin(root):
    t = (root / "cc.toml").read_text()
    (root / "cc.toml").write_text(re.sub(r'(?m)^(\[registry\]\nsha256 = ")[0-9a-f]{64}', lambda m: m.group(1) + sha(root / "registry.toml"), t))


def row_edit(rid, **kv):
    def edit(text):
        out, hit = [], False
        for blk in re.split(r"(?=\n\[\[row\]\]\n)", text):
            if f'\nid = "{rid}"\n' in blk:
                hit = True
                for k, v in kv.items():
                    blk = re.sub(rf'(?m)^{k} = ".*"$', f'{k} = "{v}"', blk)
            out.append(blk)
        assert hit, rid
        return "".join(out)
    return edit


# ---- the shipped pin and table
cfg = tomllib.loads((ROOT / "cc.toml").read_text())
check("the shipped registry.toml hashes to the pin in cc.toml [registry]", sha(ROOT / "registry.toml") == cfg["registry"]["sha256"], sha(ROOT / "registry.toml"))
proj = tomllib.loads((ROOT / "registry.toml").read_text())
check("the projection holds no gated_by or note, and no row names a field outside id/status/scope/release_module",
      all(set(r) == {"id", "status", "scope", "release_module"} for r in proj["row"]), str(proj["row"][0]))

# ---- 1. an unregistered id refuses
with tempfile.TemporaryDirectory() as t:
    root = fixture(t, row_edit("D-needle", status="built-not-registered"))
    repin(root)
    out = py(root, """
import registry, detect
e = registry.lookup("instrument.needle", "truth", sys.argv[1])
d, mod = detect.instrument("needle")
print(type(e).__name__, getattr(e, "reason", None))
print("module", mod, "imported", "needle" in sys.modules)
def boom(*a, **k): raise SystemExit("REUSED OR MEASURED")
detect.stored = boom; detect.measure = boom; detect.read_hashes = boom
try:
    detect.run_keyed("x8-ising-needle", "v01-rules", False)
except detect.Refused as r:
    print("REFUSED", str(r).splitlines()[0])
print("needle in sys.modules:", "needle" in sys.modules)
""")
    check("1. an unregistered id (built-not-registered) reads Refuse 'mechanism not yet available'", "Refuse mechanism not yet available" in out, out[-300:])
    check("1. a Refuse holds no module: instrument() gives None and the needle module is not imported", "module None imported False" in out and "needle in sys.modules: False" in out, out[-300:])
    check("1. the run gate refuses before any reuse or measurement (stored, measure, read_hashes never called)",
          "REFUSED instrument.needle is refused by the registry: mechanism not yet available" in out and "REUSED OR MEASURED" not in out, out[-300:])
    check("1. the gate wrote no result", not (root / "results").exists(), str(list(root.iterdir())))

# ---- the table cells (R1-R3, draft s5.2)
with tempfile.TemporaryDirectory() as t:
    root = fixture(t, lambda s: s)
    out = py(root, """
import registry
look = lambda u, o: registry.lookup(u, o, sys.argv[1])
print("dev", type(look("instrument.across", "observed")).__name__, look("instrument.across", "observed").scope)
print("chains", look("interval.chains", "truth").scope)
print("noid", registry.lookup("instrument.nope", "truth", sys.argv[1]) == registry.REFUSE_UNAVAILABLE)
""")
    check("a development row is RunScoped('development: not registered') on every obtained value", "dev RunScoped ('development: not registered',)" in out, out)
    check("chains is RunScoped with the readout-equivalence scope (ruling 4)", "release readout; equivalence to the T18 module not yet shown" in out, out)
    check("a unit with no registry row reads the default Refuse value", "noid True" in out, out)
    for st, mod, obt, want in (("registered-synthetic-only", "cc/instruments/across.py", "observed", "Refuse"), ("registered-synthetic-only", "cc/instruments/across.py", "truth", "RunScoped"),
                               ("registered", "", "truth", "Refuse"), ("registered", "cc/instruments/across.py", "observed", "Run")):
        with tempfile.TemporaryDirectory() as t2:
            r2 = fixture(t2, row_edit("D-across", status=st, release_module=mod))
            repin(r2)
            o = py(r2, f"import registry\nprint(type(registry.lookup('instrument.across', '{obt}', sys.argv[1])).__name__)")
            check(f"table cell ({st}, {obt}, {'module' if mod else 'no module'}) is {want}", o.strip() == want, o)
    with tempfile.TemporaryDirectory() as t3:
        r2 = fixture(t3, row_edit("D-across", status="bogus"))
        repin(r2)
        o = py(r2, "import registry\nprint(registry.lookup('instrument.needle', 'truth', sys.argv[1]))")
    check("an unknown status makes EVERY unit a Refuse value ('registry projection invalid: unknown status bogus')", "registry projection invalid: unknown status bogus" in o, o)

# ---- 2. registered-partial carries its scope
with tempfile.TemporaryDirectory() as t:
    src = ('[[structure]]\nid = "D-across"\nstatus = "registered-partial"\nrelease_module = "cc/instruments/across.py"\nawaiting = ["T4-components"]\n'
           'gated_by = "an operator name that must never reach the projection"\nnote = "a free note"\n')
    out = py(ROOT, f"""
import registry
print(registry.project({src!r}, "b" * 40, "c" * 40))""")
    check("2. the projection of a row carries awaiting as its scope and drops gated_by and note", 'scope = "T4-components"' in out and "operator name" not in out and "free note" not in out, out)
    root = fixture(t, row_edit("D-across", status="registered-partial", scope="T4-components"))
    repin(root)
    out = py(root, """
import registry
e = registry.lookup("instrument.across", "truth", sys.argv[1])
print(type(e).__name__, e.scope)
print("\\n".join(registry.scope_lines(["instrument.across", "instrument.needle"], sys.argv[1])))
""")
    check("2. a registered-partial row is RunScoped and its scope string is in the report lines", "RunScoped ('T4-components',)" in out and "scope: T4-components — across" in out, out)
res = json.loads((ROOT / "results" / "b7-at-line-2@v03-rules.json").read_text())
sys.path.insert(0, str(ROOT / "cc"))
import view  # noqa: E402
import registry  # noqa: E402
lines = registry.scope_lines(view.units_of(res), ROOT)
check("2. a stored result's report carries the registry pin and the scope of every unit it used, from the current projection",
      lines[0].startswith("registry: sha256 ") and any(l.startswith("scope: development: not registered — ") and "across" in l and "interval.block" not in l and "block" in l for l in lines), str(lines))

# ---- 3. a tampered copy fails the pin
with tempfile.TemporaryDirectory() as t:
    root = fixture(t)
    text = (root / "registry.toml").read_text()
    (root / "registry.toml").write_text(text.replace('source_blob = "', 'source_blob = "0', 1))   # one byte (the id space is untouched, so only the pin can object)
    out = py(root, """
import registry, declare
from pathlib import Path
print({type(registry.lookup(u, o, sys.argv[1])).__name__ + ":" + registry.lookup(u, o, sys.argv[1]).reason for u in ("instrument.needle", "family", "interval.chains") for o in ("truth", "any")})
for f in declare.check_file(Path(sys.argv[1]) / "cc.toml", sys.argv[1]):
    print(declare.fmt(f))
""")
    check("3. one flipped byte: every unit reads Refuse 'registry pin mismatch'", "{'Refuse:registry pin mismatch'}" in out, out[-400:])
    check("3. validate reports the mismatch with a Next line", "registry.sha256" in out and "does not hash to its pin" in out and "Next: bin/cc registry pull" in out, out[-600:])

# ---- 4. one reader
calls = []
for f in [*sorted((ROOT / "cc").rglob("*.py")), ROOT / "bin" / "cc"]:
    for n in ast.walk(ast.parse(f.read_text())):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", None)) in ("import_module", "__import__"):
            calls.append(f"{f.relative_to(ROOT)}:{n.lineno}")
check("4. importlib.import_module / __import__ is called in cc/registry.py only", len(calls) == 1 and calls[0].startswith("cc/registry.py:"), str(calls))
check("4. detect.instrument loads through the registry (no module name is imported by detect.py)", "registry.lookup" in (ROOT / "cc" / "detect.py").read_text() and "importlib" not in (ROOT / "cc" / "detect.py").read_text(), "")

# ---- 5. a live id is unique
reg_text = '[[structure]]\nid = "T7"\nstatus = "superseded"\n[[structure]]\nid = "T7"\nstatus = "registered"\n'
check("5. one superseded and one live row of an id project", "T7" in registry.project(reg_text, "a" * 40, "b" * 40), "")
try:
    registry.project(reg_text.replace("superseded", "registered-partial"), "a" * 40, "b" * 40)
    check("5. two live rows of one id fail the projection", False, "no error")
except ValueError as e:
    check("5. two live rows of one id fail the projection", "two live rows for id T7" in str(e), str(e))
with tempfile.TemporaryDirectory() as t:
    root = fixture(t, lambda s: s + '\n[[row]]\nid = "D-family"\nstatus = "development"\nscope = "x"\nrelease_module = "cc/family.py"\n')
    repin(root)
    out = py(root, "import registry\nprint(registry.lookup('family', 'truth', sys.argv[1]))")
    check("5. a projection with two live rows of one id reads Refuse for every unit", "two live rows for id D-family" in out, out)

print(f"test_registry: {len(bad)} failed" if bad else "test_registry: all passed")
sys.exit(1 if bad else 0)
