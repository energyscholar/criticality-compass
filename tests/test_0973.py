"""test_0973 - plan 0973: the structure-not-control cruft fixes (Fable #4 F1-F8). One section per phase; each section's mutation (its RED) is named in the commit message.
F8: a ValueError that is a defect (not a declared refusal) must propagate out of bin/cc run_one; only detect.Refused is refusal text."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import detect  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def load_cc():
    """bin/cc as a module (its last line is sys.exit(main(...)); the source without that line)."""
    ns = {"__name__": "cc_cli", "__file__": str(ROOT / "bin" / "cc")}
    exec(compile((ROOT / "bin" / "cc").read_text().rsplit("sys.exit(main", 1)[0], str(ROOT / "bin" / "cc"), "exec"), ns)
    return ns


# ---- F8
cli = load_cc()
cli["structure_gate"] = lambda: None
declare.validate = lambda root, name, tables: ([], None)
name = cli["inputs"]()[0]
real = detect.run_keyed
try:
    detect.run_keyed = lambda *a, **k: (_ for _ in ()).throw(ValueError("planted"))
    try:
        got = cli["run_one"](name, "v10-rules", True)
        check("F8 a planted ValueError propagates (is not refusal text)", False, f"returned as refusal {got[0]!r}")
    except ValueError as e:
        check("F8 a planted ValueError propagates (is not refusal text)", str(e) == "planted")
    detect.run_keyed = lambda *a, **k: (_ for _ in ()).throw(detect.refused("planted refusal", "nothing"))
    got = cli["run_one"](name, "v10-rules", True)
    check("F8 a declared refusal is still text with its Next line", got[1] is None and "planted refusal" in got[0] and "Next: nothing" in got[0], got)
finally:
    detect.run_keyed = real

sys.exit(1 if bad else 0)
