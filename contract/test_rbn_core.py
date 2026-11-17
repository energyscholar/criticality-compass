"""Plan 1560 — the random Boolean network System plugin: the PHYSICS CORE and the world table (contract/SCHEMA-1560.md §2-§8).
FROZEN: the Generator makes this green; it does not edit this file. No server is started here.

What it pins:
  k01  `plugin.draw_net`, `plugin.outputs` and `plugin.probe` ARE the declared network and probe (SCHEMA §2-§3), bit for
       bit, with and without replica noise, and draw exactly as many random values;
  k02  the probe measures the declared damage: its mean is the exact lambda_net of the drawn network (and the exact
       noisy formula); averaged over networks, lambda is 2p(1-p)K, so K means mean in-degree and p means bias;
  k03  the network's structure: distinct inputs, k_i = floor(K + v_i) (monotone in K, mean K), KMAX = ceil(hi);
  k04  the System's constants: the update label, the ordered side, BOTH dials, the annealed line's K section;
  k05  init / set / step / sample: the index counts probes; a set outside the domain is `None`, no clamp, nothing drawn;
       a measure outside the knobs is `None`, whole;
  k06  the truth is a total table on the world kind: a LINE (never a bare K_c) for a critical world, NO transition for a
       noise world, however weak the noise;
  k07  the world parser is total: every fault is a `Refused` value naming its field, nothing raises, no default is filled;
       p = 0, p = 1 and a zero noise cannot be written;
  k08  purity: the core knows no wire and imports nothing of the navigator or the environment.

RED until `system-instantiated/plugins/rbn/` exists.
Run from the repo root:  python contract/test_rbn_core.py   (or pytest)
"""
import ast
import dataclasses
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RBN = ROOT / "system-instantiated" / "plugins" / "rbn"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"t1560_{name}", RBN / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- the declared network and probe (SCHEMA-1560 §2-§3), written out a second time with loops: the test's own oracle -------
def ref_net(N, KMAX, rng):
    v = rng.random(N)
    inputs = [[int(a) for a in rng.choice(N, KMAX, replace=False)] for _ in range(N)]
    w = rng.random((N, 2 ** KMAX))
    return v, inputs, w


def ref_outputs(net, x, K, p):
    v, inputs, w = net
    out = []
    for i in range(len(v)):
        k = int(math.floor(K + float(v[i])))
        r = sum(int(bool(x[inputs[i][m]])) << m for m in range(k))
        out.append(bool(w[i, r] < p))
    return out


def ref_probe(net, K, p, eta, rng):
    N = len(net[0])
    x = rng.random(N) < 0.5
    j = int(rng.integers(N))
    ua, ba = rng.random(N), rng.random(N) < 0.5
    ub, bb = rng.random(N), rng.random(N) < 0.5
    y = [bool(b) for b in x]
    y[j] = not y[j]
    fx, fy = ref_outputs(net, x, K, p), ref_outputs(net, y, K, p)
    fx = [bool(ba[i]) if ua[i] < eta else fx[i] for i in range(N)]
    fy = [bool(bb[i]) if ub[i] < eta else fy[i] for i in range(N)]
    return sum(a != b for a, b in zip(fx, fy))


def exact_lambda(net, K, p):
    """lambda_net = (1/N) sum_i sum_{m<k_i} 2^-k_i sum_r [T_i(r) != T_i(r ^ 2^m)]"""
    v, inputs, w = net
    N, tot = len(v), 0.0
    for i in range(N):
        k = int(math.floor(K + float(v[i])))
        rows = np.arange(2 ** k)
        T = w[i, :2 ** k] < p
        for m in range(k):
            tot += float((T[rows] != T[rows ^ (1 << m)]).mean())
    return tot / N


def _same_net(a, net):
    v, inputs, w = net
    return (np.array_equal(np.asarray(a.v), v) and np.array_equal(np.asarray(a.inputs), np.array(inputs))
            and np.array_equal(np.asarray(a.w), w))


def test_k01_the_declared_network_and_probe():
    plugin = _load("plugin")
    for N, KMAX, K, p, eta, seed in ((9, 2, 1.0, 0.5, 0.0, 1), (27, 4, 2.0, 0.5, 0.0, 2), (30, 4, 3.7, 0.3, 0.0, 3),
                                     (27, 3, 1.4, 0.8, 0.05, 4), (12, 8, 7.5, 0.5, 0.0, 5), (18, 4, 0.0, 0.5, 0.0, 6),
                                     (21, 4, 4.0, 0.62, 1.0, 7), (27, 4, 2.6, 0.5, 0.3, 8)):
        ra, rb = np.random.default_rng(seed), np.random.default_rng(seed)
        a = plugin.draw_net(N, KMAX, ra)
        net = ref_net(N, KMAX, rb)
        assert _same_net(a, net), f"the network differs from the declared draw: N={N} KMAX={KMAX} seed={seed}"
        assert dataclasses.is_dataclass(a) and type(a).__dataclass_params__.frozen, "Net is a frozen dataclass (quenched)"
        x = ra.random(N) < 0.5
        rb.random(N)
        o = plugin.outputs(a, x, K, p)
        assert np.asarray(o).dtype == bool and list(np.asarray(o)) == ref_outputs(net, x, K, p), (N, K, p)
        for n in range(6):
            h, want = plugin.probe(a, K, p, eta, ra), ref_probe(net, K, p, eta, rb)
            assert type(h) is int and h == want, f"probe {n} differs: N={N} K={K} p={p} eta={eta}: {h} != {want}"
        assert ra.random() == rb.random(), f"the probe drew a different number of random values: N={N} K={K} eta={eta}"


def test_k02_the_probe_measures_the_declared_damage():
    plugin = _load("plugin")
    for N, K, p, eta, seed in ((243, 1.0, 0.5, 0.0, 11), (243, 2.0, 0.5, 0.0, 12), (243, 3.3, 0.3, 0.0, 13),
                               (243, 2.0, 0.5, 0.002, 14), (243, 1.5, 0.8, 0.01, 15)):
        rng = np.random.default_rng(seed)
        a = plugin.draw_net(N, 4, rng)
        net = (np.asarray(a.v), np.asarray(a.inputs).tolist(), np.asarray(a.w))
        H = np.array([plugin.probe(a, K, p, eta, rng) for _ in range(20000)])
        want = (1 - eta) ** 2 * exact_lambda(net, K, p) + N * (eta - eta ** 2 / 2)
        se = H.std() / math.sqrt(len(H))
        assert abs(H.mean() - want) <= 4.5 * se, f"N={N} K={K} p={p} eta={eta}: <h1> = {H.mean():.4f} +- {se:.4f}, exact {want:.4f}"
    # the annealed line: over networks, lambda = 2p(1-p)K (K is the mean in-degree, p the bias; inputs are distinct)
    for K, p in ((1.5, 0.5), (2.5, 0.3), (3.2, 0.9)):
        lam = []
        for seed in range(40):
            a = plugin.draw_net(243, 4, np.random.default_rng(100 + seed))
            lam.append(exact_lambda((np.asarray(a.v), np.asarray(a.inputs).tolist(), np.asarray(a.w)), K, p))
        se = np.std(lam) / math.sqrt(len(lam))
        assert abs(np.mean(lam) - 2 * p * (1 - p) * K) <= 4.5 * se + 1e-3, (K, p, np.mean(lam), se)


def test_k03_the_network_structure():
    plugin = _load("plugin")
    a = plugin.draw_net(729, 4, np.random.default_rng(21))
    inp = np.asarray(a.inputs)
    assert inp.shape == (729, 4) and np.issubdtype(inp.dtype, np.integer) and inp.min() >= 0 and inp.max() < 729
    assert all(len(set(r)) == 4 for r in inp.tolist()), "a node's inputs are distinct"
    assert np.asarray(a.w).shape == (729, 16) and np.asarray(a.v).shape == (729,)
    prev = None
    for K in (0.0, 0.5, 1.0, 1.3, 2.0, 2.71, 3.0, 4.0):
        k = np.asarray(plugin.degrees(a, K))
        assert np.array_equal(k, np.floor(K + np.asarray(a.v)).astype(int)), K
        assert abs(k.mean() - K) <= 0.06, f"the mean in-degree at K={K} is {k.mean()}"
        if prev is not None:
            assert (k >= prev).all(), "the in-degree is monotone in K for every node"
        prev = k
    for knobs, want in (((1.0, 4.0), 4), ((0.5, 3.2), 4), ((1.0, 3.0), 3), ((0.0, 0.5), 1), ((2.0, 8.0), 8)):
        assert plugin.kmax(knobs) == want, (knobs, plugin.kmax(knobs))


def test_k04_constants():
    plugin = _load("plugin")
    assert plugin.UPDATE == "uniform-probe", plugin.UPDATE
    assert plugin.ORDERED_SIDE == "-K" and plugin.DIALS == ("K", "p")
    assert plugin.critical_K(0.5) == 2.0 and type(plugin.critical_K(0.5)) is float
    for p in (0.1, 0.3, 0.5, 0.62, 0.999):
        kc = plugin.critical_K(p)
        assert abs(2 * p * (1 - p) * kc - 1.0) <= 1e-12, (p, kc)
        assert abs(kc - plugin.critical_K(1 - p)) <= 1e-9 * kc, "the line is symmetric in p <-> 1 - p"


def test_k05_init_set_step_sample():
    plugin = _load("plugin")
    N, K, p, eta, seed = 27, 1.5, 0.5, 0.01, 31
    st = plugin.init(N, K, p, eta, seed, (1.0, 4.0))
    rng = np.random.default_rng(seed)
    net = ref_net(N, 4, rng)
    assert _same_net(st.net, net) and st.index == 0 and st.K == K and st.p == p and st.eta == eta and st.N == N
    assert tuple(st.knobs_K) == (1.0, 4.0)
    for bK, bp in ((0.99, 0.5), (4.01, 0.5), (-1.0, 0.5), (2.0, 0.0), (2.0, 1.0), (2.0, -0.1), (2.0, 1.2),
                   (2.0, float("nan")), (float("nan"), 0.5)):
        assert plugin.set(st, bK, bp) is None and st.K == K and st.p == p, f"set({bK}, {bp}) is a refusal value, no clamp"
    assert plugin.set(st, 4.0, 0.5) is st and plugin.set(st, 1.0, 0.3) is st and st.p == 0.3
    assert plugin.set(st, 2.2, 0.5) is st and st.K == 2.2 and st.index == 0, "set does not step"
    out = plugin.step(st, 3)
    for _ in range(3):
        ref_probe(net, 2.2, 0.5, eta, rng)
    assert out is st and st.index == 3
    h = plugin.sample(st)
    assert type(h) is int and h == ref_probe(net, 2.2, 0.5, eta, rng) and st.index == 4
    plugin.step(st, 0)
    assert st.index == 4 and st.rng.random() == rng.random(), "step(0) draws nothing"
    # p is a DIAL: moved through set, it is the p the probes run at (never the p held since init)
    assert plugin.set(st, 2.2, 0.3) is st and st.p == 0.3
    at_init = np.random.default_rng(); at_init.bit_generator.state = rng.bit_generator.state
    want = [ref_probe(net, 2.2, 0.3, eta, rng) for _ in range(40)]
    stale = [ref_probe(net, 2.2, 0.5, eta, at_init) for _ in range(40)]
    assert want != stale, "self-check: the two biases give different probe streams on this network"
    got = [plugin.sample(st) for _ in range(40)]
    assert got == want, "set moved p but the probes still run at the init p: p is recorded, not a dial"
    # the blind face's measure is whole or nothing: one K outside the knobs and nothing moves
    blind = _load("blind")
    bs = blind.plugin.init(N, 1.0, 0.5, 0.0, seed, (1.0, 4.0))
    probe_state = bs.rng.bit_generator.state
    for Ks in ([2.0, 4.1], [0.9], [2.0, -2.0], [5.0, 2.0]):
        assert blind.measure_moments(bs, Ks, 2, 40, 1) is None, f"Ks={Ks}: a K outside the knobs is a refusal value"
        assert bs.index == 0 and bs.K == 1.0 and bs.rng.bit_generator.state == probe_state, f"Ks={Ks}: a refused measure moved the state"
    m = blind.measure_moments(bs, [1.0, 4.0], 2, 40, 3)
    assert set(m) == {"heal", "heal_err"} and bs.index == 2 * (2 + 40 * 3)


GOOD = {"kind": "critical", "N": 27, "p_ticks": 500, "seed": 7, "k": 6, "knobs_K": [1.0, 4.0], "K_start": 1.0,
        "index_unit": "probe", "index_kind": "sample_counter"}
TAU = {"value": 1}


def NOISE(ticks, **over):
    return {"kind": "noise", "eta_ticks": ticks, **{k: v for k, v in GOOD.items() if k != "kind"}, **over}


LINE = {"form": "2p(1-p)K=1", "approx": "annealed"}


def test_k06_truth_is_a_total_table_on_the_kind():
    blind = _load("blind")
    w0 = blind.parse_world(dict(GOOD), dict(TAU))
    assert isinstance(w0, blind.World) and not isinstance(w0, blind.Refused), w0
    assert blind.truth(w0) == {"transition": "line", "critical_set": LINE, "held": {"p": 0.5},
                               "section": {"dial": "K", "K_c": 2.0}}, blind.truth(w0)
    assert dataclasses.is_dataclass(w0) and type(w0).__dataclass_params__.frozen, "World is a frozen dataclass"
    assert blind.Refused._fields == ("field", "detail") and issubclass(blind.Refused, tuple)
    assert w0.eta_ticks == 0 and type(w0.eta) is float and w0.eta == 0.0 and type(w0.p) is float and w0.p == 0.5
    assert blind.P_PER_UNIT == 1000 and blind.ETA_PER_UNIT == 1000000
    for pt in (300, 1, 999, 620):
        w = blind.parse_world(dict(GOOD, p_ticks=pt), dict(TAU))
        p = pt / 1000
        t = blind.truth(w)
        assert t == {"transition": "line", "critical_set": LINE, "held": {"p": p},
                     "section": {"dial": "K", "K_c": 1.0 / (2.0 * p * (1.0 - p))}}, (pt, t)
        assert t["section"]["K_c"] != 2.0, "the K section moves with p: a line, never one scalar K_c"
        d = blind.declared(w)
        assert d["ordered_side"] == "-K" and d["roles"][0]["ordered_sign"] == "+" and d["fixed"] == {"p": p}, \
            f"p_ticks={pt}: in K the frozen side is low K on BOTH halves of p; the side is physics, not a world value: {d}"
    for ticks in (1000, 250, 220, 1, 500000, 1000000):   # the shipped decoys are weak noise, and still not a transition
        w = blind.parse_world(NOISE(ticks), dict(TAU))
        assert isinstance(w, blind.World), w
        assert w.eta_ticks == ticks and w.eta == ticks / 1000000
        assert blind.truth(w) == {"transition": "none", "critical_set": None, "held": {"p": 0.5, "eta": ticks / 1000000},
                                  "section": None}, f"eta_ticks={ticks}: a noise world has no transition: {blind.truth(w)}"
    far = blind.parse_world(dict(GOOD, knobs_K=[3.0, 4.0], K_start=3.0), dict(TAU))
    assert blind.truth(far) == blind.truth(w0), "the truth does not depend on the knob range"


def test_k07_the_world_parser_is_total(tmp_path):
    blind = _load("blind")
    w = blind.parse_world(dict(GOOD), dict(TAU, source="x", stamp="y"))
    assert isinstance(w, blind.World)
    assert (w.eta_ticks, w.N, w.p_ticks, w.seed, w.k, tuple(w.knobs_K), w.K_start, w.index_unit, w.index_kind, w.tau) == \
        (0, 27, 500, 7, 6, (1.0, 4.0), 1.0, "probe", "sample_counter", 1)
    assert blind.WORLD_KEYS == {"critical": tuple(GOOD), "noise": tuple(NOISE(1))}, blind.WORLD_KEYS
    cases = [({k: v for k, v in GOOD.items() if k != key}, TAU, key) for key in GOOD]          # no default, ever
    cases += [({k: v for k, v in NOISE(220).items() if k != key}, TAU, key) for key in NOISE(220)]
    cases += [(dict(GOOD, zz=1), TAU, "zz"), (dict(GOOD, nlev=2), TAU, "nlev"), (dict(GOOD, L=27), TAU, "L"),
              (dict(GOOD, p=0.5), TAU, "p"), (dict(GOOD, burn=5), TAU, "burn"), ({**GOOD, 1: 2}, TAU, "1"),
              ({**GOOD, None: 2, "zz": 1}, TAU, "None"), (dict(GOOD, K_c=2.0), TAU, "K_c"), (NOISE(220, zz=1), TAU, "zz")]
    # the kind decides the key set: a critical world has NO noise key, so a zero noise cannot be written
    cases += [(dict(GOOD, eta_ticks=v), TAU, "eta_ticks") for v in (0, 1, 220)]
    cases += [(dict(GOOD, eta=v), TAU, "eta") for v in (0.0, -0.0, 0.002)] + [(NOISE(220, eta=0.002), TAU, "eta")]
    cases += [(dict(GOOD, kind=v), TAU, "kind") for v in ("", "Critical", "none", "decoy", "field", 0, 1, True, None,
                                                           ["critical"], {"critical": 1}, 0.0)]
    cases += [(NOISE(v), TAU, "eta_ticks") for v in (0, -1, -220, 1000001, 1.0, 0.002, -0.0, True, "220", None, [220],
                                                     float("nan"), float("inf"))]
    cases += [(dict(NOISE(0), kind="nope", zz=1), TAU, "kind")]                                  # the kind is read first
    for key, bads in {
        "N": (8, 6, 3, 0, -9, 28, 2188, 27.0, True, "27", None, [27]),
        "p_ticks": (0, 1000, -1, 1001, 500.0, 0.5, True, "500", None),   # p = 0 and p = 1 cannot be written
        "seed": (-1, 7.0, True, "7", None),
        "k": (0, -1, 1.0, True, None),
        "knobs_K": ([4.0, 1.0], [1.0, 1.0], [1.0], [1.0, 2.0, 4.0], [1, 4], [1.0, True], "ab", None, 2.0, [-0.1, 4.0],
                    [1.0, 8.01], [1.0, float("inf")]),
        "K_start": (0.99, 4.01, 1, True, "1.0", None, float("nan")),
        "index_unit": ("", 1, None, True),
        "index_kind": ("", 1, None, True),
    }.items():
        cases += [(dict(GOOD, **{key: b}), TAU, key) for b in bads]
    cases += [(GOOD, t, "value") for t in ({}, {"value": 0}, {"value": -1.0}, {"value": True}, {"value": "1"},
                                           {"value": float("nan")}, {"value": float("inf")})]
    for d, t, field in cases:
        r = blind.parse_world(dict(d), dict(t))
        assert isinstance(r, blind.Refused) and r.field == field, f"{d} / {t}: expected Refused({field!r}), got {r!r}"
        assert isinstance(r.detail, str)
    for d, t in ((None, TAU), ([], TAU), ("x", TAU), (GOOD, None), (GOOD, [])):
        assert isinstance(blind.parse_world(d, t), blind.Refused), (d, t)
    assert isinstance(blind.parse_world(dict(GOOD, N=9, knobs_K=[0.0, 8.0], K_start=8.0), dict(TAU)), blind.World)
    assert isinstance(blind.parse_world(dict(GOOD, p_ticks=1), dict(TAU, value=1.0)), blind.World), "a float tau is a tau"
    assert isinstance(blind.parse_world(NOISE(1, p_ticks=999), dict(TAU)), blind.World), "one tick is a noise world"
    assert isinstance(blind.parse_world(NOISE(1000000), dict(TAU)), blind.World), "eta = 1 is the top of the noise range"
    assert isinstance(blind.load_world(ROOT / "no-such-dir" / "w.toml"), blind.Refused), "a missing file is a value too"
    text = "".join(f"{k} = {json.dumps(v)}\n" for k, v in GOOD.items())
    for name, world, tau, field in (("ok", text.encode(), b"value = 1\n", None),
                                    ("bytes", b"\xff\xfe N = 9\n", b"value = 1\n", "w.toml"),
                                    ("syntax", b"N = = 9\n", b"value = 1\n", "w.toml"),
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
    assert _imports(RBN / "plugin.py") <= {"math", "dataclasses", "numpy"}, _imports(RBN / "plugin.py")
    assert _imports(RBN / "blind.py") <= {"importlib", "math", "tomllib", "dataclasses", "pathlib", "typing", "numpy"}, \
        _imports(RBN / "blind.py")
    plugin, blind = _load("plugin"), _load("blind")
    for name in ("measure_moments", "declared", "truth", "load_world", "parse_world", "init_blind", "ROLES", "OBSERVABLE"):
        assert not hasattr(plugin, name), f"plugin.py holds `{name}`: a wire face belongs in a sibling module"
        assert hasattr(blind, name), f"blind.py lacks `{name}`"
    assert Path(blind.plugin.__file__).resolve() == (RBN / "plugin.py").resolve(), "blind.py path-loads its sibling plugin.py"
    text = (RBN / "plugin.py").read_text()
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
