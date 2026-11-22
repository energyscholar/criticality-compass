# Changelog

Format: Keep a Changelog. Versions: PEP 440, `0.MINOR.PATCH` while the tool is in refinement.

## 0.1.0

First distributable version.

- `compass hold`: run a catalogue system by hand and save the run as a record (schema `compass-manual-run/1`: `run.json`, `input/`, `run/`, `terminal.txt`), with `--verify` to recompute its hashes.
- The catalogue: the `ising` and `at` systems and their worlds (`compass hold --list`).
- The rulebook surface: `show`, `explain`, `validate`, `family` over the stored results; the stored results of the benchmark inputs.
- Two distributions: `criticality-compass` (code, the frozen results and every result a shipped document names) and `criticality-compass-data` (the other stored results, CC BY 4.0), which installs into the same workspace.
- Licences: code Apache-2.0; stored results and benchmark data CC BY 4.0. `NOTICE` names the ABR kernel the Python reference `cc/kernel.py` is ported from.
- The run_id of every Ising and AT run is not the one the pre-release builds printed: the declared tau-v0 files (their provenance stamp) are part of the hashed configuration, so editing the stamp changed the id. Records made before it still verify, because each carries its own hashes.
- Not in this version: `tabulate` writes into the workspace, so it is for a clone only.
