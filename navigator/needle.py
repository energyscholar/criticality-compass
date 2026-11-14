"""Plan 1511: the needle — a pure client of needle.toml + the wire. margin-constant-v0 structure.
No clock, no timeout, no retry anywhere here (test 4). It returns a value; it writes nothing (§11.8).
Order (§11.9): parse needle.toml (B) -> connect -> declare (A) -> [floor] -> where (A) -> u_range -> rounds."""
import json
import socket
import sys
import tomllib
from dataclasses import dataclass

from navigator import reader as R


@dataclass(frozen=True)
class RefusedToStart:
    field: str
    parse: str


@dataclass(frozen=True)
class Verdict:
    kind: str        # LINE | ABSENT | REFUSE
    reason: object   # None | "floor" | "budget"
    rounds: list     # [{round,K,index,evaluated,E2}] — the wire facts the orchestrator logs
    declaration: object
    edge: object


class _Wire:
    """one JSON object per line over a blocking loopback socket. A closed peer is absence (EOF), never an exception."""
    def __init__(self, host, port):
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.rf = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def ask(self, msg):
        """send msg; return the total-map value R.Reply | R.Malformed | R.EOF. A send/recv on a closed socket is EOF."""
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode())
            line = self.rf.readline()
        except OSError:
            return R.EOF
        return R.parse_line(line)

    def close(self):
        self.rf.close()
        self.sock.close()


def load_needle_cfg(path):
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return R.Malformed("needle.toml", str(e))
    return R.parse_needle_cfg(raw)


def refuses_at_floor(n, k, tau):
    """the finite-size floor (S13): a declared function of (n, k, tau) only — never sigma, never data."""
    return n < k * tau


def _declared(parsed):
    return R.parse_declared(parsed.fields) if isinstance(parsed, R.Reply) else R.Malformed("declared", "no declaration")


def _edge(parsed, expected_i):
    if not isinstance(parsed, R.Reply):
        return R.Malformed("edge", "no edge reply")
    e = R.parse_edge(parsed.fields)
    if isinstance(e, R.Edge) and e.index != expected_i:
        return R.Malformed("index", "edge index != expected")
    return e


def _round(w, K, n, exp):
    """set, step(n), sense = three replies; Evaluated iff all three are. exp = sweeps sent so far (§11.1). -> (evaluated, E2, exp')"""
    a = R.judge(w.ask({"op": "set", "K": K}), "ok", exp)
    exp += n  # the running sum of every n SENT, so a substituted reply never desyncs a later round
    b = R.judge(w.ask({"op": "step", "n": n}), "ok", exp)
    c = R.judge(w.ask({"op": "sense"}), "obs", exp)
    E2 = c.reply.fields.get("E2") if isinstance(c, R.Evaluated) else None
    ok = isinstance(a, R.Evaluated) and isinstance(b, R.Evaluated) and isinstance(c, R.Evaluated) and isinstance(E2, float)
    return ok, (E2 if ok else None), exp


def run(needle_toml):
    cfg = load_needle_cfg(needle_toml)
    if isinstance(cfg, R.Malformed):
        return RefusedToStart(cfg.field, "B")
    w = _Wire(cfg.host, cfg.port)
    try:
        decl = _declared(w.ask({"op": "declare"}))
        if isinstance(decl, R.Malformed):
            return RefusedToStart(decl.field, "A")
        if refuses_at_floor(cfg.n, decl.k, decl.tau):  # evaluated once, here, before `where`; the loop is never entered
            return Verdict("REFUSE", "floor", [], decl, None)
        edge = _edge(w.ask({"op": "where"}), 0)
        if isinstance(edge, R.Malformed):
            return RefusedToStart(edge.field, "A")
        u_max = decl.knobs_K[1] - edge.K_c
        if not 0.0 <= cfg.u <= u_max:
            return RefusedToStart("u", "u_range")
        K, exp, rounds = edge.K_c + cfg.u, 0, []
        for r in range(1, cfg.N + 1):  # all N rounds, never an early abort
            ok, E2, exp = _round(w, K, cfg.n, exp)
            rounds.append({"round": r, "K": K, "index": exp, "evaluated": ok, "E2": E2})
        if not all(x["evaluated"] for x in rounds):
            return Verdict("REFUSE", "budget", rounds, decl, edge)
        return Verdict("LINE" if abs(K - edge.K_c) <= edge.w else "ABSENT", None, rounds, decl, edge)
    finally:
        w.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--needle", required=True)
    r = run(ap.parse_args().needle)
    if isinstance(r, RefusedToStart):
        print(f"RefusedToStart field={r.field} parse={r.parse}", file=sys.stderr)
        sys.exit(2)
    print(r)
