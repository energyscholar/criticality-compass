"""Plan 1569 — Compass stage 4: the 2-D Ising System on the SAME blind face (the apparatus wire of plan 1545), carried by its
declaration and by nothing in `navigator/` (contract/SCHEMA-1569.md). Launches the REAL apparatus server and the REAL
orchestrator. FROZEN: the implementer makes this green; it does not edit this file.

What it pins:
  p01  the Engine face: every plugin the apparatus host serves exports the names of SCHEMA-1569 section 2, and the host
       serves exactly the plugin directories that hold an apparatus.py;
  p02  the port is carried by the declaration: navigator/ and needlestream/ are byte-identical to the base, no file added;
  p03  the host names no observable and no dynamics: the five host files hold no role name, no update rule, no sample floor;
  p04  AT is unchanged on the wire: a fixed call sequence gives byte-identical replies, edge.json and perf.json (pinned at base), and a truth.json whose floats
       are within 4 ulp of the base's and whose every other leaf is identical (the truth values are reproducible to 4 ulp across platforms, and bit-identical on one platform);
  p05  the Ising declaration: the key set of SCHEMA-1545, the Ising roles, its dynamics, and nothing of its kind, field or offset;
  p06  the Ising reading: one list per declared role in the declared order; the sample floor, the roles and the label are the
       plugin's (S = 39 is `nev`; a stub engine with S_MIN 20 and roles of its own is served by the same wire);
  p07  static, lagless, offset 0: the Ising apparatus is bit-identical to the frozen blind face of plan 1546; with an offset
       dK it is the blind face at K + dK; a linear or a step drift of dK acts on every sweep (values and errors);
  p08  the truth: K_c = critical_K - dK(index) on a critical world, None on a field world, in edge.json, every truth row and
       at both ends of every point's window;
  p09  the world file is strict on the plugin's own keys (kind, h_ticks) and the offset's domain;
  p10  the host's environment parse: any plugin with an Engine face; every other rule is environment/config.py's;
  p11  the scorer is a table on the transition: a field world is scored by score_none end to end (no lock, no truth state),
       with exactly its key set, and each count equal to the count in the run's own stream;
  p12  the needle's settings for AT, run on Ising, refuse to start (field M, parse A): the observable is declared, not built in;
  p13  the Ising needle settings differ from their AT twins in exactly the declared keys and values;
  p14  one jackknife: common/jackknife.py equals the frozen jackknife of both plugins;
  p15  the shipped Ising worlds and score file hold the declared numbers: K_c off every midpoint, off the ignite grid, inside
       the range, and offset_K -0.0050.

RED until `system-instantiated/plugins/ising/apparatus.py` exists and the host reads the Engine face.
Run from the repo root:  python contract/test_ising_port.py   (or pytest)
"""
import ast
import hashlib
import importlib.util
import json
import math
import socket
import struct
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PLUGINS = ROOT / "system-instantiated" / "plugins"
ISING = PLUGINS / "ising"
WIRE = "compass-apparatus/1"
TAU = 3.0
ENGINE_FACE = ("PARAMS", "HIDDEN", "ORDERED_SIDE", "ROLES", "DYNAMICS", "S_MIN", "EXTRA_KEYS", "parse_extra", "transition", "Engine")
IROLES = [{"name": "dU4", "role": "crossing", "ordered_sign": "+"}, {"name": "chi", "role": "peak"}]
SW = "algorithmic (Swendsen-Wang)"
DECLARED_KEYS = {"op", "wire", "dials", "pos", "fixed", "ordered_side", "roles", "index", "horizon", "lag", "tau", "k", "L",
                 "index_unit", "index_kind", "clock"}
DIAL = {"name": "K", "lo": 0.30, "hi": 0.60, "T": 300, "max_nudge": 32, "start": 0}
IWORLD = {"kind": "critical", "L_blocks": 3, "burn": 5, "seed": 7, "k": 2, "nlev": 2, "index_unit": "sweep",
          "index_kind": "sample_counter", "lag": 2, "horizon": 20000, "dials": [DIAL], "fixed": {}, "hidden": {"dK": 0.0},
          "drift": {"target": "dK", "law": "none"}}
FIELD = {**IWORLD, "kind": "field", "h_ticks": 1000}
RQ = {"n_eq": 3, "S": 40, "skip": 1}
AT_DIAL = {"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32, "start": 400}
AT_WORLD = {"L_blocks": 3, "burn": 5, "seed": 7, "k": 2, "nlev": 2, "index_unit": "sweep", "index_kind": "sample_counter",
            "lag": 2, "horizon": 20000, "dials": [AT_DIAL], "fixed": {}, "hidden": {"L4": 0.14},
            "drift": {"target": "L4", "law": "linear", "rate": 5.0e-6}}
AT_SEQUENCE = [{"op": "declare"}, {"op": "read", **RQ}, {"op": "nudge", "d": [7], **RQ},
               {"op": "nudge", "d": [-32], "n_eq": 2, "S": 41, "skip": 2}, {"op": "scan", "ticks": [[100], [900], [410]], **RQ},
               {"op": "read", "n_eq": 0, "S": 40, "skip": 1}, {"op": "nudge", "d": [40], **RQ}, {"op": "read", "n_eq": 3, "S": 39, "skip": 1}]
# ---- pinned at base 4df8a87 (the reviewer re-pins at the real base in a dated section of the plan before handoff) ----
# plan 1640 amendment D1: the wire is pinned in two parts. The replies, edge.json and the call log of perf.json are pinned by sha256 (byte-identical on every platform);
# truth.json is pinned as a parsed document (TRUTH_PIN) and compared by _truth_diffs: its K_c values are arcsinh(exp(-2 Lc)) / 2 of a hidden real, and the platform libm
# does not round those correctly, so the truth values are reproducible to 4 ulp across platforms, and bit-identical on one platform.
AT_BYTES = "887de304a3ad5a8d87dca98d3b64a0e1e224a61f1c345d9a5a227adca082a97e"   # sha256 of replies + edge.json + the call log of perf.json (the base's sha with truth.json taken out)
# plan 1640 amendment H': the three parts of that blob, pinned raw, so that a sha mismatch can name the leaf that moved (p04). test_p04d proves they ARE the blob of AT_BYTES.
WIRE_PIN = [
    '{"op": "declared", "wire": "compass-apparatus/1", "dials": [{"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32}], "pos": [400], "fixed": {}, "ordered_side": {"K": "+"}, "roles": [{"name": "D", "role": "crossing", "ordered_sign": "+"}, {"name": "C", "role": "peak"}], "index": 0, "horizon": 20000, "lag": 2, "tau": 3.0, "k": 2, "L": 9, "index_unit": "sweep", "index_kind": "sample_counter", "clock": "algorithmic (Swendsen-Wang)"}\n',
    '{"op": "reading", "pos": [[400]], "window": [[4, 43]], "values": {"D": [-0.054166666666666585], "C": [14.938765432098766]}, "errors": {"D": [0.06478051863440058], "C": [2.025180084656623]}, "index": 43}\n',
    '{"op": "reading", "pos": [[407]], "window": [[47, 86]], "values": {"D": [-0.0986111111111112], "C": [10.77716049382716]}, "errors": {"D": [0.0645292721604858], "C": [3.215228237558521]}, "index": 86}\n',
    '{"op": "reading", "pos": [[375]], "window": [[90, 170]], "values": {"D": [-0.16598915989159885], "C": [11.053267822651126]}, "errors": {"D": [0.057122607032899925], "C": [3.0239093784391784]}, "index": 170}\n',
    '{"op": "reading", "pos": [[100], [900], [410]], "window": [[174, 213], [217, 256], [260, 299]], "values": {"D": [-0.17777777777777776, 0.06631944444444449, -0.043055555555555625], "C": [5.506666666666666, 11.641358024691359, 22.372222222222224]}, "errors": {"D": [0.05143973697406524, 0.020274391640293706, 0.09279689327536499], "C": [1.375190964240504, 8.501809562656737, 4.19189375242485]}, "index": 299}\n',
    '{"op": "reading", "pos": [[410]], "window": [[300, 339]], "values": {"D": [-0.09027777777777785], "C": [14.066049382716049]}, "errors": {"D": [0.08772799359924208], "C": [4.377222695959092]}, "index": 339}\n',
    '{"op": "nev", "index": 339}\n',
    '{"op": "nev", "index": 339}\n',
]   # the raw reply lines, one per AT_SEQUENCE message
EDGE_PIN = '{"K_c": 0.3488838761833377, "drift": {"law": "linear", "rate": 5e-06, "target": "L4"}, "hidden": {"L4": 0.14}, "index": 0, "time": "lag and drift are in algorithmic (Swendsen-Wang) time", "wire": "compass-apparatus/1"}'   # edge.json as the server wrote it
PERF_PIN = '{"calls": [{"op": "declare"}, {"op": "read"}, {"op": "nudge"}, {"op": "nudge"}, {"op": "scan"}, {"op": "read"}, {"op": "nudge"}, {"op": "read"}], "time": "lag and drift are in algorithmic (Swendsen-Wang) time"}'   # the perf string _at_parts builds: the call log with every "sec"/"time" key taken out
ULP_BOUND = 4   # the libm accuracy bound for one exp plus one arcsinh plus one exact halving: at most 1 ulp each, and one more for the composition
TRUTH_PIN = r'''{"time": "lag and drift are in algorithmic (Swendsen-Wang) time", "wire": "compass-apparatus/1", "rows": [{"call": 1, "op": "read", "index": 43, "K_c": 0.34875425989391357, "pos": [400], "actual": [0.30000000000000004], "points": [{"pos": [400], "window": [4, 43], "K_c": [0.348871817357449, 0.34875425989391357], "sampling": 3, "dial": [[0, [400]]]}]}, {"call": 2, "op": "nudge", "index": 86, "K_c": 0.3486246790834067, "pos": [407], "actual": [0.30175], "points": [{"pos": [407], "window": [47, 86], "K_c": [0.34874220436833114, 0.3486246790834067], "sampling": 46, "dial": [[43, [400]], [45, [407]]]}]}, {"call": 3, "op": "nudge", "index": 170, "K_c": 0.34837164683170535, "pos": [375], "actual": [0.29375], "points": [{"pos": [375], "window": [90, 170], "K_c": [0.3486126268582585, 0.34837164683170535], "sampling": 88, "dial": [[86, [407]], [88, [375]]]}]}, {"call": 4, "op": "scan", "index": 299, "K_c": 0.3479833252379394, "pos": [410], "actual": [0.3025], "points": [{"pos": [100], "window": [174, 213], "K_c": [0.3483596010542822, 0.3482421708157279], "sampling": 173, "dial": [[170, [375]], [172, [100]]]}, {"pos": [900], "window": [217, 256], "K_c": [0.3482301283391113, 0.34811273028402806], "sampling": 216, "dial": [[213, [100]], [215, [900]]]}, {"pos": [410], "window": [260, 299], "K_c": [0.3481006911083425, 0.3479833252379394], "sampling": 259, "dial": [[256, [900]], [258, [410]]]}]}, {"call": 5, "op": "read", "index": 339, "K_c": 0.3478629803104053, "pos": [410], "actual": [0.3025], "points": [{"pos": [410], "window": [300, 339], "K_c": [0.3479803162404928, 0.3478629803104053], "sampling": 299, "dial": [[299, [410]]]}]}]}'''   # truth.json as the base wrote it (macOS), unchanged
TREE_PINS = "1afc8bb5734b45cb864c4720db836a5dca02c30e7b19cc1f7068db26a3800d94"
HOST = ("environment/apparatus_wire.py", "environment/apparatus_server.py", "environment/apparatus_config.py",
        "environment/run_hold.py", "environment/hold_score.py")
NAMES = {"D", "C", "Gs", "G", "dU4", "U4", "chi", "M", "E", "heal", "L4", "dK", "h", "h_ticks", "field", "critical"}
SETTINGS_DIFF = {("M", "observable"): "dU4", ("S",): 1500, ("ignite", "S"): 400}      # SCHEMA-1569 section 7


# ---------------------------------------------------------------- plumbing
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    return "{" + ", ".join(f"{k} = {_toml(x)}" for k, x in v.items()) + "}"


def _write(tmp, port, world, system):
    d = tmp / f"plugins_{system}"; d.mkdir(parents=True, exist_ok=True)
    env, at = tmp / "environment.toml", d / f"{system}-apparatus.toml"
    env.write_text(f'system = "{system}"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    at.write_text("".join(f"{k} = {_toml(v)}\n" for k, v in world.items()))
    (d / "tau-v0.toml").write_text(f"value = {TAU}\n")
    return env, at


class _Conn:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=120)
        self.rf = self.s.makefile("r", encoding="utf-8", newline="\n")

    def raw(self, line):
        self.s.sendall(line.encode() + b"\n")
        out = self.rf.readline(); assert out, "server closed unexpectedly"
        return out

    def ask(self, msg):
        return json.loads(self.raw(json.dumps(msg)))


def _server(tmp, world, system="ising"):
    port = _free_port(); env, at = _write(tmp, port, world, system)
    run_dir = tmp / "run"
    proc = subprocess.Popen([sys.executable, "-m", "environment.apparatus_server", "--env", str(env), "--at", str(at), "--run-dir", str(run_dir)],
                            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        if proc.poll() is not None:
            raise AssertionError(f"apparatus server exited early rc={proc.returncode}\n{proc.communicate()[1][-800:]}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return proc, _Conn(port), run_dir
        except OSError:
            time.sleep(0.05)
    proc.kill(); raise AssertionError("the apparatus server never bound its port")


def _stop(proc, c):
    try:
        c.s.close()
    except OSError:
        pass
    proc.terminate(); proc.wait(timeout=30)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _AC():
    from environment import apparatus_config as AC
    return AC


def _tick(d, t):
    return d["lo"] + t * (d["hi"] - d["lo"]) / d["T"]


def _tree_digest():
    out = {}
    for top in ("navigator", "needlestream"):
        for p in sorted((ROOT / top).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                out[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest(), out


def _ordered(x):
    """A finite double as an integer that is monotone in the double: the IEEE bit pattern as int64, negatives folded about zero (so -0.0 and 0.0 are the same point)."""
    i = struct.unpack("<q", struct.pack("<d", x))[0]
    return -(1 << 63) - i if i < 0 else i


def _ulp_distance(a, b):
    """The number of representable doubles between a and b: an integer, from the bit patterns, never a difference of values."""
    return abs(_ordered(a) - _ordered(b))


def _step_ulp(x, n):
    """The double n steps from x (n may be negative), by the same ordering."""
    i = _ordered(x) + n
    return struct.unpack("<d", struct.pack("<q", -(1 << 63) - i if i < 0 else i))[0]


def _truth_diffs(want, got, path="truth"):
    """The declared comparison type of truth.json: same keys, same list lengths, every non-float leaf identical (type included), every float leaf within ULP_BOUND ulp."""
    if isinstance(want, dict) and isinstance(got, dict):
        if want.keys() != got.keys():
            return [f"{path}: keys {sorted(want)} != {sorted(got)}"]
        return [d for k in want for d in _truth_diffs(want[k], got[k], f"{path}/{k}")]
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return [f"{path}: length {len(want)} != {len(got)}"]
        return [d for i, (a, b) in enumerate(zip(want, got)) for d in _truth_diffs(a, b, f"{path}[{i}]")]
    if isinstance(want, float) and isinstance(got, float):
        if not (math.isfinite(want) and math.isfinite(got)):
            return [] if repr(want) == repr(got) else [f"{path}: {want!r} != {got!r}"]
        d = _ulp_distance(want, got)
        return [] if d <= ULP_BOUND else [f"{path}: {want!r} vs {got!r} is {d} ulp apart (bound {ULP_BOUND})"]
    return [] if type(want) is type(got) and want == got else [f"{path}: {want!r} != {got!r}"]


def _at_parts(tmp):
    """The three parts of the AT blob, as _at_bytes has always joined them: (the raw reply lines, edge.json text, the perf string). Plan 1640 amendment H': p04 names the part and leaf that differ."""
    proc, c, run = _server(tmp, AT_WORLD, "at")
    try:
        lines = [c.raw(json.dumps(m)) for m in AT_SEQUENCE]
    finally:
        _stop(proc, c)
    perf = json.loads((run / "perf.json").read_text())
    perf_s = json.dumps({"time": perf["time"], "calls": [{k: v for k, v in r.items() if "sec" not in k and "time" not in k} for r in perf["calls"]]}, sort_keys=True)
    return lines, (run / "edge.json").read_text(), perf_s


def _parts_sha(parts):
    replies, edge, perf = parts
    return hashlib.sha256(("".join(replies) + edge + perf).encode()).hexdigest()


def _at_bytes(tmp):
    parts = _at_parts(tmp)
    return _parts_sha(parts), json.loads((tmp / "run" / "truth.json").read_text())


def _leaf_diffs(want, got, path=""):
    """Every differing leaf of two parsed documents, with NO tolerance: 'path: want ... got ...' (and the ulp distance for two finite floats). A missing key, a length change or a type change is a leaf too."""
    if isinstance(want, dict) and isinstance(got, dict):
        out = []
        for k in list(want) + [k for k in got if k not in want]:
            if k in want and k in got:
                out += _leaf_diffs(want[k], got[k], f"{path}/{k}")
            else:
                out.append(f"{path}/{k}: want {want.get(k, '<absent>')!r} got {got.get(k, '<absent>')!r}")
        return out
    if isinstance(want, list) and isinstance(got, list):
        out = [f"{path}: length want {len(want)} got {len(got)}"] if len(want) != len(got) else []
        for i, (a, b) in enumerate(zip(want, got)):
            out += _leaf_diffs(a, b, f"{path}[{i}]")
        return out
    if isinstance(want, float) and isinstance(got, float) and math.isfinite(want) and math.isfinite(got):
        return [] if want == got and repr(want) == repr(got) else [f"{path}: want {want!r} got {got!r} ({_ulp_distance(want, got)} ulp)"]
    return [] if type(want) is type(got) and repr(want) == repr(got) else [f"{path}: want {want!r} got {got!r}"]


def _parts_diffs(want, got):
    """The leaf differences between two (replies, edge, perf) triples, each part parsed as JSON; a part that does not parse is compared as text."""
    def parse(x):
        try:
            return json.loads(x)
        except ValueError:
            return x
    out = []
    for i in range(max(len(want[0]), len(got[0]))):
        if i >= len(want[0]) or i >= len(got[0]):
            out.append(f"reply[{i}]: present in only one of the two")
        else:
            out += _leaf_diffs(parse(want[0][i]), parse(got[0][i]), f"reply[{i}]")
    out += _leaf_diffs(parse(want[1]), parse(got[1]), "edge")
    out += _leaf_diffs(parse(want[2]), parse(got[2]), "perf")
    return out


def _fail_report(name, e):
    """The runner's report of one failure: the one-line FAIL (first line of the message, cut to 300), then the rest of the message, each line indented 4 spaces and cut to 200, up to 30 lines (plan 1640 amendment H')."""
    lines = str(e).splitlines() or [""]
    out = [f"FAIL {name}: {type(e).__name__}: {lines[0][:300]}"]
    out += ["    " + ln[:200] for ln in lines[1:31]]
    return "\n".join(out)


# ---------------------------------------------------------------- the tests
def test_p01_the_engine_face():
    AC = _AC()
    have = tuple(sorted(p.parent.name for p in PLUGINS.glob("*/apparatus.py")))
    assert {"at", "ising"} <= set(have) and AC.systems() == have, (have, getattr(AC, "systems", None))
    for name in have:
        plug = AC.load_apparatus(name)
        missing = [k for k in ENGINE_FACE if not hasattr(plug, k)]
        assert not missing, (name, missing)
        crossing = [r for r in plug.ROLES if r["role"] == "crossing"]
        assert len(crossing) == 1 and len({r["name"] for r in plug.ROLES}) == len(plug.ROLES), (name, plug.ROLES)
        assert type(plug.DYNAMICS) is str and plug.DYNAMICS and type(plug.S_MIN) is int and plug.S_MIN >= 1, name
        assert plug.Engine.S_MIN == plug.S_MIN, name
    at, ising = AC.load_apparatus("at"), AC.load_apparatus("ising")
    assert (at.DYNAMICS, at.S_MIN, tuple(at.EXTRA_KEYS)) == (SW, 40, ()), "the AT face must keep its bytes"
    assert (ising.ROLES, ising.DYNAMICS, ising.S_MIN, ising.PARAMS, ising.ORDERED_SIDE) == (IROLES, SW, 40, ("K",), {"K": "+"})
    assert ising.HIDDEN == {"dK": (-0.1, 0.1)} and set(ising.EXTRA_KEYS) == {"kind", "h_ticks"}


def test_p02_the_port_is_carried_by_the_declaration():
    digest, files = _tree_digest()
    assert digest == TREE_PINS, (f"navigator/ or needlestream/ differs from the base (tree digest {digest[:12]}…); stage 4 ports the "
                                 f"System by its declaration and edits no Navigator file", sorted(files))


def test_p03_the_host_names_no_observable_and_no_dynamics():
    for rel in HOST:
        tree = ast.parse((ROOT / rel).read_text())
        consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        bad = sorted(consts & NAMES) + sorted(c for c in consts if "Swendsen" in c or "Wolff" in c or "Metropolis" in c)
        assert not bad, (rel, bad)
        assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        assert not assigned & {"CLOCK", "TIME_LABEL"}, (rel, assigned & {"CLOCK", "TIME_LABEL"})
    wire = ast.parse((ROOT / "environment/apparatus_wire.py").read_text())
    floors = [n for n in ast.walk(wire) if isinstance(n, ast.Compare) for c in [n.left, *n.comparators]
              if isinstance(c, ast.Constant) and type(c.value) is int and c.value == 40]
    assert not floors and "S_MIN" in ast.unparse(wire), "the sample floor is the engine's S_MIN, not a literal of the wire"


def test_p04_at_is_unchanged_on_the_wire(tmp_path):
    parts = _at_parts(tmp_path)
    got = _parts_sha(parts)
    if got != AT_BYTES:
        diffs = _parts_diffs((WIRE_PIN, EDGE_PIN, PERF_PIN), parts)
        raise AssertionError(f"the AT replies, edge or perf differ from the base (sha256 {got[:12]}…); {len(diffs)} differing leaves, the first {min(len(diffs), 10)}:\n" + "\n".join(diffs[:10]))
    truth = json.loads((tmp_path / "run" / "truth.json").read_text())
    diffs = _truth_diffs(json.loads(TRUTH_PIN), truth)
    assert not diffs, "the AT truth differs from the base: " + "; ".join(diffs[:3])


def _first_leaf(x, path, kinds):
    """(path, container, key) of the first leaf whose type is in kinds, in document order."""
    if isinstance(x, dict):
        items = list(x.items())
    elif isinstance(x, list):
        items = list(enumerate(x))
    else:
        return None
    for k, v in items:
        if isinstance(v, (dict, list)):
            r = _first_leaf(v, f"{path}/{k}" if isinstance(x, dict) else f"{path}[{k}]", kinds)
            if r:
                return r
        elif type(v) in kinds:
            return (f"{path}/{k}" if isinstance(x, dict) else f"{path}[{k}]", x, k)
    return None


def test_p04c_p04_names_the_leaf_it_differs_in(tmp_path):
    """RED, run against p04 itself on the live server run: (a) one edge float moved 1 ulp, (b) one reply field changed. p04 must raise and its message must name the leaf's path."""
    live = _at_parts(tmp_path)
    saved = globals()["_at_parts"]
    try:
        # (a) an edge float, one ulp
        edge = json.loads(live[1]); path, box, key = _first_leaf({"edge": edge}, "", (float,))
        moved = _step_ulp(box[key], 1) if isinstance(box[key], float) else None
        assert moved is not None, "the live edge.json has a float leaf to move"
        box[key] = moved
        want_path = path.replace("/edge", "edge", 1)
        globals()["_at_parts"] = lambda tmp: (live[0], json.dumps(edge), live[2])
        try:
            test_p04_at_is_unchanged_on_the_wire(tmp_path)
            raise AssertionError("p04 must fail when an edge float moves one ulp")
        except AssertionError as e:
            assert want_path in str(e) and "1 ulp" in str(e) and "differing leaves" in str(e), ("p04 did not name the edge leaf", want_path, str(e)[:600])
        # (b) a reply field
        replies = list(live[0]); rep = json.loads(replies[1]); path, box, key = _first_leaf({"reply[1]": rep}, "", (float, str))
        box[key] = box[key] + 1 if isinstance(box[key], float) else box[key] + "X"
        replies[1] = json.dumps(rep) + "\n"
        want_path = "reply[1]" + path[len("/reply[1]"):]
        globals()["_at_parts"] = lambda tmp: (replies, live[1], live[2])
        try:
            test_p04_at_is_unchanged_on_the_wire(tmp_path)
            raise AssertionError("p04 must fail when a reply field changes")
        except AssertionError as e:
            assert want_path in str(e) and "differing leaves" in str(e), ("p04 did not name the reply leaf", want_path, str(e)[:600])
    finally:
        globals()["_at_parts"] = saved


def test_p04d_the_pinned_parts_are_the_pinned_sha():
    """Provenance: the pins, serialised exactly as _at_parts joins them (replies, edge.json, the perf string), are the blob whose sha is AT_BYTES."""
    assert hashlib.sha256(("".join(WIRE_PIN) + EDGE_PIN + PERF_PIN).encode()).hexdigest() == AT_BYTES
    assert len(WIRE_PIN) == len(AT_SEQUENCE) and all(x.endswith("\n") for x in WIRE_PIN), "one raw reply line per message"


def test_p04e_leaf_diffs_has_no_tolerance_and_a_failure_prints_whole():
    assert _leaf_diffs({"a": [1.0, {"b": "x"}]}, {"a": [1.0, {"b": "x"}]}) == []
    d = _leaf_diffs({"a": [1.0, {"b": "x"}]}, {"a": [_step_ulp(1.0, 1), {"b": "y"}]})
    assert len(d) == 2 and d[0].startswith("/a[0]:") and "1 ulp" in d[0] and d[1].startswith("/a[1]/b:"), d
    assert _leaf_diffs({"a": 1}, {"a": 1.0}) != [] and _leaf_diffs({"a": 1}, {}) != [] and _leaf_diffs([1], [1, 2]) != []
    msg = "\n".join(["head"] + [f"leaf{i}" for i in range(11)])
    rep = _fail_report("test_x", AssertionError(msg)).splitlines()
    assert rep[0] == "FAIL test_x: AssertionError: head" and [r.strip() for r in rep[1:]] == [f"leaf{i}" for i in range(11)] and all(r.startswith("    ") for r in rep[1:]), rep
    assert "_fail_report(t.__name__, e)" in Path(__file__).read_text().split("if __name__")[-1], "the runner must use _fail_report"


def test_p04b_the_truth_comparison_can_fail():
    """The comparison type of truth.json can say no (plan 1640 amendment D1): 4 ulp passes, 5 ulp fails, a changed non-float leaf fails, a changed key fails."""
    ref = json.loads(TRUTH_PIN)
    leaf = ref["rows"][0]["K_c"]
    assert _truth_diffs(ref, json.loads(TRUTH_PIN)) == [], "the pin must equal itself"
    for n, ok in ((1, True), (4, True), (5, False), (-4, True), (-5, False)):
        moved = json.loads(TRUTH_PIN); moved["rows"][0]["K_c"] = _step_ulp(leaf, n)
        assert (_truth_diffs(ref, moved) == []) is ok, (n, ok, _truth_diffs(ref, moved))
    moved = json.loads(TRUTH_PIN); moved["rows"][0]["op"] = "scan"
    assert _truth_diffs(ref, moved), "a changed non-float leaf must fail"
    moved = json.loads(TRUTH_PIN); moved["rows"][0]["index"] += 1
    assert _truth_diffs(ref, moved), "a changed integer leaf must fail"
    moved = json.loads(TRUTH_PIN); moved["rows"][0]["extra"] = 1
    assert _truth_diffs(ref, moved), "an added key must fail"
    moved = json.loads(TRUTH_PIN); moved["rows"][0]["K_c"] = 1
    assert _truth_diffs(ref, moved), "a float leaf that became an integer must fail"
    assert _ulp_distance(0.0, -0.0) == 0 and _ulp_distance(1.0, 1.0) == 0 and _ulp_distance(1.0, _step_ulp(1.0, 1)) == 1


def test_p05_the_ising_declaration(tmp_path):
    lines = []
    for n, w in enumerate((IWORLD, FIELD, {**FIELD, "h_ticks": 90}, {**IWORLD, "hidden": {"dK": 0.03}},
                           {**IWORLD, "drift": {"target": "dK", "law": "linear", "rate": -2.0e-6}})):
        proc, c, _ = _server(tmp_path / str(n), w)
        try:
            lines.append(c.raw('{"op": "declare"}'))
        finally:
            _stop(proc, c)
    d = json.loads(lines[0])
    assert d["op"] == "declared" and set(d) == DECLARED_KEYS and d["wire"] == WIRE, sorted(d)
    assert d["roles"] == IROLES and d["clock"] == SW and d["ordered_side"] == {"K": "+"} and d["L"] == 9, d
    assert all(l == lines[0] for l in lines), "the declaration differs between worlds: it leaks the kind, the field or the offset"
    for word in ("K_c", "dK", "hidden", '"kind"', "field", "critical", "h_ticks", "drift", "truth", "0.03"):
        assert word not in lines[0], word


def test_p06_the_ising_reading(tmp_path):
    proc, c, _ = _server(tmp_path, {**IWORLD, "lag": 0})
    try:
        r = c.ask({"op": "scan", "ticks": [[0], [300]], "n_eq": 30, "S": 200, "skip": 1})
        floor = c.ask({"op": "read", "n_eq": 1, "S": 39, "skip": 1})
        ok = c.ask({"op": "read", "n_eq": 1, "S": 40, "skip": 1})
    finally:
        _stop(proc, c)
    assert r["op"] == "reading" and list(r["values"]) == ["dU4", "chi"] and list(r["errors"]) == ["dU4", "chi"], r
    assert all(len(v) == 2 for v in r["values"].values()) and all(e > 0 for v in r["errors"].values() for e in v), r
    assert r["values"]["dU4"][0] < 0 < r["values"]["dU4"][1], ("the crossing role must change sign across K_c", r["values"])
    assert floor["op"] == "nev" and ok["op"] == "reading", (floor, ok)
    # the floor, the roles and the label are the plugin's: a stub engine with S_MIN 20 (below any host floor of 40) and roles of its own (audit F6)
    from environment import apparatus_wire as AW

    class Stub:
        S_MIN, index, pos = 20, 0, [0]

        def run(self, positions, n_eq, S, skip):
            return [{"pos": list(p), "window": [1, 2], "values": {"zeta": 1.0, "eta": 2.0}, "errors": {"zeta": 0.1, "eta": 0.2}}
                    for p in positions], [(0, 0, 2) for _ in positions]

        def truth_row(self, call, op, points, spans):
            return {"call": call}
    pub = AW.Public(dials=({"name": "x", "lo": 0.0, "hi": 1.0, "T": 10, "max_nudge": 2},), fixed={}, ordered_side={"x": "+"},
                    roles=[{"name": "eta", "role": "peak"}, {"name": "zeta", "role": "crossing", "ordered_sign": "+"}],
                    horizon=10 ** 6, lag=0, tau=TAU, k=2, L=9, index_unit="sweep", index_kind="sample_counter", dynamics="stub time")
    rows = []
    no, _ = AW.handle(Stub(), pub, rows, {"op": "read", "n_eq": 0, "S": 19, "skip": 1})
    yes, _ = AW.handle(Stub(), pub, rows, {"op": "read", "n_eq": 0, "S": 20, "skip": 1})
    dec, _ = AW.handle(Stub(), pub, rows, {"op": "declare"})
    assert no["op"] == "nev" and yes["op"] == "reading" and len(rows) == 1, (no, yes, rows)
    assert list(yes["values"]) == ["eta", "zeta"] and list(yes["errors"]) == ["eta", "zeta"], yes
    assert dec["clock"] == "stub time" and AW.time_label("stub time") == "lag and drift are in stub time time", dec


def _blind_reading(K0, Ks, n_eq, S, skip, h=0.0):
    blind = _load(ISING / "blind.py", "ising_blind_p07")
    st = blind.plugin.init(9, K0, h, 5, 7, 2, (-1.0, 2.0))
    m = blind.measure_moments(st, Ks, n_eq, S, skip)
    return m, st.index


def test_p07_the_ising_apparatus_is_the_frozen_blind_face(tmp_path):
    for n, (dK, base) in enumerate(((0.0, IWORLD), (0.0375, IWORLD), (0.0, FIELD))):
        w = {**base, "lag": 0, "hidden": {"dK": dK}}
        ticks = [[100], [140], [233]]
        proc, c, _ = _server(tmp_path / str(n), w)
        try:
            a = c.ask({"op": "scan", "ticks": ticks, **RQ})
        finally:
            _stop(proc, c)
        b, idx = _blind_reading(_tick(DIAL, 0) + dK, [_tick(DIAL, t[0]) + dK for t in ticks], RQ["n_eq"], RQ["S"], RQ["skip"],
                                base.get("h_ticks", 0) / 100000)
        assert a["index"] == idx, (a["index"], idx)
        for j in range(3):
            assert a["values"]["dU4"][j] == b["U4"][j][1] - b["U4"][j][0], ("dU4", dK, j, a["values"]["dU4"][j], b["U4"][j])
            assert a["values"]["chi"][j] == b["chi"][j] and a["errors"]["chi"][j] == b["chi_err"][j], ("chi", dK, j)
    # a drift of dK acts on every sweep (the lattice feels dial + dK + offset(index)): linear, and a step mid-reading (audit F5)
    from common import jackknife as JK
    plugin = _load(ISING / "plugin.py", "ising_plugin_p07")
    for n, (drift, off) in enumerate((({"target": "dK", "law": "linear", "rate": -4.0e-5}, lambda i: -4.0e-5 * i),
                                      ({"target": "dK", "law": "step", "at": 20, "size": 0.05}, lambda i: 0.05 if i >= 20 else 0.0))):
        w = {**IWORLD, "lag": 0, "horizon": 1000, "hidden": {"dK": 0.01}, "drift": drift}
        proc, c, _ = _server(tmp_path / f"drift{n}", w)
        try:
            a = c.ask({"op": "read", **RQ})
        finally:
            _stop(proc, c)
        st = plugin.init(9, _tick(DIAL, 0) + 0.01, 0.0, 5, 7, 2, (-1.0, 2.0))
        N, S = 81, RQ["S"]; M, A, Q = [], [], []
        for i in range(RQ["n_eq"] + S * RQ["skip"]):
            st.K = _tick(DIAL, 0) + (0.01 + off(st.index))
            plugin.step(st, 1)
            if i >= RQ["n_eq"]:
                _, msum, aa, qq = plugin.observe(st.s, 2); M.append(msum / N); A.append(aa); Q.append(qq)
        M, A, Q = np.array(M), np.array(A), np.array(Q)
        u = lambda idx, l: 1.0 - Q[idx, l].mean() / (3.0 * A[idx, l].mean() ** 2)
        d = lambda idx: u(idx, 1) - u(idx, 0)
        chi = lambda idx: N * ((M[idx] ** 2).mean() - np.abs(M[idx]).mean() ** 2)
        every = np.arange(S)
        for role, f in (("dU4", d), ("chi", chi)):
            assert math.isclose(a["values"][role][0], f(every), rel_tol=1e-9, abs_tol=1e-12), (drift["law"], role, a["values"], f(every))
            assert math.isclose(a["errors"][role][0], JK.jackknife(S, f), rel_tol=1e-9, abs_tol=1e-12), (
                drift["law"], role, "the error is the jackknife of the whole statistic", a["errors"], JK.jackknife(S, f))


def test_p08_the_truth(tmp_path):
    plugin = _load(ISING / "plugin.py", "ising_plugin_p08")
    for n, (w, want) in enumerate(((IWORLD, lambda i: plugin.critical_K()), ({**IWORLD, "horizon": 2000, "hidden": {"dK": 0.02}, "drift": {"target": "dK", "law": "linear", "rate": -1.0e-5}},
                                   lambda i: plugin.critical_K() - (0.02 - 1.0e-5 * i)), (FIELD, lambda i: None))):
        proc, c, run = _server(tmp_path / str(n), w)
        try:
            c.ask({"op": "read", **RQ}); c.ask({"op": "nudge", "d": [5], **RQ})
        finally:
            _stop(proc, c)
        edge, truth = json.loads((run / "edge.json").read_text()), json.loads((run / "truth.json").read_text())
        assert set(edge) == {"time", "wire", "index", "K_c", "drift", "hidden"} and edge["time"] == f"lag and drift are in {SW} time", edge
        assert (edge["K_c"] is None) == (want(0) is None) and (want(0) is None or math.isclose(edge["K_c"], want(0), abs_tol=1e-12)), (n, edge)
        assert len(truth["rows"]) == 2, truth
        for r in truth["rows"]:
            got, exp = r["K_c"], want(r["index"])
            assert (got is None) == (exp is None) and (exp is None or math.isclose(got, exp, abs_tol=1e-12)), (n, r["index"], got, exp)
            for p in r["points"]:
                ends = [want(p["window"][0]), want(p["window"][1])]
                assert all((k is None) == (e is None) for k, e in zip(p["K_c"], ends)) and len(p["K_c"]) == 2, (n, p)
                assert all(e is None or math.isclose(k, e, abs_tol=1e-12) for k, e in zip(p["K_c"], ends)), (n, p["window"], p["K_c"], ends)


def test_p09_the_world_file_is_strict(tmp_path):
    AC = _AC()
    bad = [("kind", {k: v for k, v in IWORLD.items() if k != "kind"}), ("kind", {**IWORLD, "kind": "tricritical"}),
           ("kind", {**IWORLD, "kind": 1}), ("h_ticks", {**IWORLD, "kind": "field"}), ("h_ticks", {**FIELD, "h_ticks": 0}),
           ("h_ticks", {**FIELD, "h_ticks": 1.5}), ("h_ticks", {**FIELD, "h_ticks": True}), ("h_ticks", {**FIELD, "h_ticks": 2.0}), ("h_ticks", {**IWORLD, "h_ticks": 90}),
           ("hidden", {**IWORLD, "hidden": {"dK": 0.2}}), ("hidden", {**IWORLD, "hidden": {"L4": 0.14}}),
           ("h", {**IWORLD, "h": 0.01}), ("knobs_K", {**IWORLD, "knobs_K": [0.4, 0.5]})]
    for n, (field, w) in enumerate(bad):
        env, at = _write(tmp_path / str(n), 9, w, "ising")
        got = AC.load_apparatus_cfgs(env, at)
        assert type(got).__name__ == "Malformed", (field, got)
        assert got.field == field or field == "hidden", (field, got)
    env, at = _write(tmp_path / "ok", 9, FIELD, "ising")
    got = AC.load_apparatus_cfgs(env, at)
    assert type(got).__name__ != "Malformed" and got[1].extra == {"kind": "field", "h_ticks": 1000}, got
    # an AT world keeps refusing the Ising keys: the extra keys are the plugin's own
    env, at = _write(tmp_path / "at", 9, {**AT_WORLD, "kind": "critical"}, "at")
    assert type(AC.load_apparatus_cfgs(env, at)).__name__ == "Malformed"


def test_p10_the_environment_parse():
    AC = _AC()
    from environment import config as C
    ok = AC.parse_env({"system": "ising", "port": 10199, "run_dir_root": "runs/"})
    assert type(ok).__name__ != "Malformed" and ok.system == "ising" and ok.port == 10199, ok
    assert type(AC.parse_env({"system": "nope", "port": 10199, "run_dir_root": "runs/"})).__name__ == "Malformed"
    for d in ({"system": "at", "port": 0, "run_dir_root": "runs/"}, {"system": "at", "port": 10199},
              {"system": "at", "port": 10199, "run_dir_root": "runs/", "x": 1}, {"system": "at", "port": "1", "run_dir_root": "runs/"},
              {"system": "at", "port": 10199, "run_dir_root": "runs/"}):
        a, b = AC.parse_env(d), C.parse_env_cfg(d)
        assert type(a).__name__ == type(b).__name__ and (getattr(a, "field", None) == getattr(b, "field", None)) and (
            type(a).__name__ == "Malformed" or a == b), (d, a, b)
        assert type(AC.parse_env({**d, "system": "ising"})).__name__ == type(b).__name__, d


HOLD = {"needle_structure": "hold-pair-v1", "ops": ["declare", "scan", "nudge"], "g": 6, "step": 3, "sigma": 0, "n_eq": 30,
        "S": 200, "skip": 1, "z": 2.0, "ignite": {"steps": [50, 10], "S": 100, "margin": 1, "n_eq": 30}, "approach": {"S": 40, "n_eq": 6},
        "lost": 3, "M": {"observable": "dU4",
                         "node": "one reading of the observable: its value at one dial tick, over the window and at the index the wire reports",
                         "relation": "path", "edge": "from each reading of a drop to the reading the wire served just before it",
                         "direction": "the wire's index: the source is the later reading, so the difference is current minus prior",
                         "provenance": "steering (declared under the Origin's ruling, pending kernel revision)",
                         "transform": "none", "rho_base": "not-declared", "chi_0": "not-declared"}}


def _run_hold(tmp, world, needle):
    env, at = _write(tmp, _free_port(), world, "ising")
    (tmp / "hold.toml").write_text("".join(f"{k} = {_toml(v)}\n" for k, v in needle.items() if not isinstance(v, dict))
                                   + "".join(f"\n[{k}]\n" + "".join(f"{a} = {_toml(b)}\n" for a, b in v.items()) for k, v in needle.items() if isinstance(v, dict)))
    (tmp / "score.toml").write_text('offset_K = -0.02\nout_run = 3\nplan = "1569"\n')
    res = subprocess.run([sys.executable, "-m", "environment.run_hold", "--env", str(env), "--at", str(at), "--needle", str(tmp / "hold.toml"),
                          "--score", str(tmp / "score.toml")], cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    runs = sorted((tmp / "runs").iterdir()) if (tmp / "runs").exists() else []
    return res, (runs[0] if runs else None)


def test_p11_the_scorer_is_a_table_on_the_transition(tmp_path):
    from environment import hold_score as HS
    assert set(HS.SCORER) == {"continuous", "none"} and HS.SCORER["continuous"] == (HS.score, HS.overlay), HS.SCORER
    short = {"horizon": 6000}
    res, run = _run_hold(tmp_path / "c", {**IWORLD, **short}, HOLD)
    assert res.returncode == 0 and run is not None, (res.returncode, res.stderr[-800:])
    sc = json.loads((run / "score.json").read_text())
    assert sc["lock"] in HS.LOCKS and "transition" not in sc, sc
    # score_none's counts, on a stream that HAS hold steps: they must be the stream's, not a constant (audit F4)
    from needlestream import read_hold as RHD
    crit = [json.loads(l) for l in (run / "report.jsonl").read_text().splitlines()]
    nh = sum(1 for x in crit if x.get("phase") == "hold" and x.get("evaluated"))
    none = HS.score_none(RHD.read((run / "report.jsonl").read_text()), json.loads((run / "truth.json").read_text())["rows"],
                         HS.parse_score({"offset_K": -0.02, "out_run": 3, "plan": "1569"}))
    assert nh >= 1 and none["hold_steps"] == nh == sc["hold_steps"] and sum(none["calls"].values()) == nh, (nh, none, sc["hold_steps"])
    res, run = _run_hold(tmp_path / "f", {**FIELD, **short}, HOLD)
    assert res.returncode == 0 and run is not None, (res.returncode, res.stderr[-800:])
    sc, over = json.loads((run / "score.json").read_text()), json.loads((run / "map-truth.json").read_text())
    assert sc["transition"] == "none" and sc["lock"] == HS.NO_TRANSITION and type(sc["hold_steps"]) is int, sc
    assert set(sc) == {"plan", "transition", "feedback", "outcome", "lock", "hold_steps", "segments", "calls", "ignite_steps", "run_id"}, sorted(sc)
    lines = [json.loads(l) for l in (run / "report.jsonl").read_text().splitlines()]
    steps = [x for x in lines if "phase" in x]
    hold = [x for x in steps if x["phase"] == "hold" and x["evaluated"]]
    kinds = {}
    for x in hold:
        kinds[x["verdict"][0]["kind"]] = kinds.get(x["verdict"][0]["kind"], 0) + 1
    assert sc["hold_steps"] == len(hold) and sc["calls"] == kinds, (sc, len(hold), kinds)
    assert sc["ignite_steps"] == sum(1 for x in steps if x["phase"] == "ignite") >= 1 and sc["outcome"] == lines[-1]["kind"], sc
    assert sc["segments"] == len({x[{"ignite": "grid", "approach": "leg", "hold": "pair"}[x["phase"]]]["segment"] for x in steps if x["evaluated"]}), sc
    places = len((run / "map.jsonl").read_text().splitlines()) - 1
    assert over["places"] == [] and over["counts"] == {HS.NO_TRANSITION: places}, (over["counts"], places)
    themap = (run / "map.jsonl").read_text()
    for word in ("K_c", "truth", "h_ticks", "field", "dK"):
        assert word not in themap, word


def test_p12_the_at_settings_refuse_on_ising(tmp_path):
    at = tomllib.loads((ROOT / "navigator" / "hold-settled.toml").read_text())
    res, run = _run_hold(tmp_path, IWORLD, at)
    assert res.returncode == 2 and "RefusedToStart field=M parse=A" in res.stderr, (res.returncode, res.stderr[-400:])
    assert json.loads((run / "refused.json").read_text()) == {"kind": "RefusedToStart", "field": "M", "parse": "A"}
    ok, _ = _run_hold(tmp_path / "ok", {**IWORLD, "horizon": 3000}, HOLD)
    assert ok.returncode == 0, ok.stderr[-400:]


def _flat(d, pre=()):
    out = {}
    for k, v in d.items():
        out.update(_flat(v, pre + (k,)) if isinstance(v, dict) else {pre + (k,): v})
    return out


def test_p13_the_ising_settings_differ_in_the_declared_keys():
    here = ROOT / "needle-settings" / "ising"
    assert sorted(p.name for p in here.glob("*.toml")) == ["hold-mid.toml", "hold-settled-off.toml", "hold-settled.toml"], sorted(here.iterdir())
    for name in ("hold-settled.toml", "hold-mid.toml", "hold-settled-off.toml"):
        a = _flat(tomllib.loads((ROOT / "navigator" / name).read_text()))
        b = _flat(tomllib.loads((here / name).read_text()))
        assert set(a) == set(b), (name, set(a) ^ set(b))
        diff = {k: b[k] for k in a if a[k] != b[k]}
        assert diff == SETTINGS_DIFF, (name, diff)


def test_p14_one_jackknife():
    from common import jackknife as JK
    assert JK.BLOCKS == 20
    rng = np.random.default_rng(3)
    X = rng.normal(size=(333, 2))
    for plug in ("at", "ising"):
        blind = _load(PLUGINS / plug / "blind.py", f"blind_{plug}_p14")
        for f in (lambda i: X[i, 0].mean(), lambda i: X[i, 1].var() / (X[i, 0].mean() ** 2 + 1)):
            assert JK.jackknife(333, f) == blind._jackknife(333, f), plug
    src = (ISING / "apparatus.py").read_text()
    assert "common.jackknife" in src and "def _jackknife" not in src and "np.array_split" not in src, "the Ising engine must use the one jackknife"


WORLDS = {     # file: (kind, h_ticks, lo, hi, T, start, drift law, rate)
    "ising-apparatus.toml": ("critical", None, 0.42, 0.545, 500, 0, "linear", -1.3e-7),
    "ising-apparatus-static.toml": ("critical", None, 0.42, 0.545, 500, 0, "none", None),
    "ising-apparatus-static-r2.toml": ("critical", None, 0.40, 0.50, 400, 400, "none", None),
    "ising-apparatus-static-r3.toml": ("critical", None, 0.425, 0.475, 200, 100, "none", None),
    "ising-apparatus-field.toml": ("field", 1000, 0.42, 0.545, 500, 0, "none", None),
    "ising-apparatus-field-hard.toml": ("field", 90, 0.42, 0.545, 500, 0, "none", None),
}


def test_p15_the_shipped_worlds_hold_the_declared_numbers(tmp_path):
    AC = _AC()
    plugin = _load(ISING / "plugin.py", "ising_plugin_p15")
    Kc = plugin.critical_K()
    assert (ISING / "tau-v0.toml").exists()
    for name, (kind, h, lo, hi, T, start, law, rate) in WORLDS.items():
        d = tomllib.loads((ISING / name).read_text())
        assert d["kind"] == kind and d.get("h_ticks") == h, name
        assert d["dials"] == [{"name": "K", "lo": lo, "hi": hi, "T": T, "max_nudge": 32, "start": start}], (name, d["dials"])
        assert (d["L_blocks"], d["nlev"], d["lag"], d["horizon"], d["hidden"], d["fixed"]) == (27, 2, 48, 200000, {"dK": 0.0}, {}), name
        assert d["drift"] == ({"target": "dK", "law": law, "rate": rate} if rate is not None else {"target": "dK", "law": law}), name
        env, _ = _write(tmp_path / name, 9, {}, "ising")
        assert type(AC.load_apparatus_cfgs(env, ISING / name)).__name__ != "Malformed", name
        t = (Kc - lo) / (hi - lo) * T
        assert 0 < t < T and abs(t - T / 2) > 20 and abs(t - round(t)) > 0.2 and min(t % 100, 100 - t % 100) > 10, (name, t)
    score = tomllib.loads((ROOT / "environment" / "hold-score-ising.toml").read_text())
    assert score == {"offset_K": -0.0050, "out_run": 3, "plan": "1569"}, ("SCHEMA-1569 section 9: the declared offset", score)
    seen = {((Kc - WORLDS[n][2]) / (WORLDS[n][3] - WORLDS[n][2])) for n in WORLDS}
    assert len({round(x, 3) for x in seen}) == 3, ("three distinct off-centre ranges", seen)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_p")]

if __name__ == "__main__":
    import inspect
    import tempfile
    passed, want = 0, set(sys.argv[1:])
    TESTS = [t for t in TESTS if not want or t.__name__.split("_")[1] in want]
    for t in TESTS:
        try:
            if "tmp_path" in inspect.signature(t).parameters:
                with tempfile.TemporaryDirectory() as d:
                    t(Path(d))
            else:
                t()
            print("PASS", t.__name__); passed += 1
        except Exception as e:  # noqa: BLE001
            print(_fail_report(t.__name__, e))
    print(f"{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
