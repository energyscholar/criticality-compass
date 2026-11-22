# Contributing to Criticality Compass

Thank you for reading the code closely. The most useful contribution is a reading that looks wrong, or a way to make CC print a verdict it should not.

## Read first

1. [`AGENTS.md`](AGENTS.md): the rules every change follows (no smoothing, interpolation, clamps, guards, defaults for missing keys, or undeclared relations).
2. [`docs/READING-THE-CODE.md`](docs/READING-THE-CODE.md): where each part lives and what CC cannot do.
3. [`docs/try-to-break-it.md`](docs/try-to-break-it.md): the faults worth trying.

## Set up

From a clone, with Python 3.11 or later:

```
python3 -m venv .venv && . .venv/bin/activate
pip install -e .[test]
bin/cc check --fast
```

`bin/cc check --fast` runs the tests that need neither a long run nor the simulation outputs. A line `SKIPPED ... needs the data root` means a test was not run, not that it passed: those tests read simulation outputs that live outside the repository. Name them with `--data-root PATH` or `CC_DATA_ROOT=PATH` to run them. The Rust kernel is optional (`README.md`, "The Rust kernel"); tests that need it say so.

## Before you open a pull request

- Paste the failure names of `bin/cc check --fast` from your tree and from the base you started from. Compare names, not counts.
- If you edit an existing test, say so in the description and say why. A test edited to fit the code, or code edited to fit a test, is the first thing a reviewer looks for.
- A new check must be seen to fail on a planted fault (`tests/planted/` holds examples) before you trust it passing.
- A pinned file (the ones listed in `FROZEN.json`, and the golden outputs under `tests/golden/`) is edited by the pattern its test describes: show the change is identical in structure (AST identity), then re-pin. Never edit a pin to make a test pass.
- If the input is wrong, extend the door's refusal so the bad input is refused with a reason. Never patch it downstream.

## Licences

By contributing you agree your contribution is licensed under Apache-2.0 section 5 (code) or CC BY 4.0 (data under `benchmark/` and `results/`), the same as the file you change. There is no contributor licence agreement and no sign-off requirement.

## Conduct and security

Be kind and specific. See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Report a vulnerability as [`SECURITY.md`](SECURITY.md) describes, not in a public issue.
