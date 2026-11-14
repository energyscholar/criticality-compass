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
class Handshake:
    """T0 only: the state of the world after a clean handshake (replaced by Verdict at T1)."""
    declaration: object
    edge: object


class _Wire:
    """one JSON object per line over a blocking loopback socket. A closed peer is absence (EOF), never an exception."""
    def __init__(self, host, port):
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.rf = self.sock.makefile("r", encoding="utf-8", newline="\n")

    def ask(self, msg):
        """send msg; return the reply dict, R.Malformed (unparseable line) or None (EOF / closed)."""
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode())
            line = self.rf.readline()
        except OSError:
            return None
        if not line:
            return None
        try:
            return json.loads(line)
        except ValueError:
            return R.Malformed("line", "not JSON")

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


def run(needle_toml):
    cfg = load_needle_cfg(needle_toml)
    if isinstance(cfg, R.Malformed):
        return RefusedToStart(cfg.field, "B")
    w = _Wire(cfg.host, cfg.port)
    try:
        decl = R.parse_declared(w.ask({"op": "declare"}))
        if isinstance(decl, R.Malformed):
            return RefusedToStart(decl.field, "A")
        edge = R.parse_edge(w.ask({"op": "where"}))
        if isinstance(edge, R.Malformed):
            return RefusedToStart(edge.field, "A")
        u_max = decl.knobs_K[1] - edge.K_c
        if not 0.0 <= cfg.u <= u_max:
            return RefusedToStart("u", "u_range")
        return Handshake(decl, edge)
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
