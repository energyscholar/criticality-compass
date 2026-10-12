"""door.py - between the data and the maths: context, relations, the resample plan, the doors (plumbing)."""
import functools
import hashlib
import itertools
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import admit
import gamma
import schema
import formats
import project
import reduce
import resample
from kernel import Provenance


@dataclass(frozen=True)
class Null:
    """A door's refusal as a VALUE: the unit's columns all read `value`, for `reason`."""
    value: str
    reason: str


@dataclass(frozen=True)
class Ctx:
    """Everything the maths may read: declared numbers and relations, built before any data is touched."""
    level: float
    eps: dict
    rel: dict
    log_ratio: object = None
    log_span: float = None
    top: int = None
    top_steps: int = None
    coarsest: int = None
    big_final: int = None
    sink_ordered: float = None
    sink_disordered: float = None
    unit_scale: float = None
    unit_scales: tuple = None        # a point unit over sizes: the declared unit scale at every size (axes.size order)
    unit_rel: object = None          # a pair unit: the 2-node restriction of the control relation (edge 1 -> 0)
    component_shape: tuple = None    # a pair unit: (R+1, n_size), the layout of Delta per resample row and size
    pair_shape: tuple = None         # a pair unit: (n_size, 2), one reduce output
    n_size: int = None               # the number of declared sizes
    member: dict = None              # a pair unit: {"door": value, "reason": text} from the membership rule
    quantity: str = "R"              # the name a sign refusal gives the logged quantity
    ratio: object = None             # a pair unit with door:basis: the correction ratio r per resample row (0 on a RAW pair; plan 0874)
    interval: dict = None            # the input's declared [interval] (plan 0878: the Gamma-method reads window_s, window_max, door_z from it)
    lin: object = None               # method gamma: the unit's Lin (its primaries' series, displacements and window), None under a resampling method
    rank: int = None                 # method chains (plan 0937): r of the order statistics [v_(r), v_(m+1-r)] of the m chain rows; None under every other method


def relations_for(m, name):
    """The declared relation `name`, built through admit.declare (acyclic, one provenance per edge)."""
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        n, edges = len(ax[r["axis"]]), [(i + 1, i) for i in range(len(ax[r["axis"]]) - 1)]
    elif r["template"] == "pair":
        n, edges = 2 * len(r["pairs"]), [(2 * k + 1, 2 * k) for k in range(len(r["pairs"]))]
    elif r["template"] == "all-pairs":
        n, edges = len(ax[r["axis"]]), [(j, i) for j in range(1, len(ax[r["axis"]])) for i in range(j)]
    else:   # matched: one pair (big, small); matched-chain: pairs laid end to end, each with its own nodes
        lv, prs = m["observable"]["levels"], r["pairs"] if r["template"] == "matched-chain" else [[r["big"], r["small"]]]
        nbs = [lv[ax["size"].index(b)] for b, _ in prs]
        offs = [0, *itertools.accumulate(2 * nb - 1 for nb in nbs)]
        n, edges = offs[-1], [(o + k, o + nb + k - 1) for o, nb in zip(offs, nbs) for k in range(1, nb)]
    return admit.declare(n, edges, [Provenance(r["provenance"])] * len(edges))


def control_pairs(m, name="control"):
    """The (a, b) point labels of every edge of the declared control relation, in its edge order (A = x[b] - x[a])."""
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        return list(zip(ax[r["axis"]], ax[r["axis"]][1:]))
    if r["template"] == "all-pairs":
        return [(ax[r["axis"]][i], ax[r["axis"]][j]) for j in range(1, len(ax[r["axis"]])) for i in range(j)]
    return [tuple(p) for p in r["pairs"]]


def unit_labels(m, inst):
    """The (unit, size) labels an instrument is read at: points, (point, size) or control pairs."""
    pts, sizes = m["axes"]["point"], m["axes"]["size"]
    if inst["unit"] == "pair":
        return [(p, None) for p in control_pairs(m)]
    return [(p, s) for p in pts for s in (sizes if inst["unit"] == "point-size" else [None])]


COVERAGE = {"block": lambda iv: iv["level"], "iid": lambda iv: iv["level"], "gamma": lambda iv: iv["level"], "chains": lambda iv: 1 - iv["alpha"]}
"""Interval method -> the coverage a declared [interval] states (plan 0937): the level, or for `chains` 1 - alpha (the exact order-statistic coverage). TOTAL over
cc.toml alphabets.interval_method (tests/test_chains.py asserts the keys equal the alphabet), so a method cannot be added without saying what it covers."""
ROW_COUNT = {"block": lambda iv: iv["resamples"] + 1, "iid": lambda iv: iv["resamples"] + 1, "gamma": lambda iv: 0, "chains": lambda iv: iv["m"] + 1}
"""Interval method -> the rows of one unit's reduce output (row 0 + the rest); gamma's is replaced once its primaries are known (measure)."""


def context(m, inst, size=None):
    sizes, rel = m["axes"]["size"], {n: relations_for(m, n) for n in inst["relations"]}
    k = len(sizes) - 1
    if "size" in rel:
        prov = Provenance(m["relations"]["size"]["provenance"])
        rel["steps"] = admit.declare(k, [(i + 1, i) for i in range(k - 1)], [prov] * (k - 1))
    rm = m.get("relations", {})
    big = rm["matched"]["big"] if "matched" in rel else rm["chain"]["pairs"][0][0] if "chain" in rel else None   # the top pair's big size
    nb = m["observable"]["levels"][sizes.index(big)] if big is not None else 0
    pair = inst["unit"] == "pair"
    unit_rel = admit.declare(2, [(1, 0)], [Provenance(m["relations"]["control"]["provenance"])]) if pair else None
    return Ctx(
        unit_rel=unit_rel, component_shape=(ROW_COUNT[m["interval"]["method"]](m["interval"]), len(sizes)) if pair else None,   # method gamma: the row count is known once the unit's primaries are (measure replaces it)
        interval=m["interval"],
        pair_shape=(len(sizes), 2) if pair else None, n_size=len(sizes), quantity=inst.get("quantity", "Delta" if pair else "R"),
        level=COVERAGE[m["interval"]["method"]](m["interval"]), rank=m["interval"].get("r"), eps={c: m["eps"][e] for c, e in inst["columns"].items()}, rel=rel,
        log_ratio=np.log(np.array(sizes[1:], float) / np.array(sizes[:-1], float)),
        log_span=float(np.log(sizes[-1] / sizes[0])), top=k - 1, top_steps=k - 2,
        coarsest=nb - 2, big_final=nb - 1,
        sink_ordered=m.get("sinks", {}).get("ordered"), sink_disordered=m.get("sinks", {}).get("disordered"),
        unit_scale=m.get("two_start", {}).get("unit_scale", {}).get(str(size)),
        unit_scales=tuple(m.get("two_start", {}).get("unit_scale", {}).get(str(s)) for s in sizes))


def unit_keys(m, inst, point, size=None):
    """The data blocks one unit of the instrument reads, in the order its reduce expects them."""
    sizes, starts = schema.unit_blocks(m, inst)
    pts = point if isinstance(point, tuple) else (point,)   # a pair unit reads both of its points, a then b
    return [(pt, s, st) for s in ([size] if inst["unit"] == "point-size" else sizes) for pt in pts for st in starts]


def reduced(m, path, key):
    """GL [N, levels]: a raw stack reduced through the input's declared [block_map] and [observable] (cc/reduce.py), cached under
    results/reduced/<input>/<sha>.npz; the name is the sha of (the raw file's sha, the code hash, the key, the map, the level count)."""
    root, bm, ob, fmt = schema.ROOT, m["block_map"], m["observable"], m["data"]["format"]
    n = formats.levels_for(formats.shape_of(fmt, path, key, str(root), m.get("windows"))[1], ob["final_size"], bm["factor"])
    if n is None:
        raise ValueError(f"{path}: L is not final_size * factor^k (bin/cc validate says so, with a Next line)")
    name = hashlib.sha256("\0".join([schema.sha(path), schema.code_hash(root), key, bm["name"], str(n), *[f"{k}={v}" for k, v in m.get("windows", {}).items()]]).encode()).hexdigest()   # plan 0884: a windowed input caches under its window too
    f = root / "results" / "reduced" / m["id"] / f"{name}.npz"
    if not f.is_file():
        gl = np.array([reduce.snapshot(x, bm["name"], n) for x in formats.read(fmt, path, key, str(root), m.get("windows"))])
        f.parent.mkdir(parents=True, exist_ok=True)
        np.savez(f.with_suffix(".part.npz"), GL=gl)
        os.replace(f.with_suffix(".part.npz"), f)
    return np.load(f)["GL"]


def memo(cache, key, make):
    if key not in cache:
        cache[key] = make()
    return cache[key]


def load_blocks(m, data_root, locate=None):
    """[(block key, {array name: ndarray})] in data.files order (the key is (point, size, start), and (point, size, start, chain) under method chains), each array cut to its declared level. In a stack format (cc.toml
    [formats.*]) the arrays of a kind it `reduces` are computed from the raw stack by the declared reduction (once per file and key)."""
    cache, out, sch = {}, [], formats.schemas(str(schema.ROOT)).get(m["data"]["format"], {"reduces": ()})
    for b in m["data"]["files"]:
        path, arrs = str((locate or (lambda x: Path(data_root) / x))(b["path"])), {}
        for name, a in b["arrays"].items():
            z = memo(cache, (path, a["key"], "GL"), lambda: reduced(m, path, a["key"])) if name in sch["reduces"] else memo(cache, path, lambda: np.load(path))
            v = z if isinstance(z, np.ndarray) else z[a["key"]]
            arrs[name] = np.ascontiguousarray(v[:, a["level"]] if "level" in a else v)
        out.append(((b["point"], b["size"], b["start"], *([b["chain"]] if "chain" in b else [])), arrs))   # plan 0937: a block of method chains is keyed by its chain as well
    return out


def resample_plan(m, ns):
    """Row 0 is the identity; rows 1..R draw one index set per block (data.files order) from ONE generator."""
    iv = m["interval"]
    yield [np.arange(n) for n in ns]
    rng = np.random.default_rng(iv["seed"])
    for _ in range(iv["resamples"]):
        if iv["method"] == "block":
            yield [resample.block_indices(n, iv["b"], rng) for n in ns]
        else:
            yield [resample.iid_indices(n, rng) for n in ns]


@dataclass(frozen=True)
class GammaStat:
    """The Gamma-method's statistics of ONE reading: its SE, the window W and tau_int. A statistic of the interval projection C (plan 0878; Robin Q0):
    it places the reading's sign cell and is never an operator input. It is a TYPE of its own, so no door can build a NodeField from it."""
    se: float
    window: int
    tau_int: float


@dataclass(frozen=True)
class Lin:
    """The linearisation of ONE unit (plan 0878): per file (block) the primaries' series [n_i, p_i], their means, the displacement h of every primary (its naive SE),
    and each file's offset into the P primaries. Row j >= 1 of linearise_plan displaces primary j by h[j - 1]; the stages then run on 1 + P rows."""
    ser: tuple
    mean: tuple
    h: object
    off: tuple


def linearise(ser, step):
    """The Lin of a unit from its per-file primary series. h = step * SE_naive, SE_naive = sd/sqrt(n) of each primary (step: cc.toml [interval_fields.gamma] diff_step,
    small enough that a nonlinear stage such as ln stays in its linear range); a primary with no variance has no fluctuation to propagate, so its displacement is
    any positive step (sqrt(eps) of its scale), never zero."""
    mean = tuple(s.mean(axis=0) for s in ser)
    h = step * np.concatenate([s.std(axis=0) / np.sqrt(len(s)) for s in ser])
    scale = np.concatenate([1 + np.abs(m) for m in mean])
    off = tuple(itertools.accumulate((s.shape[1] for s in ser), initial=0))[:-1]
    return Lin(tuple(ser), mean, np.where(h > 0, h, np.sqrt(np.finfo(float).eps) * scale), off)


def linearise_plan(lin):
    """The row plan of method gamma, beside resample_plan: row 0 is the estimate (the primaries' means); each next row displaces ONE primary's mean by its h.
    Yields the per-file means; the instrument's from_means turns each into one reduce output."""
    yield [m.copy() for m in lin.mean]
    for i, m in enumerate(lin.mean):
        for q in range(len(m)):
            ms = [x.copy() for x in lin.mean]
            ms[i][q] += lin.h[lin.off[i] + q]
            yield ms


def gamma_stat(lin, v, iv):
    """GammaStat of one reading from its value over the linearisation rows (v[0] the estimate, v[1:] the displaced rows), or None when no window is found by window_max.
    The gradient is the row difference over h; Gamma_F(t) = sum over files of c^T Gamma(t) c (files are independent; each weighted n/n_i, n the shortest file), then Wolff's window."""
    g, n = (np.asarray(v, float)[1:] - v[0]) / lin.h, min(len(s) for s in lin.ser)
    gam = sum(n / len(s) * gamma.autocov((s @ g[o:o + s.shape[1]])[:, None], iv["window_max"])[:, 0, 0] for s, o in zip(lin.ser, lin.off))
    w = gamma.window(gam, n, iv["window_s"])
    return None if w is None else GammaStat(float(np.sqrt(gamma.variance(gam, w[0], n))), int(w[0]), float(w[1]))


@functools.lru_cache(maxsize=None)
def diff_step():
    """The finite-difference step of method gamma's linearisation rows, from cc.toml [interval_fields.gamma] (a fraction of each primary's naive SE)."""
    return tomllib.loads((schema.ROOT / "cc.toml").read_text())["interval_fields"]["gamma"]["diff_step"]


@functools.lru_cache(maxsize=None)
def z_of(level):
    """The z of a declared level, from cc.toml [levels] (validate refuses a level the table does not hold)."""
    return tomllib.loads((schema.ROOT / "cc.toml").read_text())["levels"][str(level)]


def nodefield(x, ctx):
    """The reduce outputs as a NodeField: every leading axis flattened into components (C order). A Gamma statistic is refused: the interval is not an operator input."""
    if isinstance(x, GammaStat):
        raise ValueError("a Gamma-method statistic (SE, window W, tau_int) is a projection C output: it feeds the sign cell only and is never an operator input\n"
                         "  Next: read it through readout.reading_se; do not route it into a stage or a door")
    x = x.reshape(-1, x.shape[-1])
    return admit.nodefield(x) if np.isfinite(x).all() else Null("NOT-EVALUATED", "non-finite value")


def logcoord(x, ctx):
    """ln(s v) when the logged quantity (R, or Delta from a delta stage) keeps one non-zero sign s over the
    estimate and every resample, else a refusal. Under method gamma the rows are the estimate and its linearisation rows (not resamples), and the
    door is the declared number: |v| > door_z * SE_Gamma for every component (plan 0878), else a refusal."""
    x, q = (x["delta"] if isinstance(x, dict) else x), ctx.quantity
    s = np.sign(x[0])
    if (s == 0).any():
        return Null("NOT-EVALUATED", f"{q} = 0")
    if ctx.lin is not None:
        stats = [gamma_stat(ctx.lin, x[:, k], ctx.interval) for k in range(x.shape[1])]
        if None in stats:
            return Null("NOT-EVALUATED", f"no window: the autocorrelation of {q} is not summable at this N (window_max {ctx.interval['window_max']})")
        if not all(abs(x[0, k]) > ctx.interval["door_z"] * st.se for k, st in enumerate(stats)):
            return Null("NOT-EVALUATED", f"|{q}| <= door_z * SE ({ctx.interval['door_z']:g} Gamma-method SE): the sign of {q} is not resolved at this N")
    elif not (np.sign(x) == s).all():
        return Null("NOT-EVALUATED", f"sign of {q} not constant across the point estimate and every resample")
    return nodefield(project.logcoord(x, s), ctx)


def member(rules, name, pair, codes):
    """The membership of one control pair from the upstream codes of its two points, through the set's rule:
    the lowest-ranked membership of the two decides the door value. A value, never an exception."""
    r = rules[name]
    got = [codes[pt][r["reads"]] for pt in pair]
    mem = [r["map"][c] for c in got]
    low = min(mem, key=r["rank"].index)
    keep = [(pt, c) for pt, c, x in zip(pair, got, mem) if x == low]
    what = r["door"][low].lower().removeprefix("refuse-")
    return {"door": r["door"][low], "reason": f"{what}: [{', '.join(pt for pt, _ in keep)}] read "
            f"[{', '.join(c for _, c in keep)}] (membership.toml [{name}] reads {r['reads']})"}


def member_for(inst, rules, name, pair, codes):
    """The membership of one pair: the set's rule when it has one; else the instrument's DECLARED default door value (member_default),
    so a set that writes no rule for an instrument that declares one reads what the instrument declares. An instrument that
    declares no default needs its rule (a missing one is a KeyError here, as before)."""
    return member(rules, name, pair, codes) if name in rules or "member_default" not in inst else {
        "door": inst["member_default"], "reason": f"{inst['member_default'].lower()}: tables have no membership rule for {name}; the instrument's declared default"}


def ratio_of(door_value, drift, pair, log_ratio, rows):
    """The correction ratio r per resample row that a pair's door value selects (a total table over the door values): TRANSFORMED is the
    mean over the pair's two endpoints of the needle's own |v2|/|v1| = 3^-(drift + 1) read from needle_chain's resampled drift; RAW is 0
    (no correction, so y_inf = y2). `drift` and `log_ratio` are read only by the row that needs them."""
    return {"TRANSFORMED": lambda: np.mean([np.exp(-(drift(pt) + 1) * log_ratio()) for pt in pair], axis=0),
            "RAW": lambda: np.zeros(rows)}[door_value]()


def basis(x, ctx):
    """A TRANSFORMED pair is read only where the endpoints' correction decays (r < 1 at the estimate and every resample); a RAW pair has r = 0 and passes.
    Under method gamma a TRANSFORMED pair has no ratio (its r would need the drift and the pair linearised together): ctx.ratio is None and it is refused."""
    if ctx.ratio is None:
        return Null("NOT-EVALUATED", "method gamma does not declare the joint linearisation of the pair and the needle drift that a TRANSFORMED basis needs")
    return x if (ctx.ratio < 1).all() else Null("NOT-EVALUATED", "the endpoints' needle correction does not decay (r >= 1) at the estimate or a resample: y_inf is undefined")


def off_manifold(x, ctx):
    """A pair runs only when its membership door says RUN or RUN-FLAG-U; any other door value is its refusal."""
    return x if ctx.member["door"] in ("RUN", "RUN-FLAG-U") else Null(ctx.member["door"], ctx.member["reason"])


def decays(x, ctx):
    """The transform exists only where the needle's correction decays: ln r < 0 at the estimate and every resample, else a refusal."""
    return x if (x["lnr"] < 0).all() else Null("NOT-EVALUATED", "the needle's correction does not decay (r >= 1) at the estimate or a resample: y_inf is undefined")


def steps(x, ctx):
    """The per-step growths re-declared as a NodeField over the size steps (keeps growth, drops which sizes)."""
    return nodefield(x["y_steps"], ctx)
