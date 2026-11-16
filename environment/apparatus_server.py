"""Plan 1545: the APPARATUS environment server (contract/SCHEMA-1545.md). Four ops (environment/apparatus_wire.py). The truth is
written ONLY to the run directory: edge.json before the port binds, truth.json and perf.json on exit (including SIGTERM, in
a `finally`). A malformed world is refused before the run directory is created. Mirrors environment/blind_server.py.
Entry: python -m environment.apparatus_server --env environment-apparatus.toml --at at-apparatus.toml --run-dir DIR"""
import argparse
import json
import signal
import socket
import sys
import time
from pathlib import Path

from environment import apparatus_config as AC
from environment import apparatus_wire as AW
from navigator import reader as R


def serve_connection(conn, engine, pub, rows, perf):
    # errors="replace": a line that is not UTF-8 becomes a line that is not JSON, and is answered nev
    rf = conn.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    try:
        for line in rf:
            try:
                msg = json.loads(line)
            except (ValueError, RecursionError):
                msg = None
            t0 = time.perf_counter()
            reply, note = AW.handle(engine, pub, rows, msg)
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
    cfgs = AC.load_apparatus_cfgs(a.env, a.at)
    if isinstance(cfgs, R.Malformed):
        print(f"RefusedToStart field={cfgs.field} parse=B detail={cfgs.detail}", file=sys.stderr)
        return 2
    env, world, tau, plug = cfgs
    engine = plug.Engine(world)  # burn once, at the start position and the index-0 hidden values; the port binds only after
    pub = AW.public(world, tau.value, plug)
    rows, perf = [], []
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    edge = {"time": AW.TIME_LABEL, "wire": AW.WIRE, "index": 0, "K_c": engine.K_c(0), "drift": world.drift.table, "hidden": world.hidden}
    (run_dir / "edge.json").write_text(json.dumps(edge, sort_keys=True))  # the truth is written here and at exit, nowhere else
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    lsock = socket.socket()
    try:
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind(("127.0.0.1", env.port))
        lsock.listen(4)
        while True:
            conn, _ = lsock.accept()
            serve_connection(conn, engine, pub, rows, perf)
    finally:
        lsock.close()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "truth.json").write_text(json.dumps({"time": AW.TIME_LABEL, "wire": AW.WIRE, "rows": rows}))
        (run_dir / "perf.json").write_text(json.dumps({"time": AW.TIME_LABEL, "calls": perf}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
