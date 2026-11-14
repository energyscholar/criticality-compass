"""Plan 1511: the environment server — a long-running, commanded live-in-time host for one plugin, serving JSON lines
over a loopback TCP socket (§1a, §5). It owns its port and its in-memory state and releases both on exit, including on
SIGTERM/crash (`finally`; never a sweeper — §4). Timing lives HERE (not in the needle) and goes only to <run_dir>/perf.json (§11.4).
Entry: python -m environment.server --env environment.toml [--at at.toml] --run-dir DIR"""
import argparse
import json
import signal
import socket
import sys
import time
from pathlib import Path

from environment import config as C
from environment import wire
from navigator import reader as R


def declared_msg(plugin, at, tau):
    return {"op": "declared", "knobs_K": list(at.knobs_K), "ordered_side": plugin.ORDERED_SIDE, "L": at.L, "tau": tau.value,
            "k": at.k, "index_unit": at.index_unit, "index_kind": at.index_kind, "observable": plugin.OBSERVABLE}


def serve_connection(conn, plugin, state, declared, perf):
    rf = conn.makefile("r", encoding="utf-8", newline="\n")
    try:
        for line in rf:
            msg = wire.parse_line(line)
            t0 = time.perf_counter()
            reply, note = wire.handle(plugin, state, declared, msg)
            dt = time.perf_counter() - t0
            if note:
                print(f"malformed: {note}", file=sys.stderr, flush=True)
            op = msg.get("op") if isinstance(msg, dict) else None
            n = msg.get("n") if isinstance(msg, dict) and isinstance(msg.get("n"), int) else None
            perf.append({"op": str(op), "n": n, "seconds": dt})
            conn.sendall((json.dumps(reply) + "\n").encode())
    except OSError:
        pass  # peer vanished: absence, not an error
    finally:
        rf.close()
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--at", default=None)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args(argv)
    cfgs = C.load_server_cfgs(a.env, a.at)
    if isinstance(cfgs, R.Malformed):
        print(f"RefusedToStart field={cfgs.field} parse=B detail={cfgs.detail}", file=sys.stderr)
        return 2
    env, at, tau = cfgs
    plugin = C.load_plugin(env.system)
    state = plugin.init(at)  # burn once, here; the port binds only after, so a bound port means ready
    declared = declared_msg(plugin, at, tau)
    perf = []
    run_dir = Path(a.run_dir)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    lsock = socket.socket()
    try:
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind(("127.0.0.1", env.port))
        lsock.listen(4)
        while True:
            conn, _ = lsock.accept()
            serve_connection(conn, plugin, state, declared, perf)
    finally:
        lsock.close()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "perf.json").write_text(json.dumps(perf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
