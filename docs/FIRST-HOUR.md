# Your first hour with Criticality Compass

This page takes you from `pip install` to a record you can check. It runs one small simulated hold, reads the record it writes, and then says plainly what the tool reports and what it does not.

## 1. Install

You need Python 3.11 or later. In a new virtual environment:

```sh
python3 -m venv cc-venv
cc-venv/bin/python -m pip install criticality-compass criticality-compass-data
```

`criticality-compass` is the code and the frozen results. `criticality-compass-data` (CC BY 4.0) holds the remaining stored results; the commands on this page need only the first. The launcher is `cc-venv/bin/compass`. The manual is installed with the package: `man -M cc-venv/share/man compass`.

## 2. See what is in the catalogue

```
$ compass hold --list
ising  production  needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus.toml)
ising  static      needles: settled mid settled-off   (system-instantiated/plugins/ising/ising-apparatus-static.toml)
...
```

Each line is a simulated system (`ising`, `at`), a world to run it in, and the needles that can steer it. A needle moves one dial on the simulated system, over a wire protocol, and the run is scored against what the server knows to be true.

## 3. Run one hold

The `static` world has a long horizon (minutes of compute). For a first run, copy its world file and shorten the horizon to 1. The world file is in the install, under `criticality_compass/workspace/system-instantiated/plugins/ising/`:

```sh
cp cc-venv/lib/python3.*/site-packages/criticality_compass/workspace/system-instantiated/plugins/ising/ising-apparatus-static.toml quick.toml
sed -i.bak 's/^horizon .*/horizon = 1/' quick.toml
```

```
$ compass hold ising quick.toml --needle settled
INPUT
  system ising  world path  needle settled  seed 500 (from the world file)
  world  path  sha256 f5c842fc763a
  world params: kind=critical L_blocks=27 seed=500 horizon=1 dials=[{'name': 'K', 'lo': 0.42, 'hi': 0.545, 'T': 500, 'max_nudge': 32, 'start': 0}] drift={'target': 'dK', 'law': 'none'}
  needle needle-settings/ising/hold-settled.toml  sha256 c2159cac0b3e
  needle params: needle_structure=hold-pair-v1 g=12 step=6 S=1500 n_eq=450
  score  environment/hold-score-ising.toml  sha256 158dbcc14f0e
  score params: offset_K=-0.005 out_run=3 plan=1569
  code   compass 0.1.0  git not-a-clone  digest c191ac11415e
RUN step 1 phase ignite index 0  t=6s
OUTPUT
  outcome=HORIZON lock=LOST in_fraction=no-hold-steps rms_e_g=no-hold-steps mean_e=no-hold-steps hold_steps=0 accuracy=no-hold-steps  run_id=bcbffe41b8a450d0
record: 20261122T145542Z-ising-path-bcbffe41b8a450d0-f43b
exit 0: scored  (status scored)
```

This took a few seconds. Your timestamps and `t=` value will differ; the `run_id` and the numbers will be the same as shown. A horizon of 1 stops the run before the needle has held anything, so `lock=LOST` and `hold_steps=0` are what this short run should print. It is a check that the install works, not a measurement.

## 4. Read the record

The run is saved as a directory under `./compass-runs/` (or `$COMPASS_RUNS`):

- `run.json` lists the command, the exit status, the inputs and outputs with their sha256, the run's summary and the versions. `run.json.sha256` is its own hash.
- `input/` is a copy of every input the run used: the environment, the world, the needle, the score settings.
- `run/` is what the run produced: `score.json`, `truth.json`, `map.jsonl`, `report.jsonl` and others.
- `terminal.txt` is what was printed.

In the OUTPUT line, `HORIZON` means the run reached its horizon; `lock=HELD` says the lock was held at the end and `LOST` that it was not; `in_fraction` is the share of the hold steps inside the window.

## 5. Check it

```
$ compass hold --verify compass-runs/<record>
verified: every file matches run.json
```

`--verify` recomputes the hashes of every file in the record. If you change a byte of any file in the record and run it again, it names the file that differs. Two runs of the same input on the two machines we have measured (macOS arm64 and Linux x86_64, with numpy 2.4 and scipy 1.17) write byte-identical `score.json`, `truth.json`, `map.jsonl` and `report.jsonl`.

## 6. What the tool reports, and what it does not claim

- A hold outcome is a score of a needle against the simulated server's truth. It is not evidence that any physical system is critical.
- A power law, or a slowing-down signal on its own, is not evidence of criticality. `KERNEL-IN-CC.md` and the README say what each instrument computes and where the argument stops.
- The rulebook commands (`run`, `check`, `freeze`) need an external checker that this install does not include.
- `tabulate` works only in a clone of the repository.
- A `plan=NNNN` key in a record or a table is a provenance tag, the number of the plan that made the file. It is not a version.

To see why the code is written the way it is, read `docs/READING-THE-CODE.md`; to try to break it, `docs/try-to-break-it.md`.
