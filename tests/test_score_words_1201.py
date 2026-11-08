"""test_score_words_1201 - plan 1201 AMENDMENT 1 (built in plan 1205 P2): the words of `bin/cc navigate score` (cc/scorewords.py). It reads no
real data. In-process checks call scorewords.lines on a constructed oracle (9 curves, a sharp line at sample rank 8 + 2k, the C'' Span) and a
navigator record; the CLI check runs `bin/cc navigate score` on test_navfamily's walking plant. Each check names its red mutation (seen FAIL):
 W1. Reach declares ATOMS and an Axiom, and every member NAME parses to its own atom (the binding rule's parser). Red: a member
     NOT_REACHED_BEYOND_WC added (it parses to the complement of REACHED_BEYOND_WC, two atoms).
 W2 (a). navigator_verdict is the navigator's, copied verbatim: a PARTIAL_IN_CORRIDOR record whose checkpoints are all REACHED_WITHIN_WC is
     still printed PARTIAL_IN_CORRIDOR and leads "PARTIAL trace". Red: lines() recomputes the verdict (FOLLOWED_IN_CORRIDOR when every
     checkpoint is REACHED_WITHIN_WC).
 W3 (b). NOT_REACHED is its own atom, never counted as BEYOND: a trace over curves 0..4 with a checkpoint on the line at curve 7 is
     NOT_REACHED, an off-line checkpoint at curve 2 is REACHED_BEYOND_WC; the summary is 1 / 1 / 1 and the sentence says "1 beyond w_c" and
     "1 not reached". Red: REACH[(False, False)] -> REACHED_BEYOND_WC.
 W4 (c). the word FOLLOWED (any case) appears only when the navigator's verdict is FOLLOWED_IN_CORRIDOR: absent from the output of every other
     verdict, present (as the lead "FOLLOWED trace") for it. Red: LEAD[PARTIAL_IN_CORRIDOR] -> "FOLLOWED trace (partial)".
 W5 (d). the word CRITICAL (any case) appears in no score output of any verdict, and in no navigate golden. Red: "the suspect line's" ->
     "the critical line's".
 W6. the typed fields are present: traced_slow_range and suspect_slow_range in the slow unit; the census names its curves (rank (slow) per
     kind); the sentence names where each direction stopped (its terminal, the nearest curve and the next curve beyond it). Red: census_named
     returns the bare counts (o.census()).
 W7. the CLI golden tests/navigate/score-plant.txt (the walking plant, checkpoints on the line) is reproduced byte for byte (CC_REGOLDEN=1
     rewrites it), and its `score:` line still has the shape plant1201.py's C3/C4 parse (`^score: (\\d+) of (\\d+) checkpoints within`).
     Red: the score line reworded "score: N checkpoints of M within"."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, parse  # noqa: E402
bootstrap(ROOT, "cc", "tests")
import intake_feature as F  # noqa: E402
import intake_synth  # noqa: E402
import linenav  # noqa: E402
import scorewords as W  # noqa: E402
from intake_plant import long_table, write_long  # noqa: E402

GOLD = ROOT / "tests" / "navigate" / "score-plant.txt"
REGOLDEN = os.environ.get("CC_REGOLDEN") == "1"
V = linenav.Verdict


# ---- W1 the enum name
m = re.search(r"ATOMS: ([A-Z_\s|]+?)\.", W.Reach.__doc__ or "")
atoms = set(re.sub(r"\s", "", m[1]).split("|")) if m else set()
check("W1. Reach declares ATOMS and an Axiom, and its members are exactly the atoms", bool(atoms) and "Axiom" in W.Reach.__doc__ and {x.name for x in W.Reach} == atoms)
check("W1. every Reach name parses to its own atom alone", all(parse(x.name, atoms) == {x.name} and x.value == x.name for x in W.Reach),
      str([x.name for x in W.Reach if parse(x.name, atoms) != {x.name}]))

# ---- the constructed oracle: 9 curves (slow 0.1 .. 0.9), 40 samples (T = 1 .. 40), curve k's peak at sample rank 8 + 2k
K, N = 9, 40
SLOWS = tuple(round(0.1 * (k + 1), 1) for k in range(K))
O = F.Oracle(tuple(F.Located(N, 8 + 2 * k, 8 + 2 * k, 8 + 2 * k, "COLUMN") for k in range(K)), SLOWS, tuple(tuple(1.0 + j for j in range(N)) for _ in range(K)),
             F.Span((0.1, 1.0), (0.8, 39.0)), linenav.FiniteStored("plant:UNSEALED"), linenav.Side)
ON = lambda k: O.span.u((SLOWS[k], 9.0 + 2 * k))   # noqa: E731  the line's point on curve k (span units)
REC = {"dirs": {-1: {"term": linenav.FiniteTerm.EDGE}, 1: {"term": linenav.FiniteTerm.CONTOUR_EDGE}}}
FULL = [ON(k) for k in range(K)]
SUS = [O.span.u((SLOWS[0], 9.0)), O.span.u((SLOWS[-1], 25.0))]   # the suspect is held in span units (navfamily)


def say(verdict, path=FULL, cps=(ON(1), ON(4), ON(7))):
    return "\n".join(W.lines("plant", verdict, O, REC, path, list(cps), SUS, 0.15, "kbar", "COLUMN", "UNTESTED"))


# ---- W2 (a)
out = say(V.PARTIAL_IN_CORRIDOR)
check("W2 (a). a PARTIAL_IN_CORRIDOR record with 3 of 3 REACHED_WITHIN_WC prints navigator_verdict PARTIAL_IN_CORRIDOR and leads PARTIAL trace",
      "navigator_verdict PARTIAL_IN_CORRIDOR (the navigator's, copied)" in out and "sentence: PARTIAL trace (navigator verdict PARTIAL_IN_CORRIDOR)" in out
      and "checkpoints_summary: REACHED_WITHIN_WC 3, REACHED_BEYOND_WC 0, NOT_REACHED 0" in out, out)

# ---- W3 (b)
out = say(V.PARTIAL_IN_CORRIDOR, FULL[:5], (ON(1), O.span.u((SLOWS[2], 30.0)), ON(7)))
check("W3 (b). on the line inside the trace WITHIN, off it BEYOND, on the line past the trace NOT_REACHED; summary 1 / 1 / 1",
      [ln.split("-> ")[-1] for ln in out.splitlines() if ln.startswith("  checkpoint")] == ["REACHED_WITHIN_WC", "REACHED_BEYOND_WC", "NOT_REACHED"]
      and "checkpoints_summary: REACHED_WITHIN_WC 1, REACHED_BEYOND_WC 1, NOT_REACHED 1" in out, out)
check("W3 (b). the sentence counts 2 of 3 reached, 1 within, 1 beyond and 1 not reached; the score line counts 1",
      "2 of 3 checkpoints reached, 1 within w_c and 1 beyond w_c" in out and "1 not reached" in out and "\nscore: 1 of 3 checkpoints within w_c 0.15" in out, out)
check("W3 (b). the traced slow range (0.1 -> 0.5 kbar) is printed beside the suspect's (0.1 -> 0.9 kbar)",
      "traced_slow_range: 0.1 -> 0.5 kbar" in out and "suspect_slow_range: 0.1 -> 0.9 kbar" in out, out)

# ---- W4 (c), W5 (d)
outs = {v: say(v) for v in V}
outs[V.INDETERMINATE] = say(V.INDETERMINATE, [])
check("W4 (c). no FOLLOWED (any case) in the output of any verdict but FOLLOWED_IN_CORRIDOR",
      all(not re.search(r"(?i)followed", o) for v, o in outs.items() if v is not V.FOLLOWED_IN_CORRIDOR),
      str([(v.name, re.findall(r"(?i).{30}followed.{10}", o)) for v, o in outs.items() if v is not V.FOLLOWED_IN_CORRIDOR and re.search(r"(?i)followed", o)]))
check("W4 (c). FOLLOWED_IN_CORRIDOR leads \"FOLLOWED trace\"", "sentence: FOLLOWED trace (navigator verdict FOLLOWED_IN_CORRIDOR)" in outs[V.FOLLOWED_IN_CORRIDOR])
check("W5 (d). no CRITICAL (any case) in the score output of any verdict", not any(re.search(r"(?i)critical", o) for o in outs.values()),
      str([re.findall(r"(?i).{30}critical.{10}", o) for o in outs.values()]))
check("W5 (d). the INDETERMINATE record (no trace) has every checkpoint NOT_REACHED and says no line was traced",
      "checkpoints_summary: REACHED_WITHIN_WC 0, REACHED_BEYOND_WC 0, NOT_REACHED 3" in outs[V.INDETERMINATE] and "traced_slow_range: none (no line traced)" in outs[V.INDETERMINATE],
      outs[V.INDETERMINATE])

# ---- W6 the named census and the stops
out = say(V.PARTIAL_IN_CORRIDOR, FULL[2:6])
check("W6. the census names its curves: Located 9: 0 (0.1), 1 (0.2), ..., 8 (0.9); the other kinds none",
      "census: Located 9: 0 (0.1), 1 (0.2), 2 (0.3), 3 (0.4), 4 (0.5), 5 (0.6), 6 (0.7), 7 (0.8), 8 (0.9); Broad 0: none; AtSpanEnd 0: none; Absent 0: none" in out, out)
check("W6. the sentence names where each direction stopped: backward at curve 2 (next 1), forward at curve 5 (next 6), with the terminals",
      "backward stopped at 0.3 kbar (terminal EDGE; nearest curve rank 2, Located, 0.3 kbar; next curve rank 1 (Located, 0.2 kbar))" in out
      and "forward stopped at 0.6 kbar (terminal CONTOUR_EDGE; nearest curve rank 5, Located, 0.6 kbar; next curve rank 6 (Located, 0.7 kbar))" in out, out)
check("W6. a trace to the family's last curve says no curve beyond", "no curve beyond (the family's end)" in say(V.FOLLOWED_IN_CORRIDOR))


# ---- W7 the CLI golden (test_navfamily's walking plant: 12 curves, peak at 8 + 2k)
def rows(p, n=40):
    return [f"{1.0 + j:.4f},{10.0 / (1 + (j - p) ** 2):.4f},0.0300" for j in range(n)]


def cli():
    hs = [round(0.1 * (k + 1), 1) for k in range(12)]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        w, banks = tmp / "cc", tmp / "banks"
        shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
        with (w / "intake" / "ROOTS.toml").open("a") as f:
            f.write(f'\n"<score-test>" = "{banks}"   # test_score_words_1201: the planted bank\n')
        intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
        m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
        cc = lambda *a: (lambda r: (r.stdout + r.stderr, r.returncode))(subprocess.run([sys.executable, str(w / "bin" / "cc"), *a], capture_output=True, text=True, cwd=w))  # noqa: E731
        (banks / "plant").mkdir()
        write_long(banks / "plant", [(h, rows(8 + 2 * k)) for k, h in enumerate(hs)])
        d = w / "declarations" / "plant"
        d.mkdir()
        text = (long_table(m, "plant").replace("<long-test>/pf", "<score-test>/plant") + '\n[plane]\naxes = "slow-fast"\n'
                + f'\n[suspect]\nvertices = [[{hs[0]}, 9.0], [{hs[-1]}, 31.0]]\ncorridor = "continuous"\n')
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text(intake_synth.declare(m, "plant", "pf")[2])
        cc("intake", "profile", "plant", re.findall(r'^root = "([^"]*)"', text, re.M)[0])
        held = tmp / "held-out" / "checkpoints.toml"
        held.parent.mkdir()
        held.write_text(f"points = [[{hs[0]}, 9.0], [{hs[5]}, 19.0], [{hs[-1]}, 31.0]]   # on the planted line (rank 8 + 2k)\n")
        out, rc = cc("navigate", "score", "plant", str(held))
        text = f"$ bin/cc navigate score plant <held-out>/checkpoints.toml\n{out.replace(str(tmp), '<tmp>')}exit {rc}\n"
        {True: lambda: GOLD.write_text(text), False: lambda: None}[REGOLDEN]()
        check("W7. the score of the walking plant equals the golden tests/navigate/score-plant.txt", GOLD.is_file() and text == GOLD.read_text(),
              "\n".join(ln for ln in text.splitlines() if ln not in (GOLD.read_text().splitlines() if GOLD.is_file() else []))[:600])
        sc = re.findall(r"^score: (\d+) of (\d+) checkpoints within", out, re.M)
        check("W7. the score line keeps the shape C3/C4 parse, and reads 3 of 3", sc == [("3", "3")] and rc == 0, out[-500:])
        check("W5 (d). no CRITICAL (any case) in this score output", not re.search(r"(?i)critical", out), out[-300:])


try:
    cli()
except Exception as e:   # a crash is a named FAIL, never a silent pass
    check("W7. the CLI check runs to the end", False, repr(e)[:300])
for g in sorted((ROOT / "tests" / "navigate").glob("*.txt")):
    check(f"W5 (d). no CRITICAL (any case) in the navigate golden {g.name}", not re.search(r"(?i)critical", g.read_text()), g.name)
print(f"{len(bad)} failed" if bad else "test_score_words_1201: all passed")
sys.exit(1 if bad else 0)
