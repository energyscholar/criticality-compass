# Try to break it

Six commands that try to feed CC something invalid. Run each from the root of a clone, with numpy installed. Each one fails, and the last line it prints is shown under it. `tests/test_try_to_break_it.py` runs them and compares, so this page cannot drift from the code. Why each is refused is in `docs/READING-THE-CODE.md`.

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

A typed refusal must name a code that is a key of its own table; asking for its words with an unknown code fails.

```sh
python3 -c "import sys; sys.path.insert(0, 'cc'); import chain; chain.Refusal('NOT_A_CODE', 'x').words()"
```

```text
KeyError: 'NOT_A_CODE'
```
