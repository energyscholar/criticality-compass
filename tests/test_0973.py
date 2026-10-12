"""test_0973 - plan 0973: the structure-not-control cruft fixes (Fable #4 F1-F8). One section per phase; each section's mutation (its RED) is named in the commit message.
F8: a ValueError that is a defect (not a declared refusal) must propagate out of bin/cc run_one; only detect.Refused is refusal text."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import tomllib  # noqa: E402
import numpy as np  # noqa: E402
import declare  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402

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

# ---- F1 + F3
alpha = set(tomllib.loads((ROOT / "cc.toml").read_text())["alphabets"]["interval_method"])
check("F1 READOUT, SIGN_DOOR and ROWS are total over alphabets.interval_method", set(detect.READOUT) == set(door.SIGN_DOOR) == set(detect.ROWS) == alpha, (set(detect.READOUT), alpha))
fifth = door.Ctx(level=0.95, eps={"c": 1.0}, rel={}, method="fifth", rank=1)
for what, call in (("readout", lambda: detect.READOUT[fifth.method]), ("sign door", lambda: door.SIGN_DOOR[fifth.method])):
    try:
        call()
        check(f"F1 a fifth method has no {what} (KeyError at declaration)", False, "resolved")
    except KeyError:
        check(f"F1 a fifth method has no {what} (KeyError at declaration)", True)
for meth in sorted(alpha):   # every declared method's Ctx resolves to ONE readout, with no None-ness in the choice
    check(f"F1 method {meth}: Ctx.method is the key", door.Ctx(level=0.95, eps={}, rel={}, method=meth).method == meth)
check("F3 INDICES is the resampling methods only (block, iid)", set(door.INDICES) == {"block", "iid"}, set(door.INDICES))
try:
    list(door.resample_plan({"interval": {"method": "jackknife", "seed": 1, "resamples": 2}}, [5]))
    check("F3 a method past validate is a KeyError, not an iid plan", False, "ran")
except KeyError:
    check("F3 a method past validate is a KeyError, not an iid plan", True)
plan = list(door.resample_plan({"interval": {"method": "iid", "seed": 1, "resamples": 2}}, [5]))
check("F3 an iid plan: identity row then R draws", len(plan) == 3 and (plan[0][0] == np.arange(5)).all())

# ---- F2
check("F2 declare.TEMPLATES is door.TEMPLATES's field shapes (one table)", declare.TEMPLATES == {k: v[0] for k, v in door.TEMPLATES.items()})
m = {"axes": {"point": ["a", "b", "c"], "size": [27, 9, 3]}, "observable": {"levels": [4, 3, 2]},
     "relations": {"ring": {"template": "ring", "axis": "point", "big": 27, "small": 9, "pairs": [["a", "b"]], "provenance": "Continuation"}}}
for fn in (door.relations_for, door.control_pairs):
    try:
        fn(m, "ring")
        check(f"F2 an undeclared template ('ring') is refused by the table in {fn.__name__}", False, "built a relation")
    except KeyError:
        check(f"F2 an undeclared template ('ring') is refused by the table in {fn.__name__}", True)
m["relations"]["ap"] = {"template": "all-pairs", "axis": "point", "provenance": "Coupling"}   # all-pairs is declared in no locked input: its arm was untested
check("F2 all-pairs: control pairs in edge order, and the relation builds", door.control_pairs(m, "ap") == [("a", "b"), ("a", "c"), ("b", "c")] and door.relations_for(m, "ap") is not None)
m["relations"]["mt"] = {"template": "matched", "axis": "size", "big": 27, "small": 9, "provenance": "Continuation"}
check("F2 matched builds one pair (its own levels)", door.relations_for(m, "mt") is not None and door.control_pairs(m, "mt") == [(27, 9)])

# ---- F5: codes_of indexes a total dict; NOT-MEASURED is written once, explicitly, for every source column of the set
import schema  # noqa: E402
for tn in ("v02-rules", "v08-rules", "v10-rules"):
    T = detect.load_tables(tn)
    direct = [n for n, c in schema.code_cols(T.codes).items() if isinstance(c["from"], str)]
    got = detect.codes_of({}, T)
    check(f"F5 {tn}: with no cells every direct column reads NOT-MEASURED (no KeyError)", all(got[n] == "NOT-MEASURED" for n in direct), {n: got[n] for n in direct})


# ---- F4: a primary with no variance is refused at the door; linearise holds only sd > 0 primaries
good = np.arange(12.0).reshape(6, 2) ** 1.5
flat = np.hstack([good[:, :1], np.full((6, 1), 3.0)])
check("F4 constant_primaries names the (file, primary) with no variance", door.constant_primaries([good, flat]) == [(1, 1)], door.constant_primaries([good, flat]))
check("F4 linearise on sd>0 primaries has h > 0 everywhere", bool((door.linearise([good], 0.001).h > 0).all()))
class Mod:
    series = staticmethod(lambda arrays, ctx: [flat])
real_keys, door.unit_keys = door.unit_keys, lambda m, inst, u, sz: [0]
try:
    detect.rows_linearised({}, {"n": ({"arrays": ["G"]}, Mod)}, [(0, {"G": None})], {0: 0}, [("n", "a", None)], {("n", None): door.Ctx(level=0.95, eps={}, rel={}, method="gamma")})
    check("F4 a unit with a constant primary is refused at the door (a typed refusal with a Next line)", False, "ran")
except detect.Refused as e:
    check("F4 a unit with a constant primary is refused at the door (a typed refusal with a Next line)", "has no variance" in str(e) and "Next:" in str(e), str(e))
finally:
    door.unit_keys = real_keys

sys.exit(1 if bad else 0)
