"""Plan 1511 test harness: light, stdlib + pytest. Process spawn/reap, fake server, latency proxy.
The worktree root is the import root. Every fixture that spawns a process reaps it in teardown, even on failure."""
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLUGIN_DIR = ROOT / "system-instantiated" / "plugins" / "at"
PROC_TIMEOUT = 120  # the one liveness home: harness kills a spawned process after 120 s


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_bound(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def toml_dumps(d):
    def v(x):
        if isinstance(x, bool):
            return "true" if x else "false"
        if isinstance(x, str):
            return json.dumps(x)
        if isinstance(x, (list, tuple)):
            return "[" + ", ".join(v(i) for i in x) + "]"
        return repr(x)
    return "".join(f"{k} = {v(x)}\n" for k, x in d.items())


GOLDEN_AT = dict(L_blocks=9, L4=0.14, burn=400, seed=22, k=6, nlev=1, knobs_K=[0.20, 0.50], w=0.02,
                 index_unit="sweep", index_kind="sample_counter")
GOLDEN_TAU = dict(value=67, source="inputs/b7-at-line/m.toml interval b=400 > 6*tau_int => tau_int<66.7; v0 uses the implied ceiling",
                  stamp="the reviewer 2026-11-14")
GOLDEN_NEEDLE = dict(host="127.0.0.1", port=8787, needle_structure="margin-constant-v0", u=0.0, du=0.01, N=8, n=450)


def make_configs(tmp, at=None, needle=None, port=None, tau=None, run_root=None):
    """write at.toml + tau-v0.toml + environment.toml + needle.toml into tmp; return dict of paths."""
    tmp = Path(tmp)
    port = port or free_port()
    d = tmp / "plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "at.toml").write_text(toml_dumps({**GOLDEN_AT, **(at or {})}))
    (d / "tau-v0.toml").write_text(toml_dumps({**GOLDEN_TAU, **(tau or {})}))
    envp = tmp / "environment.toml"
    envp.write_text(toml_dumps(dict(system="at", port=port, run_dir_root=str(run_root or tmp / "out"))))
    nd = tmp / "needle.toml"
    nd.write_text(toml_dumps({**GOLDEN_NEEDLE, "port": port, **(needle or {})}))
    return dict(at=d / "at.toml", tau=d / "tau-v0.toml", env=envp, needle=nd, port=port, tmp=tmp,
                out=Path(run_root or tmp / "out"))


@contextlib.contextmanager
def real_server(cfg, run_dir=None):
    """spawn the environment server subprocess; wait for its port; reap it in teardown even on failure."""
    run_dir = Path(run_dir or cfg["tmp"] / "rundir")
    run_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([sys.executable, "-m", "environment.server", "--env", str(cfg["env"]), "--at", str(cfg["at"]),
                          "--run-dir", str(run_dir)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        t0 = time.time()
        while not port_bound(cfg["port"]):
            if p.poll() is not None:
                raise RuntimeError("server died: " + p.stderr.read().decode())
            if time.time() - t0 > PROC_TIMEOUT:
                raise RuntimeError("server never bound")
            time.sleep(0.05)
        yield p
    finally:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        if p.stderr:
            p.stderr.close()


class Wire:
    """a raw test-side client to the server: send a dict, read one line."""
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port))
        self.f = self.s.makefile("r", encoding="utf-8", newline="\n")

    def call(self, msg):
        self.s.sendall((json.dumps(msg) + "\n").encode())
        return json.loads(self.f.readline())

    def raw(self, line):
        self.s.sendall(line.encode())
        return self.f.readline()

    def close(self):
        self.f.close()
        self.s.close()


class FakeServer:
    """a scripted server on a loopback port. responder(msg_or_None, raw_line) -> str line | list[str] | None (silent) | 'EOF' (close).
    Records every received line in .seen. Faults are SUBSTITUTED replies, never withheld ones."""
    def __init__(self, responder, port=None):
        self.responder = responder
        self.port = port or free_port()
        self.seen = []
        self.lsock = socket.socket()
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind(("127.0.0.1", self.port))
        self.lsock.listen(4)
        self.lsock.settimeout(0.2)
        self.stop = threading.Event()
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        while not self.stop.is_set():
            try:
                c, _ = self.lsock.accept()
            except (socket.timeout, OSError):
                continue
            try:
                self._serve(c)
            finally:
                c.close()

    def _serve(self, c):
        f = c.makefile("r", encoding="utf-8", newline="\n")
        while not self.stop.is_set():
            line = f.readline()
            if not line:
                return
            self.seen.append(line.rstrip("\n"))
            try:
                msg = json.loads(line)
            except ValueError:
                msg = None
            out = self.responder(msg, line)
            if out == "EOF":
                return
            if out is None:
                continue
            for o in ([out] if isinstance(out, str) else out):
                c.sendall((o + "\n").encode())

    def close(self):
        self.stop.set()
        self.th.join(5)
        self.lsock.close()

    @property
    def ops(self):
        out = []
        for s in self.seen:
            try:
                out.append(json.loads(s).get("op"))
            except Exception:
                out.append(None)
        return out


@contextlib.contextmanager
def fake_server(responder):
    fs = FakeServer(responder)
    try:
        yield fs
    finally:
        fs.close()


def honest_declared(drop=(), **over):
    d = {"op": "declared", "knobs_K": [0.20, 0.50], "ordered_side": "+K", "L": 27, "tau": 67, "k": 6,
         "index_unit": "sweep", "index_kind": "sample_counter", "observable": "E2"}
    d.update(over)
    return {k: v for k, v in d.items() if k not in drop}


def honest_responder(declared=None, edge=None, index_box=None, e2=-100.0):
    """a minimal honest fake: tracks the cumulative-sweep index; E2 constant."""
    box = index_box if index_box is not None else {"i": 0}
    declared = declared or honest_declared()
    edge = edge or {"op": "edge", "K_c": 0.34888, "w": 0.02}

    def r(msg, raw):
        if msg is None or not isinstance(msg, dict):
            return json.dumps({"op": "nev", "index": box["i"]})
        op = msg.get("op")
        if op == "declare":
            return json.dumps(declared)
        if op == "where":
            return json.dumps({**edge, "index": box["i"]})
        if op == "set":
            return json.dumps({"op": "ok", "index": box["i"]})
        if op == "step":
            box["i"] += msg["n"]
            return json.dumps({"op": "ok", "index": box["i"]})
        if op == "sense":
            return json.dumps({"op": "obs", "E2": e2, "index": box["i"]})
        return json.dumps({"op": "nev", "index": box["i"]})
    return r


class LatencyProxy:
    """a test-side proxy between needle and a real/fake server; delays server->client lines. Optional per-line transform
    (return a line, or 'EOF' to cut). Sleeps live here (test side) — never in the needle."""
    def __init__(self, upstream_port, delay=0.0, transform=None):
        self.up = upstream_port
        self.delay = delay
        self.transform = transform
        self.port = free_port()
        self.lsock = socket.socket()
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lsock.bind(("127.0.0.1", self.port))
        self.lsock.listen(2)
        self.lsock.settimeout(0.2)
        self.stop = threading.Event()
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()
        self.n = 0

    def _run(self):
        while not self.stop.is_set():
            try:
                c, _ = self.lsock.accept()
            except (socket.timeout, OSError):
                continue
            up = socket.create_connection(("127.0.0.1", self.up))
            cf, uf = c.makefile("r", encoding="utf-8", newline="\n"), up.makefile("r", encoding="utf-8", newline="\n")
            try:
                while not self.stop.is_set():
                    line = cf.readline()
                    if not line:
                        break
                    up.sendall(line.encode())
                    rep = uf.readline()
                    if not rep:
                        break
                    self.n += 1
                    if self.delay:
                        time.sleep(self.delay)
                    if self.transform:
                        rep = self.transform(self.n, line, rep.rstrip("\n"))
                        if rep == "EOF":
                            break
                        rep += "\n"
                    c.sendall(rep.encode())
            except OSError:
                pass
            finally:
                for x in (cf, uf, c, up):
                    with contextlib.suppress(Exception):
                        x.close()

    def close(self):
        self.stop.set()
        self.th.join(5)
        self.lsock.close()


@contextlib.contextmanager
def latency_proxy(upstream_port, delay=0.0, transform=None):
    p = LatencyProxy(upstream_port, delay, transform)
    try:
        yield p
    finally:
        p.close()
