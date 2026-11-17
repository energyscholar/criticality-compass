"""Plan 1545: the APPARATUS environment server (contract/SCHEMA-1545.md); plan 1565 adds the world clock and the server's time
ledger (contract/SCHEMA-1565.md). Four ops (environment/apparatus_wire.py). Every line received is a TURN: the world first runs the
free sweeps its clock owes for the needle time that turn took (environment/world_clock.py; none for a paused world), then the op is
handled exactly as before. The truth is written ONLY to the run directory: edge.json before the port binds, truth.json, perf.json
and turns.json on exit (including SIGTERM, in a `finally`). A malformed world is refused before the run directory is created.
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
from environment import world_clock as WC
from navigator import reader as R


def free_run(engine, n):
    """n sweeps with no sample and no truth row: the world running on while the needle deliberates."""
    for _ in range(n):
        engine.sweep()


def serve_connection(conn, engine, pub, rows, perf, world_clock, book):
    # errors="replace": a line that is not UTF-8 becomes a line that is not JSON, and is answered nev
    rf = conn.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    last = time.monotonic()       # needle time runs from the accept, then from the end of each reply (SCHEMA-1565 section 3)
    try:
        for line in rf:
            gap = time.monotonic() - last
            book["ledger"], free = WC.turn(world_clock, book["ledger"], gap, pub.horizon - engine.index)
            f0 = time.perf_counter()
            free_run(engine, free)
            free_s = time.perf_counter() - f0
            try:
                msg = json.loads(line)
            except (ValueError, RecursionError):
                msg = None
            before = engine.index
            c0, t0 = time.process_time(), time.perf_counter()
            reply, note = AW.handle(engine, pub, rows, msg)
            dt, cpu = time.perf_counter() - t0, time.process_time() - c0
            if note:
                print(f"malformed: {note}", file=sys.stderr, flush=True)
            op = msg.get("op") if isinstance(msg, dict) else None
            perf.append({"op": str(op), "seconds": dt})
            book["turns"].append({"turn": book["ledger"].turns, "op": str(op), "gap_s": gap, "free": free, "free_s": free_s,
                                  "sweeps": engine.index - before, "wall_s": dt, "cpu_s": cpu, "index": engine.index})
            conn.sendall((json.dumps(reply) + "\n").encode())
            last = time.monotonic()
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
    rows, perf, book = [], [], {"ledger": WC.START, "turns": []}
    label = AW.time_label(plug.DYNAMICS)
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    edge = {"time": label, "wire": AW.WIRE, "index": 0, "K_c": engine.K_c(0), "drift": world.drift.table, "hidden": world.hidden}
    (run_dir / "edge.json").write_text(json.dumps(edge, sort_keys=True))  # the truth is written here and at exit, nowhere else
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    lsock = socket.socket()
    try:
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind(("127.0.0.1", env.port))
        lsock.listen(4)
        while True:
            conn, _ = lsock.accept()
            serve_connection(conn, engine, pub, rows, perf, world.world_clock, book)
    finally:
        lsock.close()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "truth.json").write_text(json.dumps({"time": label, "wire": AW.WIRE, "rows": rows}))
        (run_dir / "perf.json").write_text(json.dumps({"time": label, "calls": perf}))
        (run_dir / "turns.json").write_text(json.dumps({"time": label, "wire": AW.WIRE, "world_clock": world.world_clock.table,
                                                        "turns": book["turns"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
