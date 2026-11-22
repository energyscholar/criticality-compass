# Try to break it

Ten commands that try to feed CC something invalid. Run each from the root of a clone, with numpy installed. Each one fails, and the last line it prints is shown under it. `tests/test_try_to_break_it.py` runs them and compares, so this page cannot drift from the code. Why each is refused is in `docs/READING-THE-CODE.md`. These are the attacks the door refuses today; what it does not yet refuse is listed at the end.

## 1. A relation with a cycle

A ring makes node 2 the predecessor of node 0, and node 0 of node 1, and so on round.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit, kernel; admit.declare(3, [(0, 1), (1, 2), (2, 0)], [kernel.Provenance.CONTINUATION] * 3)"
```

```text
ValueError: REFUSED: a cycle (ring/torus) is inadmissible: a node would be its own predecessor
```

## 2. An edge with no declared provenance

The two edges are labelled `'smoothed'`, which is not a provenance.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit; admit.declare(3, [(0, 1), (1, 2)], ['smoothed'] * 2)"
```

```text
ValueError: REFUSED: every edge needs a declared provenance (Continuation/Coupling)
```

## 3. A non-finite value as input

A NaN is offered as one node's value.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit; admit.nodefield([[1.0, float('nan'), 2.0]])"
```

```text
ValueError: REFUSED: every value projected through M must be finite (in D)
```

## 4. Changing a relation after it is declared

A valid relation is built, then its node count is assigned.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit, kernel; r = admit.declare(2, [(0, 1)], [kernel.Provenance.CONTINUATION]); r.n = 3"
```

```text
dataclasses.FrozenInstanceError: cannot assign to field 'n'
```

## 5. A table key that is not declared

The lookup is a plain dictionary index; there is no default to fall back on.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import intake_feasible; intake_feasible.HAS_FLOOR['smooth']"
```

```text
KeyError: 'smooth'
```

## 6. A refusal with a code that has no sentence

A typed refusal can only be built with a code of its own table.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import chain; chain.Refusal('NOT_A_CODE', 'x')"
```

```text
ValueError: 'NOT_A_CODE' is not a valid Refusal.Code
```

## 7. Writing into a declared relation's edge array

A valid relation is built, then one of its target nodes is overwritten: this is how a cycle, or a wrapped negative index, could be made after the door has looked.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit, kernel; r = admit.declare(3, [(0, 1), (1, 2)], [kernel.Provenance.CONTINUATION] * 2); r.tgt[1] = 0"
```

```text
ValueError: assignment destination is read-only
```

## 8. Writing into a field after it is admitted

A value is admitted, then one entry is overwritten with a NaN.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import admit; import numpy as np; nf = admit.nodefield(np.array([[1.0, 2.0]])); nf.data[0, 0] = float('nan')"
```

```text
ValueError: assignment destination is read-only
```

## 9. Building a kernel type without the door

The kernel's own `NodeField` is the door's: constructing it directly gets the same refusal as `admit.nodefield`.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import kernel; import numpy as np; kernel.NodeField(np.array([[float('nan'), 1.0]]))"
```

```text
ValueError: REFUSED: every value projected through M must be finite (in D)
```

## 10. Building a relation with a cycle without the door

The same for `Relations`: a ring built directly through the kernel is refused with the door's words.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import kernel; kernel.Relations(3, [0, 1, 2], [1, 2, 0], (kernel.Provenance.CONTINUATION,) * 3)"
```

```text
ValueError: REFUSED: a cycle (ring/torus) is inadmissible: a node would be its own predecessor
```

## What is not refused yet

Two things are not stopped by the code today, and are kept by review: an element of an edge array inside a declared relation can be written in place (the types are frozen, the arrays are not yet read-only), and a kernel type can be built directly, without going through `cc/admit.py` (`cc/admit.py:46`). This page has no command for them because they are not refused.
