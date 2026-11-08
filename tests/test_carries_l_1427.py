"""test_carries_l_1427 - plan 1427 D13: sampler.CARRIES_L holds a fact cc.toml does not (which formats carry L), so it stays a table; it must name exactly the formats cc.toml [alphabets] declares."""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import sampler  # noqa: E402

declared = set(tomllib.loads((ROOT / "cc.toml").read_text())["alphabets"]["formats"])
bad = sorted(declared ^ set(sampler.CARRIES_L))
print(("ok   " if not bad else "FAIL ") + "CARRIES_L names exactly cc.toml [alphabets] formats" + ("" if not bad else f": differ on {bad}"))
print("test_carries_l_1427: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
