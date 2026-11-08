"""test_conventional - the transform instrument's y_inf is printed WITH its declared label in show and explain, in both modes (plan 0881 P2.3,
an external verifier (ruling Q3)): "independent conventional estimate - not a Compass reading", one string in cc.toml [conventional]. The column stays printed
(the record); nothing prints it unlabelled; a result with no transform reading prints no such line."""
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


from lib import bad, check  # noqa: E402


def cc(*a):
    return subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), *a], capture_output=True, text=True).stdout


label = tomllib.loads((ROOT / "cc.toml").read_text())["conventional"]["transform"]
check("the declared words are exactly the ruling's", label == "independent conventional estimate — not a Compass reading", label)
for tabs in ("v06-rules", "v08-rules"):
    inp = "x2b-xy-2" if tabs == "v06-rules" else "x2b-xy-3"
    for flag in ([], ["--advanced"]):
        for name, args in (("show", ["show", inp]), ("explain", ["explain", inp, "0.5"])):
            out = cc(*args, "--tables", tabs, *flag).splitlines()
            ys = [ln for ln in out if "y_inf" in ln]
            check(f"{name} {inp}@{tabs} {' '.join(flag) or 'basic'}: y_inf is printed", bool(ys))
            check(f"{name} {inp}@{tabs} {' '.join(flag) or 'basic'}: every y_inf line carries the label", all(label in ln for ln in ys), str(ys[:1]))
plain = cc("show", "b7-at-line")
check("a result with no transform reading prints no y_inf line", "y_inf" not in plain and label not in plain)
print("test_conventional: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
