# Reading the code: why it looks strange

You know numpy and dataclasses. This code will look odd to you: no `if` in the maths, dictionaries where you expect branches, frozen types everywhere, errors that are values. Each of those is a property CC has on purpose. This page lists what CC refuses today, then the idioms that make that so, so that you can read them and so that you do not "fix" them. Every claim carries a `file:line` or a command; `tests/test_reading_examples_resolve.py` fails if a line moves, and `docs/try-to-break-it.md` runs the attacks.

## What CC refuses today

These hold at the door. Where a limit is known today, it is stated.

1. **Declare a cyclic relation.** A ring or torus makes a node its own predecessor. `admit.declare` refuses it before a relation exists: `cc/admit.py:66`.
2. **Declare an edge with no declared provenance.** A relation is a set of edges, each a `Continuation` or a `Coupling`; any other value is refused, and `Provenance` has no member for "smoothed" or "inferred": `cc/admit.py:62`, `cc/admit.py:15`.
3. **Admit a non-finite value as a `NodeField`.** `admit.nodefield` refuses a NaN: `cc/admit.py:88`. In the measurement path the same condition returns a typed null that carries its reason instead of a number: `cc/door.py:290`.
4. **Reassign a field of a declared relation.** The types are frozen; assigning to a field raises: `cc/admit.py:45`. Limits today: the edge arrays inside a relation are not yet read-only, so an element can still be written in place, and nothing yet stops code from constructing a kernel type directly instead of through the door (`cc/admit.py:46`). Both are kept by review and by `AGENTS.md`.
5. **Take a default for a missing key in a total table.** In the tables named in `AGENTS.md`, a key that is not there is a `KeyError`: `cc/intake_feasible.py:18`. Not every dictionary in `cc/` is total: `.get(key, default)` is used elsewhere, for example `cc/intake_against.py:49`.
6. **Apply anything before A except `x + c`.** The one pre-A transform in the measurement path adds a constant and nothing else: `cc/intake_terminal.py:154`.

`docs/try-to-break-it.md` has a command for each of 1 to 5.

## The method in one page

Two ways to keep invalid states out of a computation.

*Control* lets the state happen, then catches it: an `if` that tests for it, a clamp, a threshold, a retry, a patch. Correct code of this kind needs every guard to be present and every guard to be right, and a missed one fails silently.

*Structure* chooses the representation, the coordinates, the update map and the output types so that the invalid state cannot be constructed. There is nothing to catch, because there is nothing to reach. Three well-known techniques that rest on the same idea. They are not part of CC; they are here to show the idea:

- **Normalization in place of clamping**, the same idea as the method: A quantity that must lie on a sphere is stored as a direction that is normalized by construction; there is no radius to drift off the sphere and no clamp to forget.
- **Bresenham's line**, the same idea as the method: The line is drawn by stepping integer coordinates with an integer error term, so every plotted point is a grid point. No rounding is applied afterwards because no real-valued point exists.
- **Symplectic integration**, the same idea as the method: The update map is chosen to preserve the phase-space structure exactly at each step, so energy error stays bounded; it is not corrected after the run.

The relational kernel (the ABR operators; credited to Robin Macomber and Metatron Dynamics, Inc., see `README.md`, "Acknowledgements") is CC's instance of the method at the point where data enters. A is the graph incidence operator, a difference along each declared edge (`cc/kernel.py:39`); B and R build on it; the maths is standard. What the kernel supplies is the rule about what may reach those operators: before A only `x + c`, every relation declared with its provenance, inadmissible input refused with a reason. `KERNEL-IN-CC.md` has the full account.

## The idioms

| You expect | CC does | Example | What it buys | Do not "fix" it into |
|---|---|---|---|---|
| `if` and `try` in the maths | no branch at all in the operators; the door builds every input | `cc/kernel.py:39` (A), `cc/admit.py:138` (the door) | the operators are written to receive only what the door built, so they carry no check | a guard inside an operator |
| validation inside the function that uses a value | frozen types that only the door builds | `cc/admit.py:46`, `cc/admit.py:141` | a value the door built is valid when built, and its fields cannot be reassigned (the arrays inside are not yet read-only) | a mutable class, or a constructor that accepts anything |
| an exception, a NaN, or a default for bad input | the refusal is a value with a reason | `cc/door.py:22`, `cc/door.py:290`, `cc/registry.py:38` | the reason travels with the result and is printed in its cell (`KERNEL-IN-CC.md:199`); nothing is replaced by a number | `0`, `np.nan`, a clamp, a bare `except` |
| `if/elif` over a set of cases | a dictionary keyed by the case, declared total | `cc/intake_feasible.py:16`, `cc/intake_feasible.py:18` | a case added without its row fails at the lookup | `.get(key, default)` |
| a typed error code checked against a list | a `Typed` refusal whose `code` must be a key of its own table | `cc/intake_blind.py:245`, `cc/chain.py:48` | the code is looked up when the refusal is printed, so an unknown code fails at print, not when the refusal is built; every known code has a sentence | a free string for the code |
| relations and comparisons chosen after looking at data | declared first, with provenance, before any data are read | `cc/admit.py:138`, `cc/admit.py:15` | relations are declared with provenance before data are admitted, and nothing in CC derives them from the data | building edges from the data |
| smoothing, detrending, interpolation | none before A; only `x + c` | `cc/intake_terminal.py:154` | pairwise differences are what A reads, and a shift leaves them unchanged | a filter or resample before the door |
| a test that a number is close to a stored one | a hash of the code that measures, and frozen results | `cc/schema.py:185`, `tests/test_dist.py` (T3) | a result is tied to the code that made it. A comment edit changes a file hash and so the reuse key; the identity of the code itself is checked on the syntax tree, comments and docstrings excluded | loosening a pin, or re-pinning without the identity test |

Two refusal styles exist today. `cc/admit.py` raises `ValueError("REFUSED: ...")` when a relation or a field is declared (`cc/admit.py:66`); `cc/door.py` returns a `Null` value that carries its reason when a measurement cannot be evaluated (`cc/door.py:290`).

## One function, two ways

`door.nodefield` (`cc/door.py:284`) turns reduced outputs into the operator input. First what CC does, abridged from `cc/door.py:284-290`:

```python
def nodefield(x, ctx):
    x = x.reshape(-1, x.shape[-1])
    return admit.nodefield(x) if np.isfinite(x).all() else Null("NOT-EVALUATED", "non-finite value")
```

Then a control-style version, written here only to show the contrast. It is an illustration and is not in CC:

```python
def nodefield(x):
    x = np.nan_to_num(x)   # replace NaN and inf so the maths can proceed
    return NodeField(x)
```

The CC function returns one of two typed values: a `NodeField` whose values are all finite, or a `Null` that names the reason. Code after it receives a `Null`, not a number, for a missing value. The illustration returns a `NodeField` in every case, so a NaN becomes `0.0` and is read as a measurement.

## Where the structure is convention, not necessity

These idioms do not buy a structural property; they are style, and are candidates for plain code. Listed so a reader does not look for a property that is not there. Bool-keyed dispatch in particular is used throughout the intake modules (for example `cc/intake_against.py:42` and `cc/intake_blind.py:91`), not only in the two examples below; the two stay listed as examples.

- **Bool-keyed dictionaries standing in for a two-way `if`.** `cc/intake_blindview.py:19`, `EXT = {True: ..., False: ...}`, called as `EXT[cond](n)` at `cc/intake_blindview.py:25`. A two-way branch on a boolean; the table is not "total" in a way that a missing key could reveal, because a boolean has two values.
- **`lambda ...: print(...) or 0` as a dispatch entry.** `cc/intake.py:123`. The entry prints and returns 0, written as an expression so that it can sit in the dictionary. No refusal or guard happens in it.

<!-- refs: each visible file:line above must resolve and its line(s) must contain the keyword.
ref cc/admit.py:66 = cycle
ref cc/admit.py:62 = provenance
ref cc/admit.py:15 = Provenance
ref cc/admit.py:88 = finite
ref cc/door.py:290 = Null
ref cc/admit.py:45 = dataclass
ref cc/intake_feasible.py:18 = HAS_FLOOR
ref cc/intake_terminal.py:154 = np.array
ref cc/kernel.py:39 = def A
ref cc/admit.py:138 = def declare
ref cc/admit.py:46 = class Relations
ref cc/admit.py:141 = Relations(
ref cc/door.py:22 = class Null
ref cc/intake_terminal.py:152 = x + c
ref cc/admit.py:57-88 = REFUSED
ref KERNEL-IN-CC.md:199 = NOT-EVALUATED
ref cc/registry.py:38 = class Refuse
ref cc/intake_feasible.py:16 = REPLICATED
ref cc/intake_blind.py:245 = class Typed
ref cc/chain.py:48 = class Refusal
ref cc/schema.py:185 = def measure_hash
ref cc/door.py:284 = def nodefield
ref cc/door.py:284-290 = Null
ref cc/intake_blindview.py:19 = EXT
ref cc/intake_blindview.py:25 = EXT[
ref cc/intake.py:123 = INTAKE
ref cc/sign.py:19 = UNRES
ref cc/door.py:104 = STANDING
ref cc/intake_against.py:49 = NAMES.get
ref cc/intake_against.py:42 = True
ref cc/intake_blind.py:91 = True
-->
