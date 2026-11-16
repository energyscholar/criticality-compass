"""Plan 1546: the System-neutral blind server (contract/SCHEMA-1546.md section 8). It names no System and no physics: it loads
plugins/NAME/blind.py, requires the whole face, and serves the frozen op table through the frozen serving loop.
Entry: python -m environment.blind_server2 --system NAME --world WORLD.toml --port P --run-dir DIR
Start order: port, system, world, bind (no listen), burn, write edge.json, listen. Every start fault is exit 2, one line."""
import importlib.util
import json
import re
import signal
import socket
import sys
from pathlib import Path

from environment import blind_server
from environment import config as C

FACE = ("Refused", "load_world", "init_blind", "declared", "truth", "measure_moments")
NAME = re.compile(r"[a-z][a-z0-9_]*")


class Fault(Exception):
    def __init__(self, field, detail):
        super().__init__(detail)
        self.field, self.detail = field, detail


def parse_port(text):
    if not (text.isascii() and text.isdigit()) or not 1 <= int(text) <= 65535:
        raise Fault("port", f"not a decimal integer in 1..65535: {text!r}")
    return int(text)


def load_face(name):
    f = C.plugin_dir(name) / "blind.py" if NAME.fullmatch(name) else None
    if f is None or not f.is_file():
        raise Fault("system", f"no blind face for {name!r}")
    spec = importlib.util.spec_from_file_location(f"blind_{name}", f)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # a face that cannot even load is not a face
        raise Fault("system", f"blind.py of {name!r} does not load: {type(e).__name__}")
    missing = [n for n in FACE if not hasattr(mod, n)]
    if missing:
        raise Fault("system", f"blind.py of {name!r} lacks {missing}")
    return mod


def args_of(argv):
    """-> {flag: value}; every flag required, none repeated, none unknown."""
    want = ("--system", "--world", "--port", "--run-dir")
    if len(argv) != 2 * len(want) or sorted(argv[0::2]) != sorted(want):
        raise Fault("args", f"expected exactly {' '.join(want)}")
    return dict(zip(argv[0::2], argv[1::2]))


def start(argv):
    a = args_of(argv)
    port = parse_port(a["--port"])
    face = load_face(a["--system"])
    world = face.load_world(a["--world"])
    if isinstance(world, face.Refused):
        raise Fault(world.field, world.detail)
    lsock = socket.socket()
    try:
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind(("127.0.0.1", port))
    except OSError as e:
        lsock.close()
        raise Fault("bind", str(e))
    return face, world, lsock, Path(a["--run-dir"])


def main(argv=None):
    try:
        face, world, lsock, run_dir = start(sys.argv[1:] if argv is None else argv)
    except Fault as e:
        print(f"RefusedToStart field={e.field} parse=B detail={' '.join(e.detail.split())}", file=sys.stderr)
        return 2
    state = face.init_blind(world)
    declared = face.declared(world)
    perf = []
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "edge.json").write_text(json.dumps(face.truth(world), sort_keys=True))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        lsock.listen(4)
        while True:
            conn, _ = lsock.accept()
            blind_server.serve_connection(conn, face, state, declared, perf)
    finally:
        lsock.close()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "perf.json").write_text(json.dumps(perf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
