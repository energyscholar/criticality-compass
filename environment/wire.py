"""Plan 1511: server-side wire framing + the total op -> reply map (§5, §11.7). One JSON object per line.
`handle(plugin, state, declared, msg) -> reply dict`. No op is unhandled: unknown/malformed => nev at the current index."""
import json


def nev(state):
    return {"op": "nev", "index": state.index}


def handle(plugin, state, declared, msg):
    """returns (reply, malformed_note_or_None). The step/set/sense mutation happens here, once."""
    if not isinstance(msg, dict):
        return nev(state), "non-object line"
    op = msg.get("op")
    if op == "declare":
        return declared, None
    if op == "where":
        return {"op": "edge", **plugin.edge(state), "index": state.index}, None
    if op == "set":
        K = msg.get("K")
        if not isinstance(K, float) or plugin.set(state, K) is None:
            return nev(state), f"set K rejected: {K!r}"
        return {"op": "ok", "index": state.index}, None
    if op == "step":
        n = msg.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            return nev(state), f"step n rejected: {n!r}"
        plugin.step(state, n)
        return {"op": "ok", "index": state.index}, None
    if op == "sense":
        return {"op": "obs", "E2": plugin.sense(state), "index": state.index}, None
    return nev(state), f"unknown op: {op!r}"


def parse_line(line):
    try:
        return json.loads(line)
    except ValueError:
        return None
