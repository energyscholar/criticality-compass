"""test_intake_residue - plan 1164 phase 3: the structure-vs-control residue of the intake (BLOAT-REVIEW 1160 section 3), one check per fix.
Planted inputs only (no real data).
 R1. intake_seal.ordering: the reads before the seal are counted only when there is a seal (no `.get` default of 0).
 R2. intake_terminal.identity: RESULT.json's seal fields from a table total over SealStatus (no `.get` default of "").
 R3. an absent declarations/<id>/intake.toml is S0 DECLARATION_FILE_ABSENT through the CLI's path (it was read as "" and refused as a schema).
 R4. intake_bytes.located: a declared name and no ".." part, both in the pattern (no guard chain).
 R5. intake_bytes._read: the first logged read of a file is its pin (one expression, no loop). (plan 1165: a held pin goes on to S3's
     profile rows; the planted directory holds no PROFILE.json, so the run after a held pin is PROFILE_ABSENT, not Pass.)
 R6. intake_read.read_csv: the columns are the header table() found (no `or [[]]` default).
 R7. intake_convert.POSITION: a name is a position only when the names line holds it once (a lookup, no inline if/else).
 R8. intake_convert.verify: an output row with no source cell outside a broadcast column is CELL_MAP_NOT_A_PERMUTATION (min had default=()).
 R9. intake_convert.chained: no manifest is CONVERSION_CHAIN_BROKEN before anything else is read (no inline if/else on None).
Seen RED (each run against the phase-2 commit 9b832f0, or a mutation applied by hand, the test run, the mutation reverted):
 - phase-2 code: R1 FAILS (an unsealed declaration reports CONVERSION_READ_BEFORE_SEAL for a read logged at t_ns -1), R2 FAILS (no IDENTITY),
   R3 FAILS (SCHEMA_UNSUPPORTED), R6 FAILS (a first line of blank cells is taken as the names: COLUMN_NAME_ABSENT), R8 FAILS (IDENTITY_FAILED
   "rows not in source order"); R4, R5, R7, R9 pass on it (pure restructurings, seen red by the mutations below);
 - R1: ordering's `before` returning set(); R2: IDENTITY's UNSEALED row reading rec[f]; R3: declared returning "" for an absent file;
   R4: the (?!\\.\\.(?:/|$)) lookahead removed; R5: `reversed` removed (the last read wins); R6: read_csv's columns made (); R7: the
   `texts.count(t) == 1` filter removed; R8: the `hollow` row made to hold always (min of an empty sequence raises); R9: chained's None row sent to
   _chained (a TypeError)."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_blind as blind  # noqa: E402
import intake_bytes  # noqa: E402
import intake_convert as ic  # noqa: E402
import intake_read as rd  # noqa: E402
import intake_seal  # noqa: E402
import intake_terminal  # noqa: E402
from intake_fold import before_data  # noqa: E402
from intake_plant import conversion, rooted  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
CT = ic.ctables()
log = lambda p, recs: Path(p).write_text("".join(json.dumps(r) + "\n" for r in recs))

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)

    # ---- R1. ordering
    d = tmp / "r1"
    d.mkdir()
    log(d / "conversion-access.log", [{"path": "/raw/a.csv", "partition": "converted-from", "t_ns": -1}])
    o, said = intake_seal.ordering(d, T)
    check("R1. no seal: NOT_SEALED and no CONVERSION_READ_BEFORE_SEAL, whatever t_ns the conversion log holds", o is intake_seal.Ordering.NOT_SEALED and "CONVERSION_READ_BEFORE_SEAL" not in said, said)
    (d / "SEAL.json").write_text(json.dumps({"sealed_at_ns": 100}))
    log(d / "conversion-access.log", [{"path": "/raw/a.csv", "partition": "converted-from", "t_ns": 50}, {"path": "/raw/b.csv", "partition": "converted-from", "t_ns": 150}])
    o, said = intake_seal.ordering(d, T)
    check("R1. a seal: the conversion reads before its time are counted (1 file of 2)", "CONVERSION_READ_BEFORE_SEAL (1 file)" in said, said)

    # ---- R2. RESULT.json's seal identity
    S = intake_seal.SealStatus
    rec = {"declaration_sha256": "s", "sealed_at_utc": "u", "author_kind": "human", "confirmed_by": "c", "sealed_at_ns": 1}
    check("R2. IDENTITY is total over SealStatus", set(getattr(intake_terminal, "IDENTITY", {})) == set(S), str(getattr(intake_terminal, "IDENTITY", "no IDENTITY")))
    got = lambda status, r: getattr(intake_terminal, "identity", lambda seal: "no identity")(intake_seal.SealState(status, "", r))
    check("R2. UNSEALED (no SEAL.json, record {}): every seal field empty by the status",
          got(S.UNSEALED, {}) == {"status": "UNSEALED", "declaration_sha256": "", "sealed_at_utc": "", "author_kind": "", "confirmed_by": ""}, str(got(S.UNSEALED, {})))
    check("R2. SEALED and SEALED_THEN_EDITED: the record's four fields, nothing else",
          all(got(s, rec) == {"status": s.name, **{k: rec[k] for k in ("declaration_sha256", "sealed_at_utc", "author_kind", "confirmed_by")}} for s in (S.SEALED, S.SEALED_THEN_EDITED)), str(got(S.SEALED, rec)))

    # ---- R3. DECLARATION_FILE_ABSENT through the CLI's path (intake._go on a root that holds the tables)
    r3 = tmp / "r3"
    (r3 / "declarations" / "empty").mkdir(parents=True)
    for n in ("intake", "inputs", "cc.toml"):
        (r3 / n).symlink_to(ROOT / n)
    _, _, out = intake._go(r3, "empty", before_data)
    check("R3. a declaration directory with no intake.toml: S0 refuses DECLARATION_FILE_ABSENT, and every later stage is withheld",
          getattr(out["S0"].result, "reason", "PASS") == "DECLARATION_FILE_ABSENT" and all(e.mark is not blind.Mark.PASSED for e in out.values()), out["S0"].text(T)[:300])
    check("R3. DECLARATION_FILE_ABSENT is a live S0 row of STAGES.toml with a sentence", "DECLARATION_FILE_ABSENT" in T["sentences"]
          and [r["live"] for s in T["stages"]["stage"] if s["id"] == "S0" for r in s["reason"] if r["code"] == "DECLARATION_FILE_ABSENT"] == [True], "")

    # ---- R4. located
    roots = {"<r>": str(tmp / "root")}
    CASES = {"<r>": str(tmp / "root"), "<r>/a/b": str(tmp / "root" / "a" / "b"), "<r>/a..b": str(tmp / "root" / "a..b"),
             "<r>/a/../b": "", "<r>/..": "", "<r>/../x": "", "<nope>/a": "", "<r>a": "", "r/a": ""}
    check("R4. located: a declared name and a path with no '..' part, else ''", {k: intake_bytes.located(k, roots) for k in CASES} == CASES,
          str({k: intake_bytes.located(k, roots) for k in CASES if intake_bytes.located(k, roots) != CASES[k]}))
    check("R4. located with no root declared names none", intake_bytes.located("<r>/a", {}) == "", intake_bytes.located("<r>/a", {}))

    # ---- R5. the first logged read is the pin
    loc, d5 = tmp / "r5bank", tmp / "r5"
    loc.mkdir()
    d5.mkdir()
    (loc / "a.csv").write_bytes(b"T,C\n1,2\n")
    sha = hashlib.sha256(b"T,C\n1,2\n").hexdigest()
    reader = type("Loader", (), {"read": lambda self, p: Path(p).read_bytes()})()
    R5 = type("Declaration", (), {"id": "r5", "data": {"source": {"root": "<r>/r5bank"}}})()   # plan 1165: S3's profile rows name the declaration
    path = str((loc / "a.csv").resolve())
    pinned = lambda first, then: (log(d5 / "access.log", [{"path": path, "sha256": first, "route": "loader"}, {"path": path, "sha256": then, "route": "loader"},
                                                          {"path": path, "sha256": "x", "route": "bypass"}]), intake_bytes._read(R5, d5, loc, ("a.csv",), reader))[1]
    check("R5. the first loader read pins the file: first = the bytes' sha passes the pin (plan 1165: to S3's next row, PROFILE_ABSENT: d5 holds no"
          " PROFILE.json; was Pass), a later different read does not move the pin",
          getattr(pinned(sha, "0" * 64), "reason", "PASS") == "PROFILE_ABSENT" and getattr(pinned("0" * 64, sha), "reason", "PASS") == "PIN_MISMATCH",
          f"{getattr(pinned(sha, '0' * 64), 'reason', 'PASS')} {getattr(pinned('0' * 64, sha), 'reason', 'PASS')}")

    # ---- R6. read_csv
    cols = lambda b: getattr(rd.read_csv(b, {}), "reason", None) or rd.read_csv(b, {}).columns
    check("R6. read_csv: the columns are the header table() found, a first line of blank cells skipped like any blank line",
          cols(b"T,C\n1,2\n") == ("T", "C") and cols(b",,\nT,C\n1,2\n") == ("T", "C"), f"{cols(b'T,C' + chr(10).encode() + b'1,2')} {cols(b',,' + chr(10).encode() + b'T,C' + chr(10).encode() + b'1,2')}")
    check("R6. read_csv: no row is HEADER_LINE_ABSENT, a header alone NO_DATA_ROW", cols(b"") == "HEADER_LINE_ABSENT" and cols(b"\n\n") == "HEADER_LINE_ABSENT" and cols(b"T,C\n") == "NO_DATA_ROW",
          f"{cols(b'')} {cols(b'T,C' + chr(10).encode())}")

    # ---- R7. POSITION
    P = ic.POSITION[str]
    check("R7. a name is a position only when the names line holds it once", (P(["a", "b", "a"], "a"), P(["a", "b", "a"], "b"), P(["a"], "z"), P([], "a")) == (None, 1, None, None),
          str((P(["a", "b", "a"], "a"), P(["a", "b", "a"], "b"), P(["a"], "z"))))

    # ---- R8. an output row with no source cell outside a broadcast column (a manifest the converter never writes: the manifest is not hashed)
    name = "r8"
    raw, d8 = tmp / "cc-datasets" / name / "raw", tmp / "declarations" / name
    raw.mkdir(parents=True)
    d8.mkdir(parents=True)
    (raw / "a.csv").write_bytes(b"h,1.5,1.6\n0.1,0.25,0.5\n0.2,0.75,1.0\n")
    (d8 / "CONVERSION.toml").write_text(conversion(f"<cc-datasets>/{name}/raw", f"<cc-banks>/{name}/bank", [("a.csv", "out.csv", '{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}')]))
    first = ic.convert(tmp, name, rooted(T, tmp), CT)
    bank = tmp / "cc-banks" / name / "bank"
    m = json.loads((bank / ic.MANIFEST).read_text())
    for label, keep in (("only the broadcast columns T and h", [0, 2]), ("no column", [])):
        r = dict(m["outputs"][0])
        text = "\n".join(",".join(ln.split(",")[j] for j in keep) for ln in (bank / "out.csv").read_text().splitlines()) + "\n"
        (bank / "b.csv").write_text(text)
        r.update(path="b.csv", sha256=hashlib.sha256(text.encode()).hexdigest(), cells=[[row[j] for j in keep] for row in r["cells"]], broadcast=list(range(len(keep))))
        (bank / ic.MANIFEST).write_text(json.dumps({**m, "outputs": m["outputs"] + [r]}))
        try:
            got = ic.verified(tmp, name, rooted(T, tmp), CT)
        except ValueError as e:   # min() of an empty sequence: the default removed with no row before it
            got = blind.Refuse(f"RAISED {e}", blind.detail())
        check(f"R8. a second output of the unit holding {label}: --verify refuses CELL_MAP_NOT_A_PERMUTATION, naming the row with no source cell",
              getattr(first, "reason", "PASS") == "PASS" and getattr(got, "reason", "PASS") == "CELL_MAP_NOT_A_PERMUTATION" and "no source cell outside a broadcast column" in str(got.evidence),
              f"{getattr(got, 'reason', 'PASS')} {str(getattr(got, 'evidence', ''))[:200]}")

    # ---- R9. chained with no manifest
    asked = []
    try:
        got = ic.chained(None, lambda p: asked.append(p), lambda p: asked.append(p), CT, {})
    except TypeError as e:
        got = blind.Refuse(f"RAISED {e}", blind.detail())
    check("R9. no manifest: CONVERSION_CHAIN_BROKEN, and no raw or bank file is read", getattr(got, "reason", "PASS") == "CONVERSION_CHAIN_BROKEN" and asked == [],
          f"{getattr(got, 'reason', 'PASS')} {asked}")

print("test_intake_residue: " + ("all passed" if not bad else "FAILED " + "; ".join(bad)))
sys.exit(1 if bad else 0)
