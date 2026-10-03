"""test_classify - cc.toml [golden.classes] partitions the changed lines of a regolden (plan 0869 P3):
each kind of change lands in its declared class, and a planted VERDICT change lands in (e) OTHER."""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402

classes = tomllib.loads((ROOT / "cc.toml").read_text())["golden"]["classes"]
bad = []


def check(name, got, want):
    print(("ok   " if got == want else "FAIL ") + f"{name}: {got}" + ("" if got == want else f" (wanted {want})"))
    if got != want:
        bad.append(name)


def kinds(name, old, new):
    return [k for k, _ in declare.classify_changes(classes, name, old, new)]


show = (ROOT / "tests/golden/show-b7.basic.txt").read_text()
planted = show.replace("REFUSE-NEEDLE-UNMEASURED", "NOT", 1)
check("a planted verdict change is (e) OTHER (RED)", kinds("show-b7.basic.txt", show, planted), ["e", "e"])
check("the same planted change in a help transcript is (e)", kinds("help.basic.txt", show, planted), ["e", "e"])
help_ = (ROOT / "tests/golden/help.advanced.txt").read_text()
check("a new help line is (a)", kinds("help.advanced.txt", help_, help_ + "  bin/cc newcmd  does a thing\n"), ["a"])
check("a count is (b)", kinds("tables-drop.basic.txt", "dropped tables/s and 38 result files\n", "dropped tables/s and 2 result files\n"), ["b", "b"])
check("a code commit is (c)", kinds("show-b7.advanced.txt", "  code_commit: aaaa\n", "  code_commit: bbbb\n"), ["c", "c"])
check("a frozen flag is (d)", kinds("run-frozen.basic.txt", "b7   rules: x   result: r (not frozen)\n", "b7   rules: x   result: r (frozen)\n"), ["d", "d"])
check("an unchanged transcript has no changed line", kinds("show-b7.basic.txt", show, show), [])
print("test_classify: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
