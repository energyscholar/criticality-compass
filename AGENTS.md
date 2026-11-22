# AGENTS.md

For AI coding assistants and new contributors. Read `docs/READING-THE-CODE.md` before you edit anything. It explains why this code looks the way it does, and `docs/try-to-break-it.md` shows the properties holding.

## The one rule

If an input is wrong, extend the door's refusal in `cc/admit.py` (or the refusal of the module that owns the input). Never patch downstream.

## Do not

- Add an `if`, `try`, clamp, threshold or retry inside an operator (`cc/kernel.py`) or after the door to deal with a bad value. The door builds every value the operators see; a bad one is refused there, with a reason.
- Smooth, detrend, interpolate or resample before operator A. The only transform allowed before A is `x + c`.
- Replace a refusal with a default, `0`, `np.nan` or an empty result. A refusal is a typed value with a reason (`cc/door.py:22`); keep it a value.
- Use `.get(key, default)` on a total table, or add a catch-all branch there. The total tables are, for example, `HAS_FLOOR` (`cc/intake_feasible.py:18`) and `STANDING` (`cc/door.py:104`): a missing key is a crash on purpose. Not every dictionary is total; `.get` with a default is used elsewhere (`cc/intake_against.py:49`). Leave those as they are.
- Accept a relation that has no declared provenance, a cycle, or an endpoint outside the declared nodes.
- Make a frozen type mutable, or construct a kernel type anywhere but the door (`cc/admit.py`).
- Edit a pinned file without the identity test. `FROZEN.json` lists files by hash; a comment edit changes the hash. For a file whose code must stay the same, check the syntax tree (comments and docstrings excluded, as `tests/test_dist.py` T3 does) and then re-pin `FROZEN.json` in the same commit. Never re-pin to make a failing check pass.
- Edit a stored result, `benchmark/MANIFEST.toml`, or the files it pins.

## Before you finish

Run `bin/cc check --fast`. A failing check is a finding to report, not a thing to loosen.

If something looks gratuitously odd and is not listed in `docs/READING-THE-CODE.md` under "convention, not necessity", assume it is structural until you have read why. If you still think it is gratuitous, say so in your report and leave it as it is.

## Where things live

- `cc/kernel.py`: the operators A, B, R and the frozen types. `cc/admit.py`: the door that builds them. `cc/door.py`: the door of the measurement path.
- `cc/instruments/`: what each reading computes. `cc/intake*.py`: reading new data in; each module owns its own refusals.
- `tests/`: each test is a script that prints `ok` or `FAIL` lines. `KERNEL-IN-CC.md`: what each instrument computes in the kernel's terms.
