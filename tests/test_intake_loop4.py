"""test_intake_loop4 - plan 1160 loop 4 (plan gate S11.5e: A33 A34 A35 A39 A41 A42 A43): one check per amendment test, on planted inputs
only (the synthetic bank of cc/intake_synth.py and small files written here; no real data). Each command runs in process against a copy of
the Compass (bin, cc, intake, ...) in a temporary directory, whose intake/ROOTS.toml names the planted banks.
 T35.1 an ORDINAL slow knob ([knobs.slow] kind ORDINAL) is refused at S1 SLOW_KNOB_HAS_NO_METRIC by `bin/cc intake lint` and by `bin/cc intake
       seal` (which writes no SEAL.json); the same declaration with kind QUANTITY passes S1 and seals. (METRIC's totality is tests/test_intake.py
       test 1.)
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - T35.1: the SLOW_KNOB_HAS_NO_METRIC row deleted from intake_choices.choices: FAIL (lint and seal pass S1); METRIC["ORDINAL"] made True
   (ORDINAL mapped to a path): FAIL.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import ORDINAL, per_file  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    w, banks = tmp / "cc", tmp / "banks"
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
    (w / "intake" / "ROOTS.toml").write_text((w / "intake" / "ROOTS.toml").read_text() + f'\n"<l4>" = "{banks}"   # test_intake_loop4: the planted banks\n')
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    M = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    TRANS = intake_synth.declare(M, "x", "pf")[2]
    n = iter(range(1000))

    def cli(*args):
        """One `bin/cc intake ...` command in process: (its exit code, stdout + stderr)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = intake.cli(w, list(args))
        return rc, out.getvalue()

    def declare(edit=lambda t: t, bank="pf"):
        """A new declaration of the PER_FILE synthetic bank (bank `bank` under <l4>), edited by `edit`: its id."""
        ident = f"d{next(n)}"
        d = w / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(edit(per_file(M, ident).replace("<long-test>/pf", f"<l4>/{bank}")))
        (d / "transducer.toml").write_text(TRANS.replace('id = "x"', f'id = "{ident}"'))
        return ident

    SEAL = ("--author", "plan 1160 loop4 test", "--as", "ai-draft", "--unconfirmed")

    # ---- T35.1 (A35): ORDINAL is refused at S1, at lint and at seal; QUANTITY passes
    o, q = declare(ORDINAL), declare()
    lint_o, seal_o = cli("lint", o), cli("seal", o, *SEAL)
    lint_q, seal_q = cli("lint", q), cli("seal", q, *SEAL)
    s1 = "S1 EXECUTED, REFUSE SLOW_KNOB_HAS_NO_METRIC"
    check("T35.1 (A35) kind ORDINAL: lint refuses S1 SLOW_KNOB_HAS_NO_METRIC (exit 1)", lint_o[0] == 1 and s1 in lint_o[1], lint_o[1][-400:])
    check("T35.1 (A35) kind ORDINAL: seal refuses S1 SLOW_KNOB_HAS_NO_METRIC (exit 1) and writes no SEAL.json",
          seal_o[0] == 1 and s1 in seal_o[1] and not (w / "declarations" / o / "SEAL.json").exists(), seal_o[1][-400:])
    check("T35.1 (A35) kind QUANTITY (the control): lint passes S1 and seal writes SEAL.json",
          lint_q[0] == 0 and "S1 EXECUTED, PASS" in lint_q[1] and seal_q[0] == 0 and (w / "declarations" / q / "SEAL.json").is_file(), lint_q[1][-300:] + seal_q[1][-300:])

print("test_intake_loop4: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
