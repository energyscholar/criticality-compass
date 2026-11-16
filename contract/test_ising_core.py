"""Plan 1546 — the 2-D Ising System plugin: the PHYSICS CORE and the world table (contract/SCHEMA-1546.md §2-§6).
FROZEN: the Generator makes this green; it does not edit this file. No server is started here.

What it pins:
  k01  `plugin.sweep` IS the declared Swendsen-Wang update (SCHEMA §3), bit for bit, field and no field — a local
       (Metropolis / heat-bath) update under the same label fails, and so does another coupling convention;
  k02  the declared update samples the declared Boltzmann weight: a 3 x 3 torus against exact enumeration of all 512
       states, with and without a field (this is what makes K mean K: p = 1 - exp(-2K), each bond counted once);
  k03  `plugin.observe` against explicit loops;
  k04  the System's constants: the update label, the ordered side, the dial, the exact critical coupling;
  k05  init / set / step: the start, the knob refusal value, the index; a measure outside the knobs is `None`, whole;
  k06  the truth is a total table on the world kind; a field world has NO transition, however weak the field;
  k07  the world parser is total: every fault is a `Refused` value naming its field, nothing raises, no default is filled;
       a world is `critical` (no field key exists) or `field` (a whole number of ticks >= 1): a zero, negative or
       signed-zero field cannot be written;
  k08  purity: the core knows no wire and imports nothing of the navigator or the environment.

RED until `system-instantiated/plugins/ising/` exists.
Run from the repo root:  python contract/test_ising_core.py   (or pytest)
"""
import ast
import dataclasses
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ISING = ROOT / "system-instantiated" / "plugins" / "ising"
KC = math.log(1.0 + math.sqrt(2.0)) / 2.0


def _load(name):
    spec = importlib.util.spec_from_file_location(f"t1546_{name}", ISING / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- the declared update (SCHEMA-1546 §3), written out a second time with a union-find: the test's own oracle --------------
def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def ref_sweep(s, K, h, rng):
    L = s.shape[0]
    N = L * L
    f = [int(v) for v in s.ravel()]
    u_r, u_d, u_g = rng.random(N), rng.random(N), rng.random(N)
    p, pg = 1.0 - math.exp(-2.0 * K), 1.0 - math.exp(-2.0 * h)
    parent = list(range(N + 1))                      # node N is the ghost
    for i in range(L):
        for j in range(L):
            x, r, d = i * L + j, i * L + (j + 1) % L, ((i + 1) % L) * L + j
            if f[x] == f[r] and u_r[x] < p:
                parent[_find(parent, x)] = _find(parent, r)
            if f[x] == f[d] and u_d[x] < p:
                parent[_find(parent, x)] = _find(parent, d)
            if f[x] == 1 and u_g[x] < pg:
                parent[_find(parent, x)] = _find(parent, N)
    label, roots = {}, [_find(parent, x) for x in range(N + 1)]
    for x in range(N + 1):                           # clusters are numbered by their smallest node
        label.setdefault(roots[x], len(label))
    u_c = rng.random(len(label))
    ghost = label[roots[N]]
    out = [(-f[x] if (u_c[label[roots[x]]] < 0.5 and label[roots[x]] != ghost) else f[x]) for x in range(N)]
    return np.array(out).reshape(L, L)


def ref_init(L, K, h, burn, seed):
    rng = np.random.default_rng(seed)
    s = rng.choice(np.array([-1, 1]), size=(L, L))
    for _ in range(burn):
        s = ref_sweep(s, K, h, rng)
    return s, rng


def test_k01_sweep_is_the_declared_swendsen_wang():
    plugin = _load("plugin")
    for L, K, h, seed in ((6, 0.30, 0.0, 1), (9, KC, 0.0, 2), (9, 0.60, 0.0, 3), (6, 0.40, 0.05, 4), (9, 0.20, 1.0, 5),
                          (3, 0.44, 0.0, 6), (9, 0.0, 0.0, 7)):
        ra, rb = np.random.default_rng(seed), np.random.default_rng(seed)
        a = ra.choice(np.array([-1, 1]), size=(L, L))
        b = rb.choice(np.array([-1, 1]), size=(L, L))
        for n in range(4):
            before = a.copy()
            new = plugin.sweep(a, K, h, ra)
            assert new is not a and np.array_equal(a, before), "sweep returns a NEW array and leaves its input alone"
            a, b = new, ref_sweep(b, K, h, rb)
            assert a.shape == (L, L) and np.array_equal(np.asarray(a), b), f"sweep {n} differs: L={L} K={K} h={h}"
            assert set(np.unique(a)) <= {-1, 1}
        assert ra.random() == rb.random(), f"the update drew a different number of random values: L={L} K={K} h={h}"


def _exact(K, h):
    """<bonds>/N, <m^2>, <|m|> on the 3 x 3 torus by enumeration of 2**9 states."""
    Z = eb = em2 = ema = 0.0
    for bits in itertools.product((-1, 1), repeat=9):
        s = np.array(bits).reshape(3, 3)
        bonds = int((s * np.roll(s, -1, 1)).sum() + (s * np.roll(s, -1, 0)).sum())
        m = int(s.sum())
        w = math.exp(K * bonds + h * m)
        Z += w
        eb += w * bonds / 9
        em2 += w * (m / 9) ** 2
        ema += w * abs(m) / 9
    return eb / Z, em2 / Z, ema / Z


def test_k02_the_update_samples_the_declared_weight():
    plugin = _load("plugin")
    for K, h, seed in ((0.30, 0.0, 11), (0.50, 0.0, 12), (0.40, 0.10, 13), (0.20, 0.50, 14)):
        rng = np.random.default_rng(seed)
        s = rng.choice(np.array([-1, 1]), size=(3, 3))
        for _ in range(200):
            s = plugin.sweep(s, K, h, rng)
        n, sb, sm2, sma, smsigned = 60000, 0.0, 0.0, 0.0, 0.0
        for _ in range(n):
            s = plugin.sweep(s, K, h, rng)
            bonds, msum, _, _ = plugin.observe(s, 1)
            sb += bonds / 9
            sm2 += (msum / 9) ** 2
            sma += abs(msum) / 9
            smsigned += msum / 9
        eb, em2, ema = _exact(K, h)
        for name, got, want in (("bonds/N", sb / n, eb), ("m^2", sm2 / n, em2), ("|m|", sma / n, ema)):
            assert abs(got - want) <= 0.03, f"K={K} h={h}: <{name}> = {got:.4f}, exact {want:.4f}"
        assert (smsigned / n > 0.2) == (h > 0), f"K={K} h={h}: <m> = {smsigned / n:.3f} (a field h > 0 favours +1)"


def test_k03_observe_against_explicit_loops():
    plugin = _load("plugin")
    rng = np.random.default_rng(21)
    for L, nlev in ((9, 2), (27, 3), (15, 2), (9, 1)):
        s = rng.choice(np.array([-1, 1]), size=(L, L))
        bonds, msum, a, q = plugin.observe(s, nlev)
        want_b = sum(int(s[i, j]) * (int(s[i, (j + 1) % L]) + int(s[(i + 1) % L, j])) for i in range(L) for j in range(L))
        assert type(bonds) is int and bonds == want_b, (bonds, want_b)
        assert type(msum) is int and msum == int(s.sum())
        assert isinstance(a, list) and isinstance(q, list) and len(a) == nlev and len(q) == nlev
        for l in range(nlev):
            g = 3 ** (nlev - 1 - l)                   # finest first: the last level is the whole lattice
            b = L // g
            ms = [float(s[i * b:(i + 1) * b, j * b:(j + 1) * b].sum()) / (b * b) for i in range(g) for j in range(g)]
            wa, wq = sum(x ** 2 for x in ms) / len(ms), sum(x ** 4 for x in ms) / len(ms)
            assert type(a[l]) is float and type(q[l]) is float
            assert abs(a[l] - wa) <= 1e-12 and abs(q[l] - wq) <= 1e-12, (L, l, a[l], wa, q[l], wq)
        assert abs(a[nlev - 1] - (msum / (L * L)) ** 2) <= 1e-12, "the LAST level is the whole lattice"


def test_k04_constants():
    plugin = _load("plugin")
    assert plugin.UPDATE == "swendsen-wang", plugin.UPDATE
    assert plugin.ORDERED_SIDE == "+K" and plugin.DIALS == ("K",)
    kc = plugin.critical_K()
    assert type(kc) is float and kc == KC and abs(math.sinh(2 * kc) - 1.0) <= 1e-15, kc
    assert abs(kc - 0.44068679350977147) <= 1e-16


def test_k05_init_set_step():
    plugin = _load("plugin")
    L, K, h, burn, seed = 9, 0.25, 0.03, 4, 31
    st = plugin.init(L, K, h, burn, seed, 2, (0.2, 0.6))
    s, rng = ref_init(L, K, h, burn, seed)
    assert np.array_equal(np.asarray(st.s), s) and st.index == 0 and st.K == K and st.h == h and st.L == L and st.nlev == 2
    assert tuple(st.knobs_K) == (0.2, 0.6)
    for bad in (0.19, 0.61, -1.0):
        assert plugin.set(st, bad) is None and st.K == K, f"K={bad} is outside the knob range: a refusal value, no clamp"
    assert plugin.set(st, 0.6) is st and st.K == 0.6 and plugin.set(st, 0.2) is st and plugin.set(st, 0.41) is st
    assert st.index == 0, "set does not step"
    out = plugin.step(st, 3)
    for _ in range(3):
        s = ref_sweep(s, 0.41, h, rng)
    assert out is st and st.index == 3 and np.array_equal(np.asarray(st.s), s)
    plugin.step(st, 0)
    assert st.index == 3 and np.array_equal(np.asarray(st.s), s)
    # the blind face's measure is whole or nothing: one coupling outside the knobs and nothing moves (no measure at the old K)
    blind = _load("blind")
    bs = blind.plugin.init(L, K, h, burn, seed, 2, (0.2, 0.6))
    before = np.array(bs.s)
    for Ks in ([0.3, 0.61], [0.19], [0.3, -0.3], [0.7, 0.3]):
        assert blind.measure_moments(bs, Ks, 2, 40, 1) is None, f"Ks={Ks}: a coupling outside the knobs is a refusal value"
        assert bs.index == 0 and bs.K == K and np.array_equal(np.asarray(bs.s), before), f"Ks={Ks}: a refused measure moved the state"
    m = blind.measure_moments(bs, [0.2, 0.6], 2, 40, 1)
    assert set(m) == {"chi", "chi_err", "U4", "U4_err"} and bs.index == 2 * 42


GOOD = {"kind": "critical", "L": 9, "burn": 5, "seed": 7, "k": 1, "nlev": 2, "knobs_K": [0.2, 0.6], "K_start": 0.2,
        "index_unit": "sweep", "index_kind": "sample_counter"}
TAU = {"value": 1.0}
H_PER_UNIT = 100000                      # the declared tick: h = h_ticks / 100000


def FIELD(ticks, **over):
    return {"kind": "field", "h_ticks": ticks, **{k: v for k, v in GOOD.items() if k != "kind"}, **over}


def test_k06_truth_is_a_total_table_on_the_field():
    blind = _load("blind")
    w0 = blind.parse_world(dict(GOOD), dict(TAU))
    assert isinstance(w0, blind.World) and not isinstance(w0, blind.Refused), w0
    assert blind.truth(w0) == {"transition": "continuous", "K_c": KC, "held": {"h": 0.0}}, blind.truth(w0)
    assert dataclasses.is_dataclass(w0) and type(w0).__dataclass_params__.frozen, "World is a frozen dataclass"
    assert blind.Refused._fields == ("field", "detail") and issubclass(blind.Refused, tuple)
    assert w0.h_ticks == 0 and type(w0.h) is float and w0.h == 0.0 and math.copysign(1.0, w0.h) == 1.0
    assert blind.H_PER_UNIT == H_PER_UNIT
    for ticks in (1000, 200, 150, 1, 50000, 300000):  # the shipped decoys are weak fields, and still not a transition
        w = blind.parse_world(FIELD(ticks), dict(TAU))
        assert isinstance(w, blind.World), w
        assert w.h_ticks == ticks and type(w.h) is float and w.h == ticks / H_PER_UNIT, (w.h_ticks, w.h)
        assert blind.truth(w) == {"transition": "none", "K_c": None, "held": {"h": ticks / H_PER_UNIT}}, \
            f"h_ticks={ticks}: a field world has no transition: {blind.truth(w)}"
    far = blind.parse_world(dict(GOOD, knobs_K=[0.5, 0.6], K_start=0.5), dict(TAU))
    assert blind.truth(far) == {"transition": "continuous", "K_c": KC, "held": {"h": 0.0}}, \
        "the truth does not depend on the knob range"


def test_k07_the_world_parser_is_total(tmp_path):
    blind = _load("blind")
    w = blind.parse_world(dict(GOOD), dict(TAU, source="x", stamp="y"))
    assert isinstance(w, blind.World)
    assert (w.h_ticks, w.L, w.h, w.burn, w.seed, w.k, w.nlev, tuple(w.knobs_K), w.K_start, w.index_unit, w.index_kind, w.tau) == \
        (0, 9, 0.0, 5, 7, 1, 2, (0.2, 0.6), 0.2, "sweep", "sample_counter", 1.0)
    assert blind.WORLD_KEYS == {"critical": tuple(GOOD), "field": tuple(FIELD(1))}, blind.WORLD_KEYS
    cases = [({k: v for k, v in GOOD.items() if k != key}, TAU, key) for key in GOOD]          # no default, ever
    cases += [({k: v for k, v in FIELD(200).items() if k != key}, TAU, key) for key in FIELD(200)]
    cases += [(dict(GOOD, zz=1), TAU, "zz"), (dict(GOOD, w=0.1), TAU, "w"), (dict(GOOD, L4=0.14), TAU, "L4"),
              ({**GOOD, 1: 2}, TAU, "1"), ({**GOOD, None: 2, "zz": 1}, TAU, "None"),
              (dict(GOOD, K_c=0.44), TAU, "K_c"), (FIELD(200, zz=1), TAU, "zz")]
    # the kind decides the key set: a critical world has NO field key, so a zero or signed-zero field cannot be written
    cases += [(dict(GOOD, h_ticks=v), TAU, "h_ticks") for v in (0, 1, 200)]
    cases += [(dict(GOOD, h=v), TAU, "h") for v in (0.0, -0.0, 0.002)] + [(FIELD(200, h=0.002), TAU, "h")]
    cases += [(dict(GOOD, kind=v), TAU, "kind") for v in ("", "Critical", "none", "decoy", 0, 1, True, None, ["critical"],
                                                           {"critical": 1}, 0.0)]
    cases += [(FIELD(v), TAU, "h_ticks") for v in (0, -1, -200, 1.0, 0.002, -0.0, True, "200", None, [200],
                                                   float("nan"), float("inf"))]
    cases += [(dict(FIELD(0), kind="nope", zz=1), TAU, "kind")]                                  # the kind is read first
    for key, bads in {
        "L": (6, 18, 54, 8, 10, 1, -9, 9.0, True, "9", None, [9]),   # odd: a box of an odd number of spins has m != 0
        "burn": (-1, 1.0, True, "5", None),
        "seed": (-1, 7.0, True, "7", None),
        "k": (0, -1, 1.0, True, None),
        "nlev": (1, 0, 2.0, True, None),
        "knobs_K": ([0.6, 0.2], [0.2, 0.2], [0.2], [0.2, 0.4, 0.6], [0, 1], [0.2, True], "ab", None, 0.4, [-0.1, 0.6],
                    [0.2, float("inf")]),
        "K_start": (0.19, 0.61, 0, True, "0.2", None, float("nan")),
        "index_unit": ("", 1, None, True),
        "index_kind": ("", 1, None, True),
    }.items():
        cases += [(dict(GOOD, **{key: b}), TAU, key) for b in bads]
    cases += [(dict(GOOD, L=15, nlev=3), TAU, "L"), (dict(GOOD, L=27, nlev=5), TAU, "L")]      # L % 3**(nlev-1) != 0
    cases += [(GOOD, t, "value") for t in ({}, {"value": 0}, {"value": -1.0}, {"value": True}, {"value": "1"},
                                           {"value": float("nan")}, {"value": float("inf")})]
    for d, t, field in cases:
        r = blind.parse_world(dict(d), dict(t))
        assert isinstance(r, blind.Refused) and r.field == field, f"{d} / {t}: expected Refused({field!r}), got {r!r}"
        assert isinstance(r.detail, str)
    for d, t in ((None, TAU), ([], TAU), ("x", TAU), (GOOD, None), (GOOD, [])):
        assert isinstance(blind.parse_world(d, t), blind.Refused), (d, t)
    assert isinstance(blind.parse_world(dict(GOOD, L=27, nlev=4), dict(TAU)), blind.World)
    assert isinstance(blind.parse_world(dict(GOOD, L=45, nlev=3), dict(TAU, value=11)), blind.World), "an int tau is a tau"
    assert isinstance(blind.parse_world(FIELD(1, L=27, nlev=3), dict(TAU)), blind.World), "one tick is a field world"
    assert isinstance(blind.load_world(ROOT / "no-such-dir" / "w.toml"), blind.Refused), "a missing file is a value too"
    text = "".join(f"{k} = {json.dumps(v)}\n" for k, v in GOOD.items())
    for name, world, tau, field in (("ok", text.encode(), b"value = 1.0\n", None),
                                    ("bytes", b"\xff\xfe L = 9\n", b"value = 1.0\n", "w.toml"),
                                    ("syntax", b"L = = 9\n", b"value = 1.0\n", "w.toml"),
                                    ("taubytes", text.encode(), b"\xff\xfe", "tau-v0.toml"),
                                    ("notau", text.encode(), None, "tau-v0.toml")):
        d = tmp_path / name
        d.mkdir()
        (d / "w.toml").write_bytes(world)
        if tau is not None:
            (d / "tau-v0.toml").write_bytes(tau)
        r = blind.load_world(d / "w.toml")
        if field is None:
            assert isinstance(r, blind.World) and r == w, r
        else:
            assert isinstance(r, blind.Refused) and r.field == field, f"{name}: expected Refused({field!r}), got {r!r}"


def _imports(path):
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, (path.name, "relative import")
            out.add((node.module or "").split(".")[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("__import__", "exec", "eval", "open") or path.name == "blind.py", (path.name, node.func.id)
    return out


def test_k08_purity_the_core_knows_no_wire():
    assert _imports(ISING / "plugin.py") <= {"math", "dataclasses", "numpy", "scipy"}, _imports(ISING / "plugin.py")
    assert _imports(ISING / "blind.py") <= {"importlib", "math", "tomllib", "dataclasses", "pathlib", "typing", "numpy"}, \
        _imports(ISING / "blind.py")
    plugin, blind = _load("plugin"), _load("blind")
    for name in ("measure_moments", "declared", "truth", "load_world", "parse_world", "init_blind", "ROLES", "OBSERVABLE"):
        assert not hasattr(plugin, name), f"plugin.py holds `{name}`: a wire face belongs in a sibling module"
        assert hasattr(blind, name), f"blind.py lacks `{name}`"
    assert Path(blind.plugin.__file__).resolve() == (ISING / "plugin.py").resolve(), "blind.py path-loads its sibling plugin.py"
    text = (ISING / "plugin.py").read_text()
    for word in ("tomllib", "socket", "json", "edge.json", "navigator", "environment"):
        assert word not in text, f"plugin.py mentions `{word}`"


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                (_t(Path(_d)) if _t.__code__.co_argcount else _t()); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
