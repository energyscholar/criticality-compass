"""test_scoreboard - the scoreboard lock: expected/<set>.toml against the STORED verdict of each point and the
verdict RECOMPUTED from its stored sign cells under the CURRENT tables/<set> (fast: no data are read)."""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import view  # noqa: E402


def schema_findings(f, expected):
    """The shape of one expected file: tables = stem, point keys = the input's axes.point, a change log with whys."""
    out = [f"{f.name}: tables '{expected.get('tables')}' differs from the file name"] * (expected.get("tables") != f.stem)
    for inp, verdicts in expected.get("verdicts", {}).items():
        m = tomllib.loads((ROOT / "inputs" / inp / "m.toml").read_text())
        out += [f"{f.name}: [verdicts.{inp}] keys differ from axes.point"] * (set(verdicts) != set(m["axes"]["point"]))
    changes = expected.get("change", [])
    out += [f"{f.name}: no [[change]] entry"] * (not changes)
    return out + [f"{f.name}: a [[change]] has an empty {k}" for c in changes for k in ("date", "points", "why") if not c.get(k)]


bad, planted = [], ROOT / "tests" / "planted" / "expected" / "no-why.toml"
refused = schema_findings(planted, tomllib.loads(planted.read_text()))
print(("ok   " if refused else "FAIL ") + f"{planted.name} is refused: {refused}")
bad += [] if refused == [f"{planted.name}: a [[change]] has an empty why"] else [f"{planted.name}: wrong findings {refused}"]
sets = sorted((ROOT / "expected").glob("*.toml"))
for f in sets:
    expected, T, n = tomllib.loads(f.read_text()), detect.load_tables(f.stem), 0
    bad += schema_findings(f, expected)
    for inp, verdicts in expected["verdicts"].items():
        res = json.loads((ROOT / "results" / f"{inp}@{f.stem}.json").read_text())
        stored = {s["point"]: s["verdict"] for s in res["signature"]}
        for pt, want in verdicts.items():
            again = detect.verdict_of(detect.signature_from_cells(view.cells_of(res, pt), T), T)[0]
            n += (want, stored[pt], again) == (want, want, want)
            if not want == stored[pt] == again:
                bad.append(f"{inp}:{pt}  expected {want}  stored {stored[pt]}  recomputed {again}")
    print(f"scoreboard {f.stem}: {n} of {sum(len(v) for v in expected['verdicts'].values())} points as expected")
sets_with_results = {p.stem.split("@")[1] for p in (ROOT / "results").glob("*.json")}
for name in sorted(sets_with_results - {f.stem for f in sets}):
    print(f"unscored: {name}")
print("\n".join(bad[:40]) + ("\nNext: if the change is intended, edit expected/<set>.toml and append a [[change]] with a why\n" * bool(bad))
      + f"test_scoreboard: {'FAILED ' + str(len(bad)) if bad else 'all passed'}")
sys.exit(1 if bad else 0)
