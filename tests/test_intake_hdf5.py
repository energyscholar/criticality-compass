"""test_intake_hdf5 - plan 1205 P1: the reader hdf5-table-v1 (cc/intake_read.py), on planted files only (no real data). Each check was seen RED under a
stated mutation (the plan-1205 report lists them). Needs h5py for every check that writes an HDF5 file; where it is absent those checks print a
NOT RUN line (penguin has no h5py; jill has it) and the h5py-absent refusal (H4) still runs, by making the import fail.
 H1. The synthetic bank (seed 1, 9 curves) written as ONE float32 HDF5 table (columns T, C, sigma, h; the slow knob h a column), read as a
     LONG_TABLE with hdf5-table-v1, gives the SAME census label as the PER_FILE bank read with csv-curve-v1 (plan 1145's test, re-used). The
     same file as float64 gives it too. Values are as written: a float32 dataset reads to exactly its float32 values widened (no rounding).
 H2. Each named refusal, with its reason: no 2-D dataset, more than one 2-D dataset, a non-float dataset, no column_names attribute, a
     column_names attribute of another length, a declared column that no name matches, a column declared by position, bytes that are no HDF5,
     a NaN cell (no filling); columns found by name in another order read to the declared order; an undeclared column is not read.
 H3. A planted NULL map (noise only, no line) passes through the reader to the census without an exception; the S5 outcome is reported.
 H4. Without h5py (the import made to fail) the reader is Unreadable HDF5_READER_ABSENT, a named reason, never an exception.
 H6. The vectorised LONG_TABLE cut (intake_census._blocks, run at 4,000,000 rows) gives the SAME curves as the row-by-row walk it replaced (kept here as the
     reference), under EXACT and FAST_RESTART: names, rows, first-row slow value and distinct-slow count, on a file whose slow column drifts.
 H5. Every reason the reader emits is a reader_reason row of S4, and the reader is live and a FORMAT [reader] row."""
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_plant  # noqa: E402
import intake_census  # noqa: E402
import intake_read as rd  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, outcome, per_file  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
HAS = importlib.util.find_spec("h5py") is not None
NAMES = ["T", "C", "sigma", "h"]
LONG_H5 = '[reader]\nname = "hdf5-table-v1"\n\n'


def h5(a, names=NAMES, extra=(), attr=True, dtype=np.float32):
    """The bytes of a planted HDF5 file: the 2-D dataset `table` of array a with a column_names attribute, plus `extra` (name, array) datasets."""
    import h5py
    buf = io.BytesIO()
    with h5py.File(buf, "w") as f:
        t = f.create_dataset("table", data=np.asarray(a, dtype=dtype))
        if attr:
            t.attrs["column_names"] = np.array(names, dtype="S")
        [f.create_dataset(n, data=x) for n, x in extra]
    return buf.getvalue()


def decl(cols=("T", "C", "sigma", "h")):
    """A declaration's data, only the fields the reader reads (the role columns): planted, never parsed from TOML here."""
    return {"reader": {"name": "hdf5-table-v1"}, "knobs": {"fast": {"key": cols[0]}, "slow": {"unit": "T"}}, "measured": {"key": cols[1], "unit": "J/K", "uncertainty": {"kind": "COLUMN", "key": cols[2]}},
            "selection": {"layout": "LONG_TABLE", "slow": {"source": "COLUMN", "key": cols[3]}}, "replicate": {"identity": "NONE", "key": {"kind": "NONE"}}, "acquisition": {"row_order": "ASCENDING", "direction": "UNORDERED"}}


A = np.array([[2.5, 0.7, 0.03, 0.1], [2.25, 1.1, 0.03, 0.1], [2.0, 0.5, 0.025, 0.2]])
A32 = tuple(map(tuple, A.astype(np.float32).astype(np.float64).tolist()))   # what a float32 file of A holds, widened


def refused(name, g, reason, *where, tag="H2"):
    check(f"{tag}. {name}: Unreadable {reason}" + (f", naming {where}" if where else ""), isinstance(g, rd.Unreadable) and g.reason == reason and all(w in str(g.detail) for w in where) and g.rows == (), str(g)[:300])


with tempfile.TemporaryDirectory() as tmp:
    banks = Path(tmp) / "banks"
    intake_synth.write(banks / "pf", Path(tmp) / "pf-TRUTH", "pf", 1, 9)
    m = __import__("json").loads((banks / "pf" / "MANIFEST.json").read_text())
    curves = [(f["h"], [[float(x) for x in ln.split(",")] for ln in (banks / "pf" / f["name"]).read_text().splitlines()[1:]]) for f in m["files"]]
    run = lambda ident, text: intake_plant.run(T, tmp, ident, text)

    def bank(name, blocks, **k):
        """<banks>/<name>/bank.h5: each (h, rows) block's rows with h appended, in the given order, as one HDF5 table."""
        (banks / name).mkdir()
        (banks / name / "bank.h5").write_bytes(h5([r + [h] for h, rows in blocks for r in rows], **k))
        return name

    def hdf5_long(ident, name):
        """The synthetic bank's declaration as a LONG_TABLE of <name>/bank.h5 read by hdf5-table-v1."""
        text = long_table(m, ident).replace("<long-test>/pf", "<long-test>/" + name).replace('file = "bank.csv"', 'file = "bank.h5"')
        return text.replace(text[text.index("\n[reader]\n") + 1:text.index("[selection]")], LONG_H5)

    # ---- H1. the same census label
    if HAS:
        pf = outcome(run("pf", per_file(m, "pf")), "S5")
        check("H1. the PER_FILE bank passes S5 CENSUS (9 curves, MISALIGNED)", pf[0] == "PASS" and pf[1].label.curves == 9 and pf[1].label.alignment.name == "MISALIGNED", str(pf)[:300])
        hd = outcome(run("hd", hdf5_long("hd", bank("hd", curves))), "S5")
        check("H1. the same bank as ONE float32 HDF5 table (LONG_TABLE) passes S5 with the SAME census label", hd[0] == "PASS" and pf[0] == "PASS" and hd[1].label == pf[1].label, f"{str(hd)[:200]} against {str(pf)[:200]}")
        h64 = outcome(run("h64", hdf5_long("h64", bank("h64", curves, dtype=np.float64))), "S5")
        check("H1. the same bank as float64 gives the same label", h64[0] == "PASS" and h64[1].label == pf[1].label, str(h64)[:300])
        print(f"  census label: {getattr(pf[1], 'label', pf)}")
        a32 = np.random.default_rng(5).normal(size=(50, 4)).astype(np.float32)
        g = rd.read_hdf5(h5(a32), decl())
        check("H1. float32 is read as written: every value is its float32 widened, not rounded or recomputed", isinstance(g, rd.Grid) and g.rows == tuple(map(tuple, a32.astype(np.float64).tolist())) and g.units == (), str(g)[:200])
        check("H1. the Grid's columns are the declared names, in role order (fast, measured, uncertainty, slow)", g.columns == ("T", "C", "sigma", "h"), str(g.columns))

        # ---- H2. each named refusal
        import h5py
        buf = io.BytesIO()
        with h5py.File(buf, "w") as f:
            f.create_dataset("v", data=np.zeros(4))
        refused("no 2-D dataset (only a 1-D one)", rd.read_hdf5(buf.getvalue(), decl()), "NO_2D_DATASET")
        refused("more than one 2-D dataset", rd.read_hdf5(h5(A, extra=[("second", np.zeros((2, 2)))]), decl()), "MORE_THAN_ONE_2D_DATASET", "2-D datasets = 2")
        refused("a non-float dataset (int32: no cast)", rd.read_hdf5(h5(A, dtype=np.int32), decl()), "DATASET_NOT_FLOAT", "int32")
        refused("no column_names attribute", rd.read_hdf5(h5(A, attr=False), decl()), "COLUMN_NAMES_ATTRIBUTE_ABSENT", "column_names")
        refused("a column_names attribute of another length", rd.read_hdf5(h5(A, names=["T", "C", "sigma"]), decl()), "COLUMN_NAMES_COUNT_DIFFERS", "column_names = 3")
        refused("a declared column that no name matches", rd.read_hdf5(h5(A), decl(("T", "Cp", "sigma", "h"))), "COLUMN_NAME_ABSENT", "'Cp'")
        refused("a column declared by position (never by index)", rd.read_hdf5(h5(A), decl((1, "C", "sigma", "h"))), "COLUMN_NOT_BY_NAME", "1")
        refused("bytes that are no HDF5 file", rd.read_hdf5(b"not an hdf5 file at all", decl()), "NOT_AN_HDF5")
        nan = A.copy()
        nan[1, 2] = np.nan
        refused("a NaN cell of a declared column (no filling, no skipped row)", rd.read_hdf5(h5(nan), decl()), "CELL_NOT_A_NUMBER", "row 2", "'sigma'")
        wide = np.hstack([A, np.full((3, 1), np.nan)])
        ok = rd.read_hdf5(h5(wide, names=NAMES + ["extra"]), decl())
        check("H2. an undeclared column is not read (a NaN there is not a refusal)", isinstance(ok, rd.Grid) and ok.rows == A32, str(ok)[:300])
        sw = rd.read_hdf5(h5(A[:, [3, 2, 1, 0]], names=["h", "sigma", "C", "T"]), decl())
        check("H2. columns found by name in another order read to the declared order", isinstance(sw, rd.Grid) and sw.rows == A32, str(sw)[:300])
        nested = io.BytesIO()
        with h5py.File(nested, "w") as f:
            t = f.create_group("run").create_dataset("table", data=A.astype(np.float32))
            t.attrs["column_names"] = np.array(NAMES, dtype="S")
        nz = rd.read_hdf5(nested.getvalue(), decl())
        check("H2. the one 2-D dataset is found wherever it is (inside a group)", isinstance(nz, rd.Grid) and nz.rows == A32, str(nz)[:300])

        # ---- H3. a planted NULL map (noise only) passes through the reader to the census
        rng = np.random.default_rng(11)
        null = [(h, [[r[0], float(rng.normal(0.5, 0.03)), 0.03] for r in rows]) for h, rows in curves]
        out = run("nl", hdf5_long("nl", bank("nl", null)))
        nl, s4 = outcome(out, "S5"), outcome(out, "S4")
        print(f"  NULL map: S5 outcome {nl[0]}" + (f" {getattr(nl[1], 'label', '')}" if nl[0] == "PASS" else ""))
        check("H3. a noise-only map is read by the reader (S4 SHAPE passes) and reaches the census (S5 gives a verdict, reported not asserted)", s4[0] == "PASS" and nl[0] not in ("READER_NOT_LIVE", "READER_REFUSED"), f"{s4[0]} {nl[0]} {str(nl[1])[:200]}")
    else:
        print("  NOT RUN (h5py is not installed on this machine): H1, H2 and H3 write HDF5 files; run them on jill")

    # ---- H4. h5py absent: the import made to fail
    real = importlib.util.find_spec
    importlib.util.find_spec = lambda name, *a, **k: None if name == "h5py" else real(name, *a, **k)
    try:
        gone = rd.read_hdf5(b"\x89HDF\r\n\x1a\n", decl())
    finally:
        importlib.util.find_spec = real
    refused("h5py absent (the import made to fail)", gone, "HDF5_READER_ABSENT", "h5py", tag="H4")
    check("H4. the H4 refusal names h5py in its words (never an exception, never a fallback)", isinstance(gone, rd.Unreadable) and "h5py" in str(gone.detail), str(gone)[:200])

    # ---- H5. reasons and the reader are table rows
    import ast
    s4t = next(s for s in T["stages"]["stage"] if s["id"] == "S4")
    tree = ast.parse((ROOT / "cc" / "intake_read.py").read_text())
    emitted = ({n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Unreadable" and isinstance(n.args[0], ast.Constant)}
               | {n.elts[1].value for n in ast.walk(tree) if isinstance(n, ast.Tuple) and len(n.elts) == 3 and isinstance(n.elts[1], ast.Constant) and isinstance(n.elts[1].value, str) and isinstance(n.elts[0], ast.Lambda)})
    want = {"HDF5_READER_ABSENT", "NOT_AN_HDF5", "NO_2D_DATASET", "MORE_THAN_ONE_2D_DATASET", "DATASET_NOT_FLOAT", "COLUMN_NAMES_ATTRIBUTE_ABSENT", "COLUMN_NAMES_COUNT_DIFFERS", "COLUMN_NOT_BY_NAME"}
    rows = {r["code"]: r for r in s4t["reader_reason"]}
    check("H5. every reason hdf5-table-v1 adds is emitted by intake_read and is a live reader_reason row of S4", want <= emitted and all(rows[c]["live"] is True for c in want), str(sorted(want - emitted)))
    check("H5. hdf5-table-v1 is live and a FORMAT [reader] row", "hdf5-table-v1" in rd.LIVE and "hdf5-table-v1" in T["format"]["fields"]["reader"]["variants"], "")

# ---- H6. the vectorised cut equals the row-by-row walk
import itertools  # noqa: E402


def walk(g, d):
    """The pre-1205 cut, row by row (reference): the blocks as (rows, first slow value, distinct slow values)."""
    rows = tuple(g.rows)
    rule = {"EXACT": lambda p, r: p[-1] != r[-1], "FAST_RESTART": lambda p, r: r[0] < p[0]}[d["selection"]["block"]]   # the two rules, as the walk held them (ascending fast knob; the slow column last)
    ids = itertools.accumulate(int(rule(p, r)) for p, r in zip(rows[:1] + rows[:-1], rows))
    runs = [[r for _, r in rs] for _, rs in itertools.groupby(zip(ids, rows), key=lambda x: x[0])]
    return [(tuple(rs), rs[0][-1], len({r[-1] for r in rs})) for rs in runs]


class File:
    name = "f.h5"


drifting = [[x, 0.5, 0.03, h] for h in (0.1, 0.2, 0.3) for x in (1.0, 2.0, 3.0)] + [[x, 0.5, 0.03, h] for h in (0.4, 0.1, 0.2) for x in (1.0, 2.0)] + [[1.0, 0.5, 0.03, 0.2]]
gd = rd.Grid(("T", "C", "sigma", "h"), (), tuple(map(tuple, drifting)), ())
for rule in ("EXACT", "FAST_RESTART"):
    dd = {**decl(), "selection": {**decl()["selection"], "block": rule}}
    got = [(c.rows, c.slow[0], c.drift) for c in intake_census._blocks(File, gd, dd)]
    check(f"H6. the vectorised cut equals the row-by-row walk under {rule} ({len(got)} curves, slow column drifting)", got == walk(gd, dd) and len(got) > 1, f"{len(got)} against {len(walk(gd, dd))}")

print("test_intake_hdf5: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
