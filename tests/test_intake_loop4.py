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
 T42.1 (A42) peek finds a file whose name holds spaces (<cc-datasets>/sp/raw/my run 1.csv), by membership of each directory's listing; the
       four T19.2 refusals (another root, an absolute path, a '..' part, a bare name) still hold, each SOURCE_FILE_ABSENT.
 T43.1 (A43) peek on a 2-column file whose header line holds 6 blank-separated tokens: the shown line says 2 cells under COMMA (the
       default; --delimiter WHITESPACE says 6 cells under WHITESPACE, the 6 tokens), and the head says the file's line count (4).
 T41.1 (A41, leak) a plant bank whose nine curve FILE NAMES carry a sentinel (curve_zzqBLIND4471_<k>.csv): `bin/cc intake blind` makes
       the view <cc-blind>/<id>/ of ordinal-named links (001.csv ...) and the key beside it; a BLINDED declaration whose selection is the
       view's listing (as a declarer reads it) is linted, sealed and run, and passes S5; nothing printed (blind, lint, seal, run) and no
       file the intake wrote under declarations/<id>/ (report, RESULT.json, SEAL.json, access.log, seal.log) holds the sentinel. Each
       refusal of the command is planted (its Detail must not print a selected name either, so the absent name carries the sentinel):
       BLIND_ID_REFUSED, ROOT_UNRESOLVED, BLIND_NAME_REPEATED, SOURCE_FILE_ABSENT, BLIND_VIEW_EXISTS, and BLIND_NOT_ONE_DEVICE when this
       machine has a second device at /dev/shm (else NOT REACHED HERE); a BLINDED root not under <cc-blind>/ is refused at S0
       ROOT_NOT_UNDER_CC_BLIND.
 T39.1-T39.5 (A39) on three planted banks of nine curves on one T grid (0..9): MONO (C rises with T: every maximum at the fast end),
       PEAKED (C peaks at T = 4 or 5: interior), SHIFTED (PEAKED with curve_004's T moved by +100).
       T39.1 MONO, an ALTERNATIVE projection ARGMAX_FAST (chained): S9 refuses NO_INTERIOR_FAST_MAXIMUM, {curves 9, of 9}, its Next printed;
             S10 still passes. T39.2 MONO, the PRIMARY projection ARGMAX_FAST: S10 refuses PROJECTION_EMPTY_ON_CURVE and no RESULT.json is
             written (PEAKED, the control, passes S10). T39.3 SHIFTED, the ALTERNATIVE bridge PAIR_NEAREST_FAST: S9 refuses
             ANCHOR_OUTSIDE_NEIGHBOUR_SPAN naming curve_003, curve_004, curve_005 once each in slow order, {curves 3, of 9}. T39.4 MONO
             on the aligned grid, PAIR_NEAREST_FAST: S9 refuses NO_INTERIOR_FAST_MAXIMUM (the span rule alone passed it). T39.5 DOMAIN is total
             over POLICY's projections, ANCHOR and PAIRS over its bridges, NEXT over S9's rows; S9's rows are the two, and S10's
             PROJECTION_EMPTY_ON_CURVE is live and before DOOR_REFUSED.
(plan 1165) Every declaration that reaches S3 is profiled first (`intake profile <id> <its root>`, s5i; T41.1's blinded view too). T34.1's
five members are then refused at S3 PROFILE_CONTRADICTED (the profile predicts each), the planted name unprinted; the S5 Detail is checked
on a second declaration run with intake_against.against returning () (a profile that predicts nothing).
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - T35.1: the SLOW_KNOB_HAS_NO_METRIC row deleted from intake_choices.choices: FAIL (lint and seal pass S1); METRIC["ORDINAL"] made True
   (ORDINAL mapped to a path): FAIL.
 - T33.1: the key ignored (DECLARED["FILE_NAME"]["PER_FILE"] made ONE in cc/intake_census.py): the FILE_NAME PASS check FAILS
   (CURVE_REPEATED).
 - T34.1: the DELIMITER row removed from intake_differs.DIFFERS: the DELIMITER plant FAILS (it reads COLUMN_COUNT) and the totality check
   FAILS.
 - T42.1: peek_cli's `at = listed(rel, base)` restored to the old class, `intake_bytes.located(rel, {"<cc-datasets>": base})`: the spaced
   file is SOURCE_FILE_ABSENT (FAIL); the four refusals still hold.
 - T41.1: the view built with the original names (`view / n` for `view / o` in intake_blindview._make): the leak checks FAIL (the
   sentinel in the view's names reaches the declaration's outputs).
 - T39: DOMAIN["ARGMAX_FAST"] made `lambda cs: []`: T39.1, T39.2 and T39.4 FAIL; the S10 row's holds made `lambda: True`: T39.2 FAILS;
   the old PAIRS row restored (`a.where` for both directions): T39.3 FAILS; ANCHOR["PAIR_NEAREST_FAST"] made "MAX_MEASURED": T39.4 FAILS;
   NEXT's ANCHOR_OUTSIDE_NEIGHBOUR_SPAN row deleted: T39.5 FAILS.
 - T43.1: the count omitted (peek's `count` made to return ""): FAIL.
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
import intake_convert  # noqa: E402
import intake_differs  # noqa: E402
import intake_feasible  # noqa: E402
import tomllib  # noqa: E402
import intake_convert as ic  # noqa: E402
import intake_synth  # noqa: E402
import intake_against as A  # noqa: E402
from intake_plant import ARGMAX_LANE, ORDINAL, PAIR_LANE, per_file  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    w, banks = tmp / "cc", tmp / "banks"
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
    (w / "intake" / "ROOTS.toml").write_text(re.sub(r'(?m)^"<cc-blind>" = "[^"]*"', f'"<cc-blind>" = "{tmp / "cc-blind"}"', (w / "intake" / "ROOTS.toml").read_text(), count=1)
                                             + f'\n"<l4>" = "{banks}"   # test_intake_loop4: the planted banks\n')
    (tmp / "cc-blind").mkdir()
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
    root = lambda i: re.findall(r'(?m)^root = "([^"]*)"', (w / "declarations" / i / "intake.toml").read_text())[0]
    s5i = lambda i: (cli("profile", i, root(i)), cli("lint", i), cli("seal", i, *SEAL), cli("run", i))[3][1]   # a declaration profiled (plan 1165), linted, sealed and run: what run printed
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
        at3 = s5i(declare(bank=b.name))   # plan 1165: the profile predicts each member's difference, so S3 refuses it first
        check(f"T34.1 (plan 1165) {member}: S3 refuses PROFILE_CONTRADICTED; the planted header name never prints",
              "**S3 SOURCE_INTEGRITY** (LIVE): EXECUTED, REFUSE PROFILE_CONTRADICTED" in at3 and PLANTED.decode() not in at3, (re.findall(r"- \*\*S3 [^\n]{0,400}", at3) or [at3[-300:]])[0])
        keep, A.against = A.against, lambda p, m, d: ()   # past a profile that predicts nothing (the seam: S3 reads intake_against.against at call time)
        out = s5i(declare(bank=b.name))
        A.against = keep
        line = S5(out)
        check(f"T34.1 (A34) {member}: S5 refuses FILE_DIFFERS_FROM_FIRST and names {member} and no other member (plan 1165: past a profile that predicts nothing)",
              "REFUSE FILE_DIFFERS_FROM_FIRST" in line and f"{member}: {intake_differs.DIFFERS.get(member, '?')}" in line
              and not [k for k in EDITS if k != member and f"{k}: " in line], line)
        check(f"T34.1 (A34) {member}: the planted header name never prints", PLANTED.decode() not in out, "printed")

    # ---- T42.1 (A42) / T43.1 (A43): peek by listing membership; cell and line counts
    raw = tmp / "cc-datasets" / "sp" / "raw"
    raw.mkdir(parents=True)
    (raw / "my run 1.csv").write_bytes(b"T,C\n1.5,0.25\n")
    (raw / "six.csv").write_bytes(b"temp in K, heat cap C\n1,2\n3,4\n5,6\n")
    RT = {"roots": {"<cc-datasets>": str(tmp / "cc-datasets")}}

    def peek(rel, *args):
        (w / "declarations" / "pk").mkdir(parents=True, exist_ok=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = intake_convert.peek_cli(w, "pk", [rel, *args], RT)
        return rc, out.getvalue()
    rc, said = peek("<cc-datasets>/sp/raw/my run 1.csv")
    check("T42.1 (A42) a file named with spaces is peeked", rc == 0 and "line 1: 2 text names" in said, said)
    outside = ["<cc-banks>/sp/raw/my run 1.csv", str(raw / "my run 1.csv"), "<cc-datasets>/sp/raw/../raw/my run 1.csv", "my run 1.csv"]
    said = [peek(rel)[1] for rel in outside]
    check("T42.1 (A42) another root, an absolute path, a '..' part and a bare name are each SOURCE_FILE_ABSENT", all("SOURCE_FILE_ABSENT" in x for x in said), "\n".join(said))
    (rc, said), (_, ws) = peek("<cc-datasets>/sp/raw/six.csv"), peek("<cc-datasets>/sp/raw/six.csv", "--delimiter", "WHITESPACE")
    check("T43.1 (A43) a 2-column file with a 6-token header: the shown line has 2 cells under COMMA, and the file's line count is 4",
          rc == 0 and "; 2 cells under COMMA" in said and "lines in the file: 4" in said, said)
    check("T43.1 (A43) --delimiter WHITESPACE: the same line has 6 cells under WHITESPACE (the 6 tokens)", "; 6 cells under WHITESPACE" in ws, ws)

    # ---- T41.1 (A41): the blinded view; a sentinel in the FILE NAMES never reaches an output
    SENT = "zzqBLIND4471"
    (banks / "sb").mkdir()
    [(banks / "sb" / f"curve_{SENT}_{k}.csv").write_bytes((banks / "pf" / f["name"]).read_bytes()) for k, f in enumerate(M["files"])]
    named = [f"curve_{SENT}_{k}.csv" for k in range(len(M["files"]))]
    ib = declare(bank="sb")
    said = [cli("blind", ib, "<l4>/sb", *named)]
    view = tmp / "cc-blind" / ib
    seen = sorted(p.name for p in view.iterdir()) if view.is_dir() else []
    blinded = lambda x: re.sub(r'(?m)^root = "[^"]*"', f'root = "<cc-blind>/{ib}"\nblinded_from = "<l4>/sb"\nkey_sha256 = "' + (re.findall(r"sha256 ([0-9a-f]{64})", said[0][1]) or ["?"])[0] + '"',
                                x.replace('kind = "DEPOSIT"', 'kind = "BLINDED"', 1), count=1)
    listed_ = lambda x: re.sub(r'(?m)^excluded = \[[^#]*\]', "excluded = []", re.sub(r'(?m)^files = \[[^\]]*\]', "files = " + json.dumps(seen), x, count=1), count=1)
    d = w / "declarations" / ib
    (d / "intake.toml").write_text(listed_(blinded((d / "intake.toml").read_text())))
    prof = cli("profile", ib, root(ib))   # plan 1165: the blinded view profiled before lint; its output joins the leak checks below
    said += [cli("lint", ib), cli("seal", ib, *SEAL), cli("run", ib), prof]
    check("T41.1 (A41) blind makes nine ordinal-named links and the key beside the view", said[0][0] == 0 and len(seen) == 9 and (tmp / "cc-blind" / f"{ib}.KEY.json").is_file(), said[0][1])
    check("T41.1 (A41) the BLINDED declaration lints, seals and runs, and passes S5", [s[0] for s in said[:3]] == [0, 0, 0] and "**S5 CENSUS** (LIVE): EXECUTED, PASS" in said[3][1],
          "".join(s[1][-300:] for s in said))
    wrote = {p.name: p.read_text(errors="replace") for p in d.iterdir() if p.is_file() and p.name not in ("intake.toml", "transducer.toml")}
    check("T41.1 (A41) the intake wrote a report, RESULT.json or SEAL.json, and the logs", {"SEAL.json", "access.log", "seal.log"} <= set(wrote) and [n for n in wrote if n.endswith(".md")] != [], str(sorted(wrote)))
    check("T41.1 (A41, leak) no output printed by blind, lint, seal or run holds the sentinel", not [s for s in said if SENT in s[1]], str([s[1][s[1].index(SENT) - 80:][:200] for s in said if SENT in s[1]]))
    check("T41.1 (A41, leak) no file the intake wrote holds the sentinel", not [n for n, x in wrote.items() if SENT in x], str([n for n, x in wrote.items() if SENT in x]))
    say = {**ic.ctables()["sentences"], **{r["code"]: r["sentence"] for r in ic.ctables()["blind_reason"]}}
    ref = lambda out: (re.findall(r": REFUSE (\w+)", out[1]) or ["PASS"])[0]
    (w / "declarations" / "bad id").mkdir()
    shm = Path("/dev/shm")
    PLANTS = {"BLIND_ID_REFUSED": lambda: cli("blind", "bad id", "<l4>/sb", named[0]), "ROOT_UNRESOLVED": lambda: cli("blind", declare(), "<nope>/sb", named[0]),
              "BLIND_NAME_REPEATED": lambda: cli("blind", declare(), "<l4>/sb", named[0], named[0]),
              "SOURCE_FILE_ABSENT": lambda: cli("blind", declare(), "<l4>/sb", named[0], f"curve_{SENT}_absent.csv"), "BLIND_VIEW_EXISTS": lambda: cli("blind", ib, "<l4>/sb", named[0])}
    two = shm.is_dir() and shm.stat().st_dev != (tmp / "cc-blind").stat().st_dev
    got = {k: f() for k, f in PLANTS.items()}
    with tempfile.TemporaryDirectory(dir={True: shm, False: None}[two]) as other:
        (Path(other) / f"curve_{SENT}.csv").write_bytes(b"T,C,sigma\n")
        (w / "intake" / "ROOTS.toml").write_text((w / "intake" / "ROOTS.toml").read_text() + f'"<l4shm>" = "{other}"\n')
        got |= {True: lambda: {"BLIND_NOT_ONE_DEVICE": cli("blind", declare(), "<l4shm>", f"curve_{SENT}.csv")}, False: dict}[two]()
    NOT_HERE = {True: [], False: ["BLIND_NOT_ONE_DEVICE"]}[two]
    print(f"  /dev/shm a second device here: {two}; NOT REACHED HERE: {NOT_HERE or 'none'}")
    for k, out in got.items():
        check(f"T41.1 (A41) {k} is refused by its plant, exit 1, and prints no selected name", ref(out) == k and out[0] == 1 and SENT not in out[1], out[1][-300:])
    check("T41.1 (A41) the codes reached are exactly the blind rows of CONVERSION.toml with ROOT_UNRESOLVED and SOURCE_FILE_ABSENT",
          set(got) | set(NOT_HERE) == {r["code"] for r in ic.ctables()["blind_reason"]} | {"ROOT_UNRESOLVED", "SOURCE_FILE_ABSENT"} and all(k in say for k in got), str(sorted(got)))
    nu = declare(lambda x: blinded(x).replace(f'root = "<cc-blind>/{ib}"', 'root = "<l4>/sb"', 1), "sb")
    lint_nu = cli("lint", nu)
    check("T41.1 (A41) a BLINDED root not under <cc-blind>/ is refused at S0 ROOT_NOT_UNDER_CC_BLIND", lint_nu[0] == 1 and "ROOT_NOT_UNDER_CC_BLIND" in lint_nu[1], lint_nu[1][-300:])

    # ---- T39 (A39): DOMAIN, the S9 split, PAIRS naming, S10 PROJECTION_EMPTY_ON_CURVE
    def grid(name, c, shift=lambda k: 0):
        """A bank of nine curves on T = 0..9 (curve k's T moved by shift(k)), C = c(k, T), sigma 0.1."""
        (banks / name).mkdir()
        [(banks / name / f"curve_{k:03d}.csv").write_text("T,C,sigma\n" + "".join(f"{T + shift(k)},{c(k, T)},0.1\n" for T in range(10))) for k in range(9)]
        (banks / name / "MANIFEST.json").write_text('{"planted": "test_intake_loop4"}\n')
        return name
    mono, peaked = grid("mono", lambda k, T: T + 0.1 * k), grid("peaked", lambda k, T: 10 - (T - 4.5 - 0.1 * k) ** 2)
    shifted = grid("shifted", lambda k, T: 10 - (T - 4.5 - 0.1 * k) ** 2, lambda k: 100 * (k == 4))
    PRIMARY_ARGMAX = lambda x: x.replace('bias = "MAX_MEASURED"', 'bias = "ARGMAX_FAST"', 1)
    line = lambda out, s: (re.findall(r"- \*\*" + s + r" [A-Z_]+\*\* \(LIVE\): [^\n]*", out) or [out[-300:]])[0]   # the stage's verdict line
    o1 = s5i(declare(ARGMAX_LANE, mono))
    check("T39.1 (A39) MONO, ALTERNATIVE ARGMAX_FAST: S9 refuses NO_INTERIOR_FAST_MAXIMUM, curves 9 of 9, its Next printed; S10 passes",
          "EXECUTED, REFUSE NO_INTERIOR_FAST_MAXIMUM" in line(o1, "S9") and "curves = 9; of = 9" in line(o1, "S9")
          and intake_feasible.NEXT["NO_INTERIOR_FAST_MAXIMUM"] in line(o1, "S9") and "EXECUTED, PASS" in line(o1, "S10"), line(o1, "S9") + " | " + line(o1, "S10"))
    i2, i2c = declare(PRIMARY_ARGMAX, mono), declare(PRIMARY_ARGMAX, peaked)
    o2, o2c = s5i(i2), s5i(i2c)
    check("T39.2 (A39.1) MONO, PRIMARY ARGMAX_FAST: S10 refuses PROJECTION_EMPTY_ON_CURVE, curves 9 of 9, and writes no RESULT.json",
          "EXECUTED, REFUSE PROJECTION_EMPTY_ON_CURVE" in line(o2, "S10") and "curves = 9; of = 9" in line(o2, "S10")
          and not (w / "declarations" / i2 / "RESULT.json").exists(), line(o2, "S10"))
    check("T39.2 (A39.1) PEAKED, PRIMARY ARGMAX_FAST (the control): S10 passes and RESULT.json is written",
          "EXECUTED, PASS" in line(o2c, "S10") and (w / "declarations" / i2c / "RESULT.json").is_file(), line(o2c, "S10"))
    o3 = line(s5i(declare(PAIR_LANE, shifted)), "S9")
    check("T39.3 (A39.3) SHIFTED, PAIR_NEAREST_FAST: S9 refuses ANCHOR_OUTSIDE_NEIGHBOUR_SPAN naming curve_003, curve_004, curve_005 once each in slow order, curves 3 of 9",
          "EXECUTED, REFUSE ANCHOR_OUTSIDE_NEIGHBOUR_SPAN" in o3 and re.findall(r"curve_\d{3}\.csv", o3) == ["curve_003.csv", "curve_004.csv", "curve_005.csv"]
          and "curves = 3; of = 9" in o3 and intake_feasible.NEXT["ANCHOR_OUTSIDE_NEIGHBOUR_SPAN"] in o3, o3)
    o4 = line(s5i(declare(PAIR_LANE, mono)), "S9")
    check("T39.4 (A39.1) MONO on the aligned grid, PAIR_NEAREST_FAST: S9 refuses NO_INTERIOR_FAST_MAXIMUM", "EXECUTED, REFUSE NO_INTERIOR_FAST_MAXIMUM" in o4, o4)
    ST = tomllib.loads((ROOT / "intake" / "STAGES.toml").read_text())
    rows = {s["id"]: [r["code"] for r in s["reason"]] for s in ST["stage"]}
    POL = tomllib.loads((ROOT / "intake" / "POLICY.toml").read_text())
    check("T39.5 (A39) DOMAIN total over POLICY's projections, ANCHOR and PAIRS over its bridges, NEXT over S9's rows; S9 holds the two rows; S10's PROJECTION_EMPTY_ON_CURVE before DOOR_REFUSED",
          set(intake_feasible.DOMAIN) == set(POL["projection"]) and set(intake_feasible.ANCHOR) == set(intake_feasible.PAIRS) == set(POL["bridge"])
          and set(intake_feasible.ANCHOR.values()) <= set(intake_feasible.DOMAIN) and rows["S9"] == list(intake_feasible.NEXT) == ["NO_INTERIOR_FAST_MAXIMUM", "ANCHOR_OUTSIDE_NEIGHBOUR_SPAN"]
          and rows["S10"].index("PROJECTION_EMPTY_ON_CURVE") < rows["S10"].index("DOOR_REFUSED"), str((sorted(intake_feasible.NEXT), rows["S9"], rows["S10"])))

print("test_intake_loop4: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
