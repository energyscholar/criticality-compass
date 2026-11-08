"""test_positional_1427 - plan 1427 D22: a positional word that equals the DEFAULT table set is still a positional when no flag gave that set.
bin/cc family <default-set-name> and bin/cc reverdict <default-set-name> --tables X see the word as the id (they refuse it as an unknown id), they do not print the usage line."""
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
default = tomllib.loads((ROOT / "cc.toml").read_text())["defaults"]["tables"]
other = sorted(p.name for p in (ROOT / "tables").iterdir() if p.is_dir() and p.name != default)[0]


def cc(*args):
    r = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), *args], capture_output=True, text=True, cwd=ROOT)
    return r.stdout + r.stderr


from lib import bad, check  # noqa: E402


for label, args in (("family", ("family", default)), ("reverdict", ("reverdict", default, "--tables", other))):
    out = cc(*args)
    check(f"{label} <default-set-name>: the word is the id, not the usage line", f"'{default}'" in out and not out.startswith("usage:"), out[:120])
print("test_positional_1427: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
