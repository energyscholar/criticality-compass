# Criticality Compass (CC)

CC reads what was measured at a set of points and says, by a rulebook you can edit, what each reading supports, or `BLANK` and why.

What CC cannot do, and why that is the point:

- It cannot fill a gap: a point that was not measured prints `BLANK` with its reason, never a guess ([where that is enforced](docs/READING-THE-CODE.md)).
- It cannot change a stored result: a frozen result and every file it read are read-only and hash-checked, and you fork to change one ([how the freeze works](docs/READING-THE-CODE.md)).
- It cannot hide a rule: every possible signature row falls in exactly one row of the verdict table, and each row says why ([the table, row by row](docs/READING-THE-CODE.md)).
- It cannot vouch for its own checks: the suite plants faults to see each check fail, and finding one it misses is a welcome report ([try to break it](docs/try-to-break-it.md)).

## Install

From a clone, with Python 3.11 or later (`<the repository>` is filled in when the repository is published):

```
git clone <the repository> criticality-compass && cd criticality-compass
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

Code: Apache-2.0 (`LICENSE`, `NOTICE`). Data in `benchmark/` and `results/`: CC BY 4.0 (`DATA-LICENSE`). How to cite: `CITATION.cff`.

CC reads what was measured at a set of points, codes each reading by where its interval sits against
declared margins, and looks the codes up in a rulebook you can edit. When something was
not measured, or the interval cannot decide between two codes (the cell `UNRES`, `cc/sign.py:19`), CC prints `BLANK` and says why. The cases (what each model is
supposed to be) and the rulebook (which codes mean which verdict) are plain TOML files. You change them by
editing data, never code, and every old result stays readable after you do.

The code that `compass hold` runs is written in an unusual style, on purpose; `docs/READING-THE-CODE.md` explains it and says where it is only convention.

To run a system by hand, start with "Run a system by hand" below. For the rulebook, start with the first hour. `TUTORIAL.md` walks one point
from data to verdict, `HOWTO.md` covers the weekly loop and the advanced commands, and `KERNEL-IN-CC.md`
explains what the instruments compute.

## Run a system by hand (`compass hold`)

`compass hold` runs one hold of a catalogue system: a needle steers a dial on a simulated system served over the apparatus wire, and the run is scored against the
server's truth. It prints the input it resolved, the needle's progress, and the scored output, and it saves the run as a record (a directory) you can check later.
`man compass` has the full page; the page is `docs/man/compass.1` in a clone and `<prefix>/share/man/man1/compass.1` in an installed wheel.

```
$ compass hold --list
ising  production  needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus.toml)
ising  static      needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-static.toml)
ising  static-r2   needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-static-r2.toml)
ising  static-r3   needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-static-r3.toml)
ising  field       needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-field.toml)
ising  field-hard  needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-field-hard.toml)
at     production  needles: settled mid settled-off mid-off mid-null   (system-instantiated/plugins/at/at-apparatus.toml)
at     static      needles: settled mid settled-off mid-off mid-null   (system-instantiated/plugins/at/at-apparatus-static.toml)
fhn    pending     not in this release
```

No hold mode is the default: a missing `--needle` is REFUSED (exit 2) and names the needles the system has. Run one (Ising, production world, the `settled` needle; this
output was captured from a run that took 284 s on an 8-core machine at 1-minute load 13 falling to 8.6; the `RUN` lines are one per step, 53 in all):

```
$ compass hold ising production --needle settled
INPUT
  system ising  world production  needle settled  seed 500 (from the world file)
  world  system-instantiated/plugins/ising/ising-apparatus.toml  sha256 93587cb627b5
  world params: kind=critical L_blocks=27 seed=500 horizon=200000 dials=[{'name': 'K', 'lo': 0.42, 'hi': 0.545, 'T': 500, 'max_nudge': 32, 'start': 0} …
  needle needle-settings/ising/hold-settled.toml  sha256 c2159cac0b3e
  needle params: needle_structure=hold-pair-v1 g=12 step=6 S=1500 n_eq=450
  score  environment/hold-score-ising.toml  sha256 158dbcc14f0e
  score params: offset_K=-0.005 out_run=3 plan=1569
  code   compass 0.1.0  git not-a-clone  digest c191ac11415e
RUN step 1 phase ignite index 5100  t=5s
…
RUN step 53 phase hold index 198426  t=164s
OUTPUT
  outcome=HORIZON lock=HELD in_fraction=0.9583333333333334 rms_e_g=0.48005523022349245 mean_e=-4.748954039085869 hold_steps=48 accuracy=0.5625  run_id=34d021cf86b5547e
record: 20261122T145559Z-ising-production-34d021cf86b5547e-24ac
exit 0: scored  (status scored)
```

The record is `compass-runs/<time>-ising-production-<run id>-<4 hex>/` under the directory you ran in (`--out DIR` or `COMPASS_RUNS` move it). It holds `run.json` (what was
run, with which code, the status, a summary of the score, the sha256 of every file), `run.json.sha256`, `terminal.txt` (what was printed), `input/` (the exact files the run read)
and `run/` (what the orchestrator wrote). Every path in it is relative to the record. Two identical runs leave two records. `compass hold --verify RECORD` recomputes the hashes
and names every file that is missing, differs or is not listed (exit 1), or prints `verified: every file matches run.json` (exit 0).

An installed wheel runs the same command from any directory and writes only under the current directory. Build and install one (measured with `--no-deps`, numpy already importable):

```
$ python3 -m pip wheel --no-deps --no-build-isolation -w dist .
$ python3 -m venv hold-venv && hold-venv/bin/python -m pip install dist/criticality_compass-*.whl
```

The rulebook commands in the rest of this document (`show`, `explain`, `run`, `validate`, ...) are a second surface of the same tool, unchanged. `run`, `check` and `freeze` need
the external structure checker named under "The first hour".

## Glossary (14 terms)

1. **input**: a directory `inputs/<id>/` holding `m.toml` (what was measured and how: Kernel V8's M) and `points.toml`.
2. **point**: one labelled place in parameter space, e.g. `"0.07"` or `"d2.0-K1.0"`, with a list of sizes.
3. **instrument**: one measurement (needle, across, stability, two_start, along, fluct). It takes ordered differences over a declared comparison (the size chains, the matched block levels, the two starts), inside a projection C; `along` also reads one edge of the declared control relation (an external verifier, 2026-10-06).
4. **comparison / relation**: declared nodes and directed edges. A comparison (a size chain, a start pair, matched levels) relates independently observed values through the declared blocking map and claims no provenance; a relation (the control edge between neighbouring points, pending an external verifier (ruling R2)) is a kernel declaration. The difference along each edge is source minus target (the kernel's A arithmetic); `explain` labels step 3 COMPARISON or RELATION.
5. **reading**: an estimate plus its resampled interval, and its **sign cell**: where the interval sits among the cuts -eps, 0, +eps (SIG+, POS, SLOW+, ZERO!, SLOW-, NEG, SIG-, UNRES).
6. **code**: a sign cell translated by `codes.toml` into words, e.g. SIG+ becomes RELEVANT.
7. **signature row**: the six codes of one point: needle, sink, flow, across, stability, two_start.
8. **table set** (rulebook): a directory `tables/<name>/` holding `codes.toml` and `verdict.toml`.
9. **verdict**: the output of the row of `verdict.toml` that contains the signature row. The rows partition every possible row, and each row has a `why`.
10. **BLANK**: CC does not know (not measured, not evaluated, unresolved, or a refusal). The brackets give the exact reason.
11. **case**: taxonomy (`cases/<id>.toml`, holding the true class). `points.toml` maps points to cases and is never frozen.
12. **frozen**: a result, and every file it read, made read-only and hash-checked. To change a frozen thing you fork it.
13. **geometry**: what the flow says (point, line, walking, ...), read from needle, flow, across and stability only. A rulebook with `geometry.toml` (`v02-rules`) prints it beside the verdict.
14. **order**: whether the two starts agree at the window, and what the fluct witness says when they do (coexist, continuous, first-order tunnelling, off the window, ...), read from needle, two_start and fluct only (`order.toml`). `compose.toml` turns (geometry, order) into the verdict, and `validate` proves it gives `verdict.toml`'s verdict on every row.

## The first hour

For a first hour from `pip install criticality-compass` (no clone), see `docs/FIRST-HOUR.md`. The steps below start from a clone.

Install once, from a clone (the clone is the workspace: results, tables and inputs live beside the code, so the install is editable):

```
$ git clone <the repository> criticality-compass && cd criticality-compass
$ python3 -m venv .venv && . .venv/bin/activate
$ pip install -e .
$ compass help
```

You need Python >= 3.11 (3.12 is the version tested) and numpy and scipy, which `pip install -e .` brings. `compass` is the console script; it runs this clone's `bin/cc` in the venv's interpreter, and `bin/cc` starts every script and test with that same interpreter (`sys.executable`). Called directly, `bin/cc` runs under whichever `python3` your PATH gives it, so activate the venv first. Run everything below from the repository root.

Two places are never defaults, because a default would be one person's machine: **the data** (the simulation outputs live outside the repository; name them with `--data-root PATH` or `CC_DATA_ROOT=PATH`, else CC looks only in the clone's `data/`, which holds the redistributable l8 files) and **the structure checker** that `run`, `check` and `freeze` call (`CC_STRUCTURE_CHECKS=<directory that holds checks.py>`; without it those commands REFUSE and say so). Every stored data path starts with the name `<data-root>` (cc.toml `[data] name`), which is a name, never a location.

Other ways to install:

- **A non-editable install** (`pip install .`, or a built wheel from `python3 -m build`) carries a copy of the workspace (`bin/`, `cc/`, `tables/`, `inputs/`, `cases/`, `results/`, `data/`, `docs/`, `benchmark/`, `environment/`, `needle-settings/`, `manual/`, ...) inside the package, so `compass validate`, `compass show`, `compass explain` and `compass family` work without a clone (given the data root and the structure checker above); `compass tabulate` writes into the workspace, so it is for a clone only. Of `tests/` it carries only the files `FROZEN.json` names, which the structure gate needs; `compass check` and `compass test` REFUSE there and say to use a clone. Anything you write (`run`, `new`, `tables fork`) lands in that copy inside site-packages and is lost on reinstall; to author, use the editable install above. `compass --help` and `compass help` both print the help text; an unknown command exits non-zero.
- Python 3.11 is the minimum and works; 3.12 is the version most tested.

## The Rust kernel (optional)

Measurement runs the Python `cc/kernel.py`, which is the reference. The Rust kernel (`kernel_rs`, the pinned `abr-kernel`) is used only by the tests `test_kernel_rs` and `test_kernel_rs_bitwise`, which check that it equals the Python one. It is not a dependency or an extra of this package and it is **not on any package index**: build the wheel yourself (the test environment is `pip install -e .[test]` plus that wheel).

```
$ pip install maturin
$ maturin build --release -m rust/Cargo.toml     # needs rustup/cargo on PATH
$ pip install rust/target/wheels/criticality_compass_kernel-*.whl
```

The build needs a Rust toolchain (`cargo`; rustup puts it in `~/.cargo/bin`, which may not be on `PATH`) and **network access**: the crate pulls `metatron_kernel_v8` by git URL at a pinned revision from GitHub, so that repository must be reachable. Without the wheel the two kernel tests print `kernel_rs is not installed` with the steps above, and everything else is unaffected.

The repository also holds a prebuilt `cc/_ext/kernel_rs.so` (SHA256 beside it). It is an **x86-64 Linux ELF only**; on macOS or ARM it will not import, and you build the wheel instead. A non-editable install does not carry it.

## Benchmark data outside the repository

`bin/cc bench verify` checks `benchmark/MANIFEST.toml` (hashes of every file the benchmark rows used). The files under `results/`, `inputs/` and the like are in the repository; the simulation outputs (for example the `nav-m7-bank` and `nav-m7-grid` `.npz` files) are not: they live in a data root outside it. Point CC at it with `bin/cc --data-root <dir> bench verify` (the declared name is in `cc.toml` `[data]`). Without that data, `bench verify` reports those rows as ABSENT and exits 1; that is expected for a clone and says nothing about the files that are present.

### 1. Ask for help

(Plain `bin/cc`, `compass --help` and `compass -h` print the same text.)

```
$ bin/cc help
cc - Criticality Compass   (BASIC; `bin/cc help --advanced` lists every command)

  bin/cc show <input>                   every reading of an input, and each point's verdict (a declared report)
  bin/cc explain <input> <point>        the whole chain for one point: data -> verdict (a declared report)
  bin/cc run <input> | --all [--dry]    measure under the working rules; verdicts are declared reports (--dry writes nothing)
  bin/cc new case <id>                  start a case file (taxonomy) from the template
  bin/cc tables fork <from> <to>        copy a rulebook so you can edit it
  bin/cc tables drop <set>              delete a rulebook you no longer want
  bin/cc validate                       check every file; each problem says what to do next
  bin/cc check                          validate + tests + scoreboard; run it before a commit
  bin/cc hold <system> <world> --needle M  run a system by hand; the run is saved as a record (bin/cc hold --list)
  bin/cc navigate <input>               UNTESTED: walk a stored map (stored-map mode only); every line it prints is untested

…
rules in use: v01-rules   (cc.toml [defaults] tables)
BLANK (...) means "CC does not know"; the word in brackets says why.

start: bin/cc show b7-at-line
```

### 2. Look at an input

```
$ bin/cc show b7-at-line
b7-at-line   rules: v01-rules   result: results/b7-at-line@v01-rules.json (frozen)
report: declared report — a projection C over sign cells of declared comparisons (the blocking-map comparison of independent sizes; the two-start difference), not a relational reading (an external verifier, 2026-10-06)
point 0.0   case at-self-dual-line
  sink       BLANK (NOT-MEASURED: needle is not declared on this input)
  needle     BLANK (NOT-MEASURED: needle is not declared on this input)
  flow       BLANK (NOT-MEASURED: needle is not declared on this input)
  across     1.009 [0.9764, 1.045] SIG+ -> RELEVANT
  stability  0.01661 [-0.03909, 0.07487] ZERO! -> STABLE
  two_start  BLANK (NOT-MEASURED: two_start is not declared on this input)
  => verdict BLANK (REFUSE-NEEDLE-UNMEASURED)
     why: honest null (not in verdict_x): the needle was not measured or not evaluated
…
```

One block per point. Each line is one instrument: the estimate, its interval in square brackets, the sign
cell, then `->` and the code. The last two lines are the verdict and the rulebook's reason for it.

### 3. Read one block

`BLANK (NOT-MEASURED: needle is not declared on this input)` means CC does not know the needle at this point,
because this input never measured it. That is not an error and not a zero: a missing measurement is a value
CC carries all the way to the verdict. Other BLANKs you will meet: `UNRES` (the interval straddles zero and a
margin edge, so the data cannot say which side) and a refusal such as `REFUSE-NEEDLE-UNMEASURED` (the rulebook
declines to give a class). Here the verdict is a refusal because the rulebook needs the needle before it will
name any class.

### 4. Ask why

```
$ bin/cc explain w2-potts 5
explain w2-potts 5   rules: v01-rules
sink       BLANK (NOT-MEASURED: needle is not declared on this input)
…
across
  1 DATA      w2/q5-L27-random.npz [G key G, E key E] ... 3 blocks; sha256 matches fixtures/data/w2-potts.toml
  2 REDUCE    row 0: 27 14.42, 81 83.45, 243 527.7
  3 COMPARISON size: chain, declared report   27 <- 81 <- 243
  4 C         operator A over size; row 0: y_steps [1.598, 1.679]; y_last [1.679]
  5 READING   y_last 1.679  interval [1.417, 1.932]  (95 %, 400 block resamples, b 400)
  6 SIGN      cuts -0.25 0 +0.25 (eps y): bL 3, bU 3 -> SIG+
  7 CODE      across: codes.toml line 107: SIG+ -> RELEVANT
…
8 VERDICT   verdict.toml line 153: when.needle = [NOT-MEASURED, NOT-EVALUATED]
            => verdict BLANK (REFUSE-NEEDLE-UNMEASURED)
               why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

`explain` prints the whole chain for one point, from the data files (with their hashes checked) to the
verdict. The last section names the rulebook file and line that decided: `verdict.toml line 153`.
`TUTORIAL.md` reads this output section by section.

### 5. Open that line

Open `tables/v01-rules/verdict.toml` in Geany and go to line 153. That `[[row]]` is the rule that
decided: its `when` lines say which codes it covers, `verdict` is the answer, `why` is the reason printed
above. You cannot edit it, because it is frozen; the next step makes a copy you can.

### 6. Fork the rulebook

```
$ bin/cc tables fork v01-rules my-rules
forked tables/v01-rules to tables/my-rules
  Next: edit tables/my-rules/verdict.toml, then bin/cc validate, then bin/cc run --all --tables my-rules
```

### 7. Change one row

In `tables/my-rules/verdict.toml`, find the row for `when.needle = ["NOT-MEASURED", "NOT-EVALUATED"]` and
change `verdict = "REFUSE-NEEDLE-UNMEASURED"` to `verdict = "NOT"`. Save. (The order of rows does not matter:
the rows are a partition of every possible signature row, and `validate` checks that none overlap and none are missing.)

### 8. Validate

```
$ bin/cc validate

l8-tetris-600: refused as declared (5 sentences)
l8-tetris-600-g: refused as declared (5 sentences)
validate: clean
```

If a row were wrong, each finding would end with a `Next:` line saying what to do.

### 9. Try it without writing anything

```
$ bin/cc run w2-potts --tables my-rules --dry
run w2-potts@my-rules
w2-potts   rules: my-rules   result: results/w2-potts@my-rules.json (dry: nothing written)
report: declared report — a projection C over sign cells of declared comparisons (the blocking-map comparison of independent sizes; the two-start difference), not a relational reading (an external verifier, 2026-10-06)
…
point 5   case potts-q5
  sink       BLANK (NOT-MEASURED: needle is not declared on this input)
  needle     BLANK (NOT-MEASURED: needle is not declared on this input)
  flow       BLANK (NOT-MEASURED: needle is not declared on this input)
  across     1.679 [1.417, 1.932] SIG+ -> RELEVANT
  stability  0.08076 [-0.3098, 0.5382] BLANK (UNRES: interval straddles 0 and a margin edge)
  two_start  BLANK (UNRES: interval straddles 0 and a margin edge)
  => verdict NOT
     why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

The readings are the same as before; only the verdict moved, from a refusal to `NOT`. That is the point of the
split: instruments measure, the rulebook decides, and the rulebook is yours. (The old `why` line stays until
you edit it too. Write your own reason when you keep a change.)

### 10. Throw it away

```
$ bin/cc tables drop my-rules
dropped tables/my-rules
```

## Navigating a stored map (UNTESTED)

```
bin/cc navigate b7-at-line-ch
```

walks a **stored map**: an input whose `[interval] method` is `chains` (m independent chains per point and size, format `npz-v1`,
`arrays.G` on every chain file). It reads the two end points, and, when the first reads disordered and the last ordered, bisects
between them, reading one point at a time with the navigator v2 needle (L 81 against L 27, m chains, order-statistic interval, margin
0.01). It reads only stored points, only the ones the walk visits, and appends one line per chain file read to an access log
(`results/navigate/<input>.access.jsonl`, or `--access-log PATH`).

**This verb ships untested.** Every line it prints starts under a first line that says so; no transcript is evidence of a located
transition. Its outcomes are values: BRACKET (two adjacent points), STOP (a point read inside the margin), UNRESOLVED (a point whose
interval straddles 0 and the margin edge: no location is claimed), NOT_ESTABLISHED (fewer than m chains stored), REFUSE (the end points
do not read disordered then ordered). An input that is not a stored map is refused (`REFUSED NOT_A_STORED_MAP`, exit status 1).
`docs/navigate.md` holds the design, the predictions committed before the first run, and the one change from the navigator it ports.

## What v0.1 can and cannot say

Twelve inputs are scored under the default rulebook (`v01-rules`), 79 points. Positive verdicts do exist on real
data now. `x5n-bilayer`, the coupled Ising bilayer at its confirmed-stop critical point, reads **POINT** at all
three of its points (needle MID, flow STOPPED, across RELEVANT, stability STABLE, two starts INDEP):

```
point 0.0   case coupled-ising-bilinear
  needle     velocity -0.00244 [-0.007564, 0.001852] ZERO! d_ord 0.2411 [0.2383, 0.2449] SIG+ d_dis 0.7589 [0.7551, 0.7617] SIG+ -> MID
  flow       -0.00244 [-0.007564, 0.001852] ZERO! -> STOPPED
  across     0.9846 [0.9309, 1.051] SIG+ -> RELEVANT
  stability  -0.04351 [-0.1291, 0.06495] ZERO! -> STABLE
  two_start  INDEP
  => verdict POINT
     why: verdict_x CAND_GS: relevant and stable
```

(Transcript of `bin/cc run --all`, point 0.0 of `x5n-bilayer`; 0.1 and 0.3 read POINT the same way.) A second
kind of positive verdict belongs to a **family**, not a point: the points of `b7-at-line-2` taken together read LINE
(`bin/cc family b7-at-line-2`, `TUTORIAL.md` part 3). LINE, WALKING and FIRST-ORDER still appear in no real
per-point result: the other 76 points give NOT or a refusal, and only synthetic test cases reach those rows.
`HOWTO.md` ("Known limits of v0.1") says what the family verdict means. Under `v05-rules` a family can also read where a line **ends**
(`bin/cc family x2b-xy --tables v05-rules`, `TUTORIAL.md` part 5, HOWTO "LINE-END families"): `lower` and `upper` name each side of the interior
and its end kind, and the end is reported as a bracket (`end_bracket`), not a point.

## Before you commit

```
bin/cc check
```

runs `validate`, every test and the scoreboard, and takes several minutes (about seven). In a fresh clone, run
`git config core.hooksPath .githooks` once, so that a quicker version of the same check runs for you before
every commit.

The tests need the test extra, and two of them the kernel wheel: `pip install -e .[test]` and the kernel wheel, which is built by hand (see "The Rust kernel").

## Acknowledgements

The ABR relational-kernel method that CC computes with is credited to Robin Macomber and Metatron Dynamics, Inc. / Relational Relativity Corp. `cc/kernel.py` is a Python port of their `abr-kernel` (`metatron_kernel_v8`), licensed Apache-2.0, and the Rust binding `kernel_rs` (`rust/`) uses the same crate at a pinned revision. `NOTICE` gives the revision and the changes, and `CITATION.cff` the reference; if you use CC, please cite the kernel as well. Why CC computes this way, and how to read its code, is in `KERNEL-IN-CC.md` ("Why CC uses relational math") and `docs/READING-THE-CODE.md`.

## Adding a case

A case is taxonomy: what a model is supposed to be.

```
$ bin/cc new case potts-q4
wrote cases/potts-q4.toml
  Next: fill every TODO in cases/potts-q4.toml, map points to it in inputs/<input>/points.toml, then bin/cc validate
```

Open `cases/potts-q4.toml` and replace every `TODO` (validate names each one that is left). Then open
`inputs/w2-potts/points.toml` and change `"4" = "none"` to `"4" = "potts-q4"`. Run `bin/cc validate`. No result
changes, because no result names a case; `bin/cc show w2-potts` now prints the new case beside point 4.

## Where things live

| file or folder | what it holds | who edits it | frozen? |
|---|---|---|---|
| `cases/<id>.toml` | taxonomy: the true class of a model, its traps, its sources | you | never |
| `inputs/<id>/points.toml` | which case each point belongs to | you | never |
| `inputs/<id>/m.toml` | what was measured and how: files, sizes, relations, margins, resampling | you, when you add an input | once a result read it |
| `fixtures/data/<id>.toml` | the sha256 of each data file an input reads | `bin/cc data add` | once a result read it |
| `inputs/<id>/couplings.toml` | the sampler's couplings (from the Hamiltonian) and which of them `across` probes; read by `v04-rules` (HOWTO, "Probe completeness") | you, when you add an input | once a result read it |
| `instruments/*.toml` | what each instrument measures and its pipeline | the maintainers | once a result read it |
| `tables/<set>/codes.toml` | sign cell to code, per column | you, in a forked set | with its set |
| `tables/<set>/verdict.toml` | the rows that map a signature row to a verdict | you, in a forked set | with its set |
| `tables/<set>/probe.toml` | `v04-rules`: the projection of the geometry by the declared probe (a positive geometry with an unprobed coupling is a named refusal) | you, in a forked set | with its set |
| `tables/<set>/membership.toml` | which needle codes count as "on the manifold" for a pair of points (the along instrument) | you, in a forked set | with its set |
| `tables/<set>/family.toml` | how the readings along a family of points are coded and looked up (bracket, f1, f2) | you, in a forked set | with its set |
| `families/<id>.toml` | one family: an input and the points that form it (a family names no rulebook) | you | never |
| `results/<input>@<set>.json`, `.npz` | one run: readings, cells, codes, verdicts, and the hashes of what it read | `bin/cc run` | after `bin/cc freeze` |
| `expected/<set>.toml` | the verdict each point is expected to get (the scoreboard lock) | you, as a reviewed edit with a `why` | never |
| `cc.toml` | defaults, alphabets, what BASIC shows | the maintainers | never |
| `cc/`, `bin/cc` | the code | the maintainers | the four core files only |
| `tests/` | the tests and the recorded command transcripts (`tests/golden/`) | the maintainers | the four core tests |
| `SIGNATURE-TABLE.md`, `docs/verdict-table.html` | every result and the rulebook as tables (`bin/cc tabulate`) | written by `tabulate` | no |
| `FROZEN.json` | the list of frozen files and their hashes | written by `bin/cc freeze` | n/a |

## Since v04-rules (plan 0870)

The working rulebook above is `v01-rules`. `v04-rules` (HOWTO, "Probe completeness, the size chain and POINT-MANIFOLD") adds three things:
a per-point POINT, LINE or WALKING is refused (`REFUSE-PROBE-INCOMPLETE`) when the system has a second coupling that nothing probes, which
turns `x5n-bilayer`'s three POINTs into refusals; a flow read from two size pairs can call a decaying finite-size correction STOPPED
(`drift_code`); and a family can read POINT-MANIFOLD. Try `bin/cc explain x5n-bilayer-2 0.0 --tables v04-rules` and
`bin/cc family x5n-g --tables v04-rules`: the points refuse, and the family over g reads one point class.
