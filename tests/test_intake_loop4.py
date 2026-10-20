"""test_intake_loop4 - plan 1160 loop 4 (plan gate S11.5e: A33 A34 A35 A39 A41 A42 A43): one check per amendment test, on planted inputs
only (the synthetic bank of cc/intake_synth.py and small files written here; no real data). Each command runs in process against a copy of
the Compass (bin, cc, intake, ...) in a temporary directory, whose intake/ROOTS.toml names the planted banks.
 T35.1 an ORDINAL slow knob ([knobs.slow] kind ORDINAL) is refused at S1 SLOW_KNOB_HAS_NO_METRIC by `bin/cc intake lint` and by `bin/cc intake
       seal` (which writes no SEAL.json); the same declaration with kind QUANTITY passes S1 and seals. (METRIC's totality is tests/test_intake.py
       test 1.)
 T33.1 (A33) a PER_FILE bank of nine curves named run_<k>.csv in which two curves share a slow value: identity RUN with [replicate.key]
       FILE_NAME (separator "_", field 2) passes S5 (every (slow value, run) pair once); the same bank with the key undeclared (kind NONE)
       refuses S5 CURVE_REPEATED; a FILE_NAME field the names do not have (field 3) refuses S5 REPLICATE_KEY_UNRESOLVED.
 T34.1 (A34) one plant per member of intake_differs.DIFFERS, each a later file (curve_003.csv) of the PER_FILE bank edited: bytes that are
       not UTF-8 (ENCODING); tabs for commas (DELIMITER); a fourth header name (COLUMN_COUNT); a header name changed (NAMES_LINE, to a
       planted name that must never print); a data cell that is no number under an equal header (ROWS, the residue the four leave). Each run
       refuses S5 FILE_DIFFERS_FROM_FIRST and its S5 line names that member and no other; DIFFERS is total over the closed set, and the
       planted name never prints.
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - T35.1: the SLOW_KNOB_HAS_NO_METRIC row deleted from intake_choices.choices: FAIL (lint and seal pass S1); METRIC["ORDINAL"] made True
   (ORDINAL mapped to a path): FAIL.
 - T33.1: the key ignored (DECLARED["FILE_NAME"]["PER_FILE"] made ONE in cc/intake_census.py): the FILE_NAME PASS check FAILS
   (CURVE_REPEATED).
 - T34.1: the DELIMITER row removed from intake_differs.DIFFERS: the DELIMITER plant FAILS (it reads COLUMN_COUNT) and the totality check
   FAILS.
"""
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_differs  # noqa: E402
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

    # ---- T33.1 (A33): a replicate key read from the file name
    (banks / "rep").mkdir()
    [(banks / "rep" / f"run_{k}.csv").write_bytes((banks / "pf" / f["name"]).read_bytes()) for k, f in enumerate(M["files"])]
    (banks / "rep" / "MANIFEST.json").write_bytes((banks / "pf" / "MANIFEST.json").read_bytes())
    runs = lambda t: re.sub(r'(?m)^files = \[[^\]]*\]', "files = " + json.dumps([f"run_{k}.csv" for k in range(len(M["files"]))]), t, count=1)
    shared = lambda t: re.sub(r'(?m)^(values = \[)("[^"]*"), "[^"]*"', r"\1\2, \2", t, count=1)   # the second curve at the first's slow value
    keyed = lambda field: lambda t: t.replace('identity = "NONE"', 'identity = "RUN"', 1).replace(
        '[replicate.key]\nkind = "NONE"', f'[replicate.key]\nkind = "FILE_NAME"\nseparator = "_"\nfield = {field}', 1)
    S5 = lambda x: (re.findall(r"- \*\*S5 CENSUS\*\*[^\n]{0,900}", x) or [x[-300:]])[0]   # the run's S5 line, for a failure's why
    s5i = lambda i: (cli("lint", i), cli("seal", i, *SEAL), cli("run", i))[2][1]   # a declaration linted, sealed and run: what run printed
    s5 = lambda edit: s5i(declare(lambda t: edit(shared(runs(t))), "rep"))
    by_name, unkeyed, absent = s5(keyed(2)), s5(lambda t: t.replace('identity = "NONE"', 'identity = "RUN"', 1)), s5(keyed(3))
    check("T33.1 (A33) two curves at one slow value, identity RUN keyed by the file-name field 2: S5 passes", "**S5 CENSUS** (LIVE): EXECUTED, PASS" in by_name, S5(by_name))
    check("T33.1 (A33) the same bank with the key undeclared (kind NONE): S5 refuses CURVE_REPEATED", "**S5 CENSUS** (LIVE): EXECUTED, REFUSE CURVE_REPEATED" in unkeyed, S5(unkeyed))
    check("T33.1 (A33) a file-name field the names do not have (field 3): S5 refuses REPLICATE_KEY_UNRESOLVED", "**S5 CENSUS** (LIVE): EXECUTED, REFUSE REPLICATE_KEY_UNRESOLVED" in absent, S5(absent))

    # ---- T34.1 (A34): FILE_DIFFERS_FROM_FIRST names what differs
    PLANTED = b"zzq7357name"   # a planted header name: it must never print
    lines = lambda x: x.split(b"\n")
    EDITS = {"ENCODING": lambda x: x + b"\xff\n", "DELIMITER": lambda x: x.replace(b",", b"\t"), "COLUMN_COUNT": lambda x: x.replace(b"T,C,sigma", b"T,C,sigma,sd", 1),
             "NAMES_LINE": lambda x: x.replace(b"T,C,sigma", b"T,C," + PLANTED, 1),
             "ROWS": lambda x: b"\n".join(lines(x)[:2] + [b"abc," + lines(x)[2].split(b",", 1)[1]] + lines(x)[3:])}
    check("T34.1 (A34) DIFFERS is total over the closed set ENCODING, DELIMITER, COLUMN_COUNT, NAMES_LINE (and ROWS, the residue)",
          set(intake_differs.DIFFERS) == {"ENCODING", "DELIMITER", "COLUMN_COUNT", "NAMES_LINE", "ROWS"} == set(EDITS), str(sorted(intake_differs.DIFFERS)))
    for member, edit in EDITS.items():
        b = banks / f"df-{member}"
        shutil.copytree(banks / "pf", b)
        (b / "curve_003.csv").write_bytes(edit((b / "curve_003.csv").read_bytes()))
        out = s5i(declare(bank=b.name))
        line = S5(out)
        check(f"T34.1 (A34) {member}: S5 refuses FILE_DIFFERS_FROM_FIRST and names {member} and no other member",
              "REFUSE FILE_DIFFERS_FROM_FIRST" in line and f"{member}: {intake_differs.DIFFERS.get(member, '?')}" in line
              and not [k for k in EDITS if k != member and f"{k}: " in line], line)
        check(f"T34.1 (A34) {member}: the planted header name never prints", PLANTED.decode() not in out, "printed")

print("test_intake_loop4: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
