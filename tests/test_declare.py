"""test_declare - the door's breakers: planted bad plugins must be refused with their exact finding and Next line."""
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from dataclasses import fields

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cc"))
import declare  # noqa: E402

P = ROOT / "tests" / "planted"
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def found(path, over, root=ROOT):
    return [declare.fmt(f) for f in declare.check_file(path, root, **{k: P / v for k, v in over.items()})]


plants = tomllib.loads((P / "expected.toml").read_text())["plant"]
check("expected.toml names at least 26 plants", len(plants) >= 26, f"only {len(plants)}")
for pl in plants:
    name, over, want = pl["file"], pl.get("over", {}), pl["text"]
    got = found(P / name, over)
    check(f"plant {name} gives its finding", want in got, f"wanted\n{want}\n  got {got}")
    if pl["fix"]:
        text = (P / name).read_text()
        fixed = text.replace(pl["fix"][0], pl["fix"][1])
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "planted" / name
            f.parent.mkdir()
            f.write_text(fixed)
            after = [x.replace(str(f), f"tests/planted/{name}") for x in found(f, over)]
        check(f"plant {name} fixed no longer gives it", fixed != text and want not in after, f"still got {after}")
clean = (("input-ok.toml", {}), ("manifest-ok.toml", {"input": "input-ok.toml"}), ("codes-mini.toml", {}),
         ("verdict-mini-ok.toml", {"codes": "codes-mini.toml"}))
for name, over in clean:
    check(f"planted base {name} is clean", found(P / name, over) == [], str(found(P / name, over)))

repo = declare.validate(ROOT)[0]
check("the repo validates clean", repo == [], "\n".join(map(declare.fmt, repo)))
codes = tomllib.loads((ROOT / "tables/verdict-x-rules/codes.toml").read_text())
dom = declare.doms(codes, declare.Ctx(ROOT).alpha["nulls"])
size = 1
for v in dom.values():
    size *= len(v)
check("the verdict domain has exactly 45 360 cells", size == 45360, str(size))
check("verdict-x-rules partitions it (no overlap, no gap)",
      declare.check_file(ROOT / "tables/verdict-x-rules/verdict.toml") == [])

sources = [f for d in ("cc", "bin") for f in (ROOT / d).rglob("*") if f.is_file() and f.suffix in ("", ".py")]
hits = {str(f.relative_to(ROOT)) for f in sources if "class_truth" in f.read_text()}
check("firewall: class_truth appears only in declare.py and score.py",
      hits <= {"cc/declare.py", "cc/score.py"} and "cc/declare.py" in hits, str(hits))
check("firewall: Case has no class_truth field", "class_truth" not in {f.name for f in fields(declare.Case)})
case = declare.load_case(ROOT / "cases/potts-q3.toml")
check("firewall: a loaded case carries no class_truth",
      not hasattr(case, "class_truth") and declare.load_truth(ROOT / "cases/potts-q3.toml") == "POINT")

with tempfile.TemporaryDirectory() as t:
    copy = Path(t) / "repo"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    shutil.copyfile(P / "points-unknown-case.toml", copy / "inputs/w2-potts/points.toml")
    scoped = declare.validate(copy, "x8-ising-needle", "verdict-x-rules")[0]
    full = declare.validate(copy)[0]
check("scoped validate of x8 passes while a join elsewhere is bad", scoped == [], str(scoped))
check("full validate names that bad join", any("unknown case 'potts-4'" in f.msg for f in full), str(full))
print("".join(f"FAILED {b}\n" for b in bad) + "test_declare: " + ("FAILED " + str(len(bad)) if bad else "all passed"))
sys.exit(1 if bad else 0)
