"""test_intake_example - plan 1136 phase 1, test 6: the worked example declarations/dial1118-s1-v5 (plan 1160 A35: dial1118-s1-v4 restated in
format v5, was -v4; plan 1160 A17: dial1118-s1-v3 restated in format v4, was -v3; plan 1160 P1: dial1118-s1-v2 restated in format v3; dial1118-s1 (v1), dial1118-s1-v2 (v2) and -v3 (v3) are kept as history, and refused SCHEMA_UNSUPPORTED by tests/test_intake.py test 5) (the planted S1 bank of plan 1118, sealed
against the FIXTURE universe tests/planted/intake/p1118-bank-FIXTURE) reaches PRIMARY_INCOMPLETE, and its committed intake-report.md is the
report a run writes now, byte for byte, listing every stub. Expected (design E11 with the A2 numbering, plus A2 Q6): PRIMARY_INCOMPLETE[S1, S3,
S4, S5, S6, S7, S8, confirmation] (the seal is an unconfirmed AI draft), ROBUSTNESS_INCOMPLETE[S9], S10 a STUB.
S0 runs the CC transducer check, whose update pin is looked up in the toolset's git history at the data root's parent (cc/transducer.py), so
this test needs CC_DATA_ROOT (or --data-root) to name the toolset's data/ directory, like test_transducer; without it S0 refuses
TRANSDUCER_FILE_REFUSED and this test says so. It reads no data file: the fixture's files are empty and every data stage is a STUB."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import intake  # noqa: E402
import intake_fold  # noqa: E402
import intake_say  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


ID = "dial1118-s1-v5"   # plan 1160 A35 (was dial1118-s1-v4, format v4: history; plan 1160 A17: was dial1118-s1-v3)
D = ROOT / "declarations" / ID
# (1160 A40: was intake._go(ROOT, ID, ...) on D itself) the root '<p1118-bank>' is a name of intake/ROOTS.toml now, so S3 reads the fixture's
# files and appends to the declaration's access.log: the run is made on a copy of D in a temporary directory, so the test writes nothing
# under declarations/.
TMP = tempfile.TemporaryDirectory()
C = Path(TMP.name) / ID
shutil.copytree(D, C)
t = intake.tables(ROOT)
out = intake.fold(t["stages"]["stage"], intake.bodies(t, C, intake.declared(C), intake._findings(ROOT, D, ID)))
p, r = intake_fold.verdicts(t, out)
check("6. S0 FORMAT passes (needs the toolset through CC_DATA_ROOT for the transducer pin)", out["S0"].mark is intake.Mark.PASSED, out["S0"].text(t)[:400])
check("6. S2 SEAL passes SEALED: the committed SEAL.json and seal.log hold the declaration's sha (plan 1139: the seal is advisory)", out["S2"].mark is intake.Mark.PASSED and out["S2"].result.evidence.status.name == "SEALED", out["S2"].text(t)[:300])
# plan 1160 A40 (was: S3 refuses ROOT_UNRESOLVED, PRIMARY_REFUSED_AT S3, S10 withheld after S3): the bank '<p1118-bank>' is a name of
# intake/ROOTS.toml (the committed fixture), so S3 admits the 61 empty files and S4 refuses READER_NOT_LIVE (npz-curve-v1 is not live);
# every stage that needs it is withheld. (plan 1165) S3 needs a PROFILE.json: the example carries the committed PROFILE.json and PROFILE.md
# of `bin/cc intake profile dial1118-s1-v5 <p1118-bank>` (64 files, the 61 npz UNPROFILED_FORMAT; npz-curve-v1 is no reader against()
# checks, so 0 contradictions), and the committed report carries its Profile line.
check("6. (1160 A40) S3 passes on the fixture (61 files, each 0 bytes)", out["S3"].mark is intake.Mark.PASSED and len(out["S3"].result.evidence.files) == 61
      and all(f.data == b"" for f in out["S3"].result.evidence.files), out["S3"].text(t)[:300])
check("6. (1160 A40) S4 refuses READER_NOT_LIVE", out["S4"].mark is intake.Mark.REFUSED and out["S4"].result.reason == "READER_NOT_LIVE", out["S4"].text(t)[:300])
check("6. PRIMARY_REFUSED_AT S4 (1160 A40: was S3)", p.kind is intake_fold.Primary.PRIMARY_REFUSED_AT and p.at == "S4", f"{p}")
check("6. ROBUSTNESS_WITHHELD", r.kind is intake_fold.Robustness.ROBUSTNESS_WITHHELD, f"{r}")
check("6. S10 KERNEL_HANDOFF is withheld after S4's refusal (1160 A40: was S3's)", isinstance(out["S10"], intake_fold.Withheld) and out["S10"].stage == "S4", str(out["S10"]))
text = intake_say.report(t, ID, out, intake.intake_seal.ordering(C, t))
check("6. the committed intake-report.md is the report of a run now, byte for byte", text == (D / "intake-report.md").read_text(), "")
stubs = [f"- **{s['id']} {s['name']}** (STUB): STUB. " for s in t["stages"]["stage"] if not s["implemented"]]
# plan 1160 P1: S1 has a body now (was: the one stub no refusal withholds), so every stub is withheld after S3's refusal; plan 1160 P4: S6
# has a body too, so the stubs are S7..S10 (was: len(stubs) == 5); plan 1160 P5: S7, S8, S9 have bodies, so the one stub is S10 (was: 4);
# plan 1160 A6: P6 gave S10 a body, so no stub remains (was: 1). With `stubs` empty the per-line test is vacuous, so the report itself must
# carry no STUB marking: no "(STUB)" stage line and no "| STUB |" table cell. Seen red: S10 implemented = false in STAGES.toml.
check("6. S1 CHOICES passes (every live row), and no stub is listed as a STUB: each is withheld after S3", out["S1"].mark is intake.Mark.PASSED
      and len(stubs) == 0 and all(ln not in text for ln in stubs) and "(STUB)" not in text and "| STUB |" not in text,
      str([s["id"] for s in t["stages"]["stage"] if not s["implemented"]]))
check("6. the report carries the seal claim and the UNENFORCED list", t["stages"]["report"]["seal_claim"] in text and all(u in text for u in t["stages"]["report"]["unenforced"]), "")
cli = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "lint", ID], capture_output=True, text=True)
check("6. bin/cc intake lint passes S0 and S1 (plan 1160 P1: was S1 STUB)", cli.returncode == 0 and "S1 EXECUTED, PASS." in cli.stdout, cli.stdout[-300:])
again = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "seal", ID, "--author", "x", "--as", "human", "--unconfirmed"],   # plan 1160 A20: no --universe (was the fixture)
                       capture_output=True, text=True)
check("6. sealing it again is refused ALREADY_SEALED and writes nothing", again.returncode == 1 and "ALREADY_SEALED" in again.stdout, again.stdout[-300:])
# plan 1160 A40: the example is reproducible with the CLI alone. A fresh copy of the tool and the example (bin, cc, intake, the top-level files, the fixture,
# the declaration without its SEAL.json and seal.log) is sealed by that copy's bin/cc: the seal passes, and lists the universe the committed seal lists.
with tempfile.TemporaryDirectory() as fresh:
    F = Path(fresh)
    for part in ("bin", "cc", "intake", "tests/planted/intake/p1118-bank-FIXTURE"):
        shutil.copytree(ROOT / part, F / part, ignore=shutil.ignore_patterns("__pycache__"))
    [shutil.copyfile(q, F / q.name) for q in ROOT.iterdir() if q.is_file()]   # cc.toml, checks.toml and the other top-level files
    (F / "declarations" / ID).mkdir(parents=True)
    for n in intake.intake_seal.FILES:
        shutil.copyfile(D / n, F / "declarations" / ID / n)
    sealed = subprocess.run([str(F / "bin" / "cc"), "intake", "seal", ID, "--author", "x", "--as", "ai-draft", "--unconfirmed"], capture_output=True, text=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    listing = lambda q: json.loads((q / "SEAL.json").read_text())["universe"]["listing"] if (q / "SEAL.json").is_file() else None
    check("6. (1160 A40) bin/cc intake seal on a fresh copy passes, and its universe listing is the committed seal's",
          sealed.returncode == 0 and listing(F / "declarations" / ID) == listing(D) and listing(D), sealed.stdout[-400:] + sealed.stderr[-400:])
usage = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "fold"], capture_output=True, text=True)
check("6. an unknown subcommand is a usage refusal with a Next line", usage.returncode == 1 and "Next: bin/cc intake explain" in usage.stdout, usage.stdout)
print("test_intake_example: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
