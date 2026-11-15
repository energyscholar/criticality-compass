"""Plan 1525: the BLIND environment server. Its op table has exactly `declare` and `measure` (environment/blind_wire.py); the
lattice is burned at the declared K_start, never at K_c; the truth is written ONLY to <run_dir>/edge.json, before the port binds.
Releases its port and writes perf.json on exit including SIGTERM (`finally`). Mirrors environment/server.py.
Entry: python -m environment.blind_server --env environment.toml --at at-blind.toml --run-dir DIR"""
import argparse
import importlib.util
import json
import signal
import socket
import sys
import time
from pathlib import Path

from environment import blind_config as BC
from environment import blind_wire
from environment import config as C
from navigator import reader as R


def load_blind(system):
    f = C.plugin_dir(system) / "blind.py"
    spec = importlib.util.spec_from_file_location(f"blind_{system}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def declared_msg(blind, at, tau):
    return {"op": "declared", "knobs_K": list(at.knobs_K), "ordered_side": blind.ORDERED_SIDE, "L": at.L, "tau": tau.value,
            "k": at.k, "index_unit": at.index_unit, "index_kind": at.index_kind, "observable": blind.OBSERVABLE, "nlev": at.nlev}


def serve_connection(conn, blind, state, declared, perf):
    rf = conn.makefile("r", encoding="utf-8", newline="\n")
    try:
        for line in rf:
            try:
                msg = json.loads(line)
            except ValueError:
                msg = None
            t0 = time.perf_counter()
            reply, note = blind_wire.handle(blind, state, declared, msg)
            dt = time.perf_counter() - t0
            if note:
                print(f"malformed: {note}", file=sys.stderr, flush=True)
            op = msg.get("op") if isinstance(msg, dict) else None
            perf.append({"op": str(op), "seconds": dt})
            conn.sendall((json.dumps(reply) + "\n").encode())
    except OSError:
        pass  # peer vanished: absence, not an error
    finally:
        rf.close()
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--at", required=True)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args(argv)
    cfgs = BC.load_blind_cfgs(a.env, a.at)
    if isinstance(cfgs, R.Malformed):
        print(f"RefusedToStart field={cfgs.field} parse=B detail={cfgs.detail}", file=sys.stderr)
        return 2
    env, at, tau = cfgs
    blind = load_blind(env.system)
    state = blind.init_blind(at)  # burn once, at K_start; the port binds only after, so a bound port means ready
    declared = declared_msg(blind, at, tau)
    perf = []
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "edge.json").write_text(json.dumps(blind.truth(state), sort_keys=True))  # the only place the truth is written
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    lsock = socket.socket()
    try:
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind(("127.0.0.1", env.port))
        lsock.listen(4)
        while True:
            conn, _ = lsock.accept()
            serve_connection(conn, blind, state, declared, perf)
    finally:
        lsock.close()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "perf.json").write_text(json.dumps(perf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
