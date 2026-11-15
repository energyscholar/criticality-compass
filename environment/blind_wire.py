"""Plan 1525: the blind face's total op -> reply map. Exactly two ops, `declare` and `measure`; everything else, `where`
included, is `nev` at the current index. `measure` is validated whole before anything mutates; there is no clamp."""


def nev(state):
    return {"op": "nev", "index": state.index}


def _int(v, lo):
    return isinstance(v, int) and not isinstance(v, bool) and v >= lo


def handle(blind, state, declared, msg):
    """-> (reply, malformed_note_or_None)."""
    if not isinstance(msg, dict):
        return nev(state), "non-object line"
    op = msg.get("op")
    if op == "declare":
        return declared, None
    if op == "measure":
        Ks, n_eq, S, skip = msg.get("Ks"), msg.get("n_eq"), msg.get("S"), msg.get("skip")
        lo, hi = declared["knobs_K"]
        valid = (isinstance(Ks, list) and len(Ks) > 0 and all(isinstance(K, float) and lo <= K <= hi for K in Ks)
                 and _int(n_eq, 1) and _int(S, 40) and _int(skip, 1))
        if not valid:
            return nev(state), f"measure rejected: Ks={Ks!r} n_eq={n_eq!r} S={S!r} skip={skip!r}"
        m = blind.measure_moments(state, Ks, n_eq, S, skip)
        return {"op": "moments", **m, "index": state.index}, None
    return nev(state), f"unknown op: {op!r}"
