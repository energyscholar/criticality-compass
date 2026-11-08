"""test_transducer - the transducer file inputs/<id>/transducer.toml is REQUIRED for every input (plan 0883; prediction b): a scratch copy of the
repo with ONE transducer file deleted makes validate return exactly that finding (with its Next line); and a result written now pins the file."""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import declare  # noqa: E402


have = sorted(p.parent.name for p in (ROOT / "inputs").glob("*/m.toml"))
check("every input directory has a transducer file", all((ROOT / "inputs" / i / "transducer.toml").is_file() for i in have), "")
ok = [declare.fmt(f) for f in declare.check_file(ROOT / "tests" / "planted" / "transducer-ok.toml")]
check("the planted clean base transducer-ok.toml is clean", ok == [], str(ok))
with tempfile.TemporaryDirectory() as t:
    base = Path(t) / "repo"
    shutil.copytree(ROOT, base, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "rust", "tests"))
    victim = "x2b-xy-2"
    (base / "inputs" / victim / "transducer.toml").unlink()
    got = [declare.fmt(f) for f in declare.validate_scored(base)[0]]
    want = (f"inputs/{victim}/transducer.toml: missing\n  Next: copy inputs/TEMPLATE.transducer.toml.in to inputs/{victim}/transducer.toml and fill every TODO")
    check("validate with one transducer file deleted returns exactly that finding", got == [want], f"got {got}")
    scoped = [declare.fmt(f) for f in declare.validate(base, victim)[0]]
    check("the scoped validate of that input returns exactly that finding", scoped == [want], f"got {scoped}")
    check("the scoped validate of another input is clean", declare.validate(base, "x2b-xy-3")[0] == [], "")
print("test_transducer: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
