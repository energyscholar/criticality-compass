"""test_breakers - rule breakers: synthetic readings through detect's own entry points and the verdict table."""
import sys
import tomllib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

TOP = {"schema", "kind", "id", "rule", "why", "tables", "entry", "cells", "expect", "mutation"}
ENTRY = {"kind", "instrument", "column", "context", "vector", "x"}
EXPECT = {"cell", "signature_column", "code", "verdict", "not_verdict"}


def recipe(r):
    """Synthetic INPUTS only (row 0 exact, rows 1..n noisy); no rule is implemented here."""
    rng, k = np.random.default_rng(r.get("seed", 0)), r["recipe"]
    if k == "normal":
        return np.concatenate([[r["mean"]], r["mean"] + r["sd"] * rng.standard_normal(r["rows"])])
    if k == "nodes":
        means = np.array(r["means"])
        return np.vstack([means, means + r["sd"] * rng.standard_normal((r["rows"], len(means)))])
    if k == "growth":
        y, ratio = np.array(r["y_steps"]), np.log(np.array(r["sizes"][1:]) / np.array(r["sizes"][:-1]))
        ys = np.vstack([y, y + r["sd"] * rng.standard_normal((r["rows"], len(y)))])
        return np.exp(np.hstack([np.zeros((len(ys), 1)), np.cumsum(ys * ratio, axis=1)]))
    return np.array(r["values"], float)


def evaluate(b):
    """The breaker's entry column goes through detect's readout; every cell then through codes and verdict."""
    tables, e, cells, got = detect.load_tables(b["tables"]), b["entry"], dict(b["cells"]), {}
    if e["kind"] != "cells":
        c = e["context"]
        ctx = detect.context_for(c["input"], e["instrument"], c["point"], c.get("size"))
        if e["kind"] == "readout":
            r = detect.read_vector(e["instrument"], e["column"], recipe(e["vector"]), ctx)
        else:
            r = detect.after_reduce(e["instrument"], recipe(e["x"]), ctx)[e["column"]]
        got["cell"] = r.cell
        per_size = detect.instrument(e["instrument"])[0]["unit"] == "point-size"
        cells[f"{e['instrument']}.{e['column']}"] = [r.cell] if per_size else r.cell
    sig = detect.signature_from_cells(cells, tables)
    got["code"], got["verdict"] = sig.get(b["expect"].get("signature_column")), detect.verdict_of(sig, tables)[0]
    return got


ok, broken = 0, []
files = sorted((ROOT / "tests" / "breakers").glob("*.toml"))
for f in files:
    b = tomllib.loads(f.read_text())
    shape = [] if set(b) == TOP and set(b["entry"]) <= ENTRY and set(b["expect"]) <= EXPECT else ["unknown or missing field"]
    shape += [] if b["id"] == f.stem else ["id differs from the file name"]
    shape += ["py starts with <"] if b["mutation"]["py"].startswith("<") else []
    if shape:
        broken.append(f"BROKEN {f.stem}: {', '.join(shape)}")
        continue
    got, want = evaluate(b), b["expect"]
    bad = [f"expected {k} {want[k]}, got {got.get(k)}" for k in ("cell", "code", "verdict")
           if k in want and got.get(k) != want[k]]
    if got["verdict"] in want.get("not_verdict", []):
        bad.append(f"expected verdict not in {want['not_verdict']}, got {got['verdict']}")
    if bad:
        broken.append(f"BROKEN {b['id']}: " + "; ".join(bad))
    else:
        ok += 1
        print(f"ok {b['id']}")
print("\n".join(broken))
print(f"test_breakers: {ok} of {len(files)} ok" + ("" if broken else " (all passed)"))
sys.exit(1 if broken or not files else 0)
