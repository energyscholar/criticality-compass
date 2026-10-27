"""test_hook_env_typed - a finding's TYPE says what it is evidence about (plan 1273): content (schema.F, true of the files on any host) or
host.NotEvaluableHere (this host lacks a resource the check needs). With the data root unset (the clone's own data/, which holds only the
in-repo `local` data), validate yields NotEvaluableHere(data_root) at every data-path check of an input and NO content finding there (T1); the
toolset, found as the data root's parent, is NotEvaluableHere(toolset) for each toolset pin. A content defect still yields content with the data
root absent: the environment type never hides content (T2). Seen RED on 272c843 (no cc/host.py; a data-path check was a content finding)."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
os.environ.pop("CC_DATA_ROOT", None)   # the data root unset: resolve_data_root falls to the clone's data/
import declare  # noqa: E402
import host  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


INPUT = "w2-potts"   # its data live under the data root (w2/...), not in the repo's local data
m = declare.load(ROOT / "inputs" / INPUT / "m.toml")[0]
nblocks = len(m["data"]["files"])
found = declare.validate(ROOT, INPUT)[0]
at_path = [f for f in found if f.loc.startswith(f"inputs/{INPUT}/m.toml:data.files[") and f.loc.endswith(".path")]
check("T1 the data root unset: the probe says the data root is Absent", isinstance(host.probe(declare.Ctx(ROOT))[0], host.Absent), str(host.probe(declare.Ctx(ROOT))))
check(f"T1 every data-path check of {INPUT} ({nblocks} blocks) is NotEvaluableHere(data_root)",
      len(at_path) == nblocks and all(type(f) is host.NotEvaluableHere and f.resource == "data_root" for f in at_path), str(at_path[:3]))
check("T1 zero content findings at the data-path checks", not [f for f in found if type(f) is declare.F and ".path" in f.loc], str([f for f in found if type(f) is declare.F][:3]))
check("T1 the input has no content finding at all here (only the host is missing)", [f for f in found if type(f) is declare.F] == [], str([f for f in found if type(f) is declare.F][:3]))
pins = [f for f in found if f.loc.startswith(f"inputs/{INPUT}/transducer.toml:transducer.update[")]
check("T1 each toolset pin is NotEvaluableHere(toolset), never 'is in no commit'", pins and all(type(f) is host.NotEvaluableHere and f.resource == "toolset" for f in pins), str(pins[:2]))
check("T1 the Next line says: commit from a host with the resource", all(f.nxt.startswith(f"commit from a host with {f.resource}") for f in at_path + pins), str((at_path + pins)[:1]))
check("T1 fmt prints it with its location and a Next line", declare.fmt(at_path[0]).startswith(at_path[0].loc + ": not evaluable here: ") and "\n  Next: " in declare.fmt(at_path[0]), declare.fmt(at_path[0]) if at_path else "")

with tempfile.TemporaryDirectory() as t:
    empty = Path(t) / "data"
    empty.mkdir()
    text = (ROOT / "inputs" / INPUT / "m.toml").read_text()
    f1 = Path(t) / "unknown-instrument" / "m.toml"
    f1.parent.mkdir()
    f1.write_text(text.replace('instruments = ["', 'instruments = ["no-such-instrument", "', 1))
    got = declare.check_file(f1, ROOT, data_root=str(empty))
    content = [f for f in got if type(f) is declare.F]
    check("T2 an unknown instrument is a CONTENT finding with the data root absent", any("'no-such-instrument' is not in the instrument registry" in f.msg for f in content), str(got[:3]))
    check("T2 ... and it is not NotEvaluableHere", not any(type(f) is host.NotEvaluableHere and "no-such-instrument" in f.msg for f in got), str(got[:3]))
    f2 = Path(t) / "bad-point" / "m.toml"
    f2.parent.mkdir()
    first = m["data"]["files"][0]["point"]
    f2.write_text(text.replace(f'point = "{first}"', 'point = "no-such-point"', 1))
    got = declare.check_file(f2, ROOT, data_root=str(empty))
    content = [f for f in got if type(f) is declare.F]
    check("T2 a block's point outside axes.point is CONTENT beside the NotEvaluableHere data-path checks",
          any("data.files[0].point" in f.loc for f in content) and any(type(f) is host.NotEvaluableHere for f in got), str(got[:4]))
    held = Path(t) / "held"
    (held / "w2").mkdir(parents=True)   # a data root that holds data (an entry besides the local ones) but not this file: the missing file is CONTENT
    got = declare.check_file(ROOT / "inputs" / INPUT / "m.toml", ROOT, data_root=str(held))
    check("T2 a HELD data root that lacks a declared file: the miss is content ('does not exist under the data root'), not NotEvaluableHere",
          any(type(f) is declare.F and "does not exist under the data root" in f.msg for f in got) and not any(f.resource == "data_root" for f in got if type(f) is host.NotEvaluableHere), str(got[:3]))
print("test_hook_env_typed: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
