# Reading the code: why it looks strange

You know numpy and dataclasses. This code will look odd to you: no `if` in the maths, dictionaries where you expect branches, frozen types everywhere, errors that are values. Each of those is a property CC has on purpose. This page lists what CC cannot do, then the idioms that make that so, so that you can read them and so that you do not "fix" them. Every claim carries a `file:line` or a command; `tests/test_reading_examples_resolve.py` fails if a line moves, and `docs/try-to-break-it.md` runs the attacks.

## What CC cannot do

1. **Build a cyclic relation.** A ring or torus makes a node its own predecessor. `admit.declare` refuses it before a relation exists: `cc/admit.py:39`.
2. **Build an edge with no declared provenance.** A relation is a set of edges, each a `Continuation` or a `Coupling`; any other value is refused, and `Provenance` has no member for "smoothed" or "inferred": `cc/admit.py:35`, `cc/kernel.py:30`.
3. **Feed operator A a non-finite value.** A NaN cannot become a `NodeField`: `cc/admit.py:49`. In the measurement path the same condition returns a typed null that carries its reason instead of a number: `cc/door.py:290`.
4. **Change a relation after it is declared.** The types are frozen; assigning to one raises: `cc/kernel.py:35`.
5. **Take a default for a missing table key.** The tables are total dictionaries; a key that is not there is a `KeyError`, never a fallback value: `cc/intake_feasible.py:18`.
6. **Apply anything before A except `x + c`.** The one pre-A transform in the measurement path adds a constant and nothing else: `cc/intake_terminal.py:154`.

`docs/try-to-break-it.md` has a command for each of 1 to 5.

## The method in one page

Two ways to keep invalid states out of a computation.

*Control* lets the state happen, then catches it: an `if` that tests for it, a clamp, a threshold, a retry, a patch. Correct code of this kind needs every guard to be present and every guard to be right, and a missed one fails silently.

*Structure* chooses the representation, the coordinates, the update map and the output types so that the invalid state cannot be constructed. There is nothing to catch, because there is nothing to reach. Three standard cases of the method:

- **Normalization in place of clamping.** A quantity that must lie on a sphere is stored as a direction that is normalized by construction; there is no radius to drift off the sphere and no clamp to forget.
- **Bresenham's line.** The line is drawn by stepping integer coordinates with an integer error term, so every plotted point is a grid point. No rounding is applied afterwards because no real-valued point exists.
- **Symplectic integration.** The update map is chosen to preserve the phase-space structure exactly at each step, so energy error stays bounded; it is not corrected after the run.

The relational kernel (the ABR operators; credited to Robin Macomber and Metatron Dynamics, Inc., see `README.md`, "Acknowledgements") is CC's instance of the method at the point where data enters. A is the graph incidence operator, a difference along each declared edge (`cc/kernel.py:72`); B and R build on it; the maths is standard. What the kernel supplies is the rule about what may reach those operators: before A only `x + c`, every relation declared with its provenance, inadmissible input refused with a reason. `KERNEL-IN-CC.md` has the full account.

## The idioms

| You expect | CC does | Example | What it buys | Do not "fix" it into |
|---|---|---|---|---|
| `if` and `try` in the maths | no branch at all in the operators; the door builds every input | `cc/kernel.py:72` (A), `cc/admit.py:28` (the door) | the operators cannot meet an invalid input, so they need no check | a guard inside an operator |
| validation inside the function that uses a value | frozen types that only the door builds | `cc/kernel.py:36`, `cc/admit.py:40` | a value that exists is valid; it cannot be changed into an invalid one | a mutable class, or a constructor that accepts anything |
| an exception, a NaN, or a default for bad input | the refusal is a value with a reason | `cc/door.py:22`, `cc/door.py:290`, `cc/registry.py:38` | the reason travels with the result and is printed in its cell (`KERNEL-IN-CC.md:198`); nothing is replaced by a number | `0`, `np.nan`, a clamp, a bare `except` |
| `if/elif` over a set of cases | a dictionary keyed by the case, declared total | `cc/intake_feasible.py:16`, `cc/intake_feasible.py:18` | adding a case without its row is a crash at the lookup, so no case is handled by accident | `.get(key, default)` |
| a typed error code checked against a list | a `Typed` refusal whose `code` must be a key of its own table | `cc/intake_blind.py:245`, `cc/chain.py:48` | a refusal with an unknown code cannot be printed; every code has a sentence | a free string for the code |
| relations and comparisons chosen after looking at data | declared first, with provenance, before any data are read | `cc/admit.py:28`, `cc/kernel.py:30` | a relation cannot be fitted to the data it is applied to | building edges from the data |
| smoothing, detrending, interpolation | none before A; only `x + c` | `cc/intake_terminal.py:154` | pairwise differences are what A reads, and a shift leaves them unchanged | a filter or resample before the door |
| a test that a number is close to a stored one | a hash of the code that measures, and frozen results | `cc/schema.py:185`, `tests/test_dist.py` (T3) | a result is tied to the code that made it. A comment edit changes a file hash and so the reuse key; the identity of the code itself is checked on the syntax tree, comments and docstrings excluded | loosening a pin, or re-pinning without the identity test |

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

The CC function returns one of two typed values: a `NodeField` whose values are all finite, or a `Null` that names the reason. Code after it cannot receive a number that stands for a missing one. The illustration returns a `NodeField` in every case, so a NaN becomes `0.0` and is read as a measurement.

## Where the structure is convention, not necessity

These idioms do not buy a structural property; they are style, and are candidates for plain code. Listed so a reader does not look for a property that is not there.

- **Bool-keyed dictionaries standing in for a two-way `if`.** `cc/intake_blindview.py:19`, `EXT = {True: ..., False: ...}`, called as `EXT[cond](n)` at `cc/intake_blindview.py:25`. A two-way branch on a boolean; the table is not "total" in a way that a missing key could reveal, because a boolean has two values.
- **`lambda ...: print(...) or 0` as a dispatch entry.** `cc/intake.py:123`. The entry prints and returns 0, written as an expression so that it can sit in the dictionary. No refusal or guard happens in it.

<!-- refs: each visible file:line above must resolve and its line(s) must contain the keyword.
ref cc/admit.py:39 = cycle
ref cc/admit.py:35 = provenance
ref cc/kernel.py:30 = Provenance
ref cc/admit.py:49 = finite
ref cc/door.py:290 = Null
ref cc/kernel.py:35 = dataclass
ref cc/intake_feasible.py:18 = HAS_FLOOR
ref cc/intake_terminal.py:154 = np.array
ref cc/kernel.py:72 = def A
ref cc/admit.py:28 = def declare
ref cc/kernel.py:36 = class Relations
ref cc/admit.py:40 = Relations(
ref cc/door.py:22 = class Null
ref cc/intake_terminal.py:152 = x + c
ref cc/admit.py:33-58 = REFUSED
ref KERNEL-IN-CC.md:198 = NOT-EVALUATED
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
-->
