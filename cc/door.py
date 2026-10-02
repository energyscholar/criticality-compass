"""door.py - between the data and the maths: context, relations, the resample plan, the doors (plumbing)."""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import admit
import declare
import project
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
    member: dict = None              # a pair unit: {"door": value, "reason": text} from the membership rule
    quantity: str = "R"              # the name a sign refusal gives the logged quantity


def relations_for(m, name):
    """The declared relation `name`, built through admit.declare (acyclic, one provenance per edge)."""
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        n, edges = len(ax[r["axis"]]), [(i + 1, i) for i in range(len(ax[r["axis"]]) - 1)]
    elif r["template"] == "pair":
        n, edges = 2 * len(r["pairs"]), [(2 * k + 1, 2 * k) for k in range(len(r["pairs"]))]
    elif r["template"] == "all-pairs":
        n, edges = len(ax[r["axis"]]), [(j, i) for j in range(1, len(ax[r["axis"]])) for i in range(j)]
    else:
        nb = m["observable"]["levels"][ax["size"].index(r["big"])]
        n, edges = 2 * nb - 1, [(k, nb + k - 1) for k in range(1, nb)]
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


def context(m, inst, size=None):
    sizes, rel = m["axes"]["size"], {n: relations_for(m, n) for n in inst["relations"]}
    k = len(sizes) - 1
    if "size" in rel:
        prov = Provenance(m["relations"]["size"]["provenance"])
        rel["steps"] = admit.declare(k, [(i + 1, i) for i in range(k - 1)], [prov] * (k - 1))
    nb = m["observable"]["levels"][sizes.index(m["relations"]["matched"]["big"])] if "matched" in rel else 0
    pair = inst["unit"] == "pair"
    unit_rel = admit.declare(2, [(1, 0)], [Provenance(m["relations"]["control"]["provenance"])]) if pair else None
    return Ctx(
        unit_rel=unit_rel, component_shape=(m["interval"]["resamples"] + 1, len(sizes)) if pair else None,
        pair_shape=(len(sizes), 2) if pair else None, quantity="Delta" if pair else "R",
        level=m["interval"]["level"], eps={c: m["eps"][e] for c, e in inst["columns"].items()}, rel=rel,
        log_ratio=np.log(np.array(sizes[1:], float) / np.array(sizes[:-1], float)),
        log_span=float(np.log(sizes[-1] / sizes[0])), top=k - 1, top_steps=k - 2,
        coarsest=nb - 2, big_final=nb - 1,
        sink_ordered=m.get("sinks", {}).get("ordered"), sink_disordered=m.get("sinks", {}).get("disordered"),
        unit_scale=m.get("two_start", {}).get("unit_scale", {}).get(str(size)),
        unit_scales=tuple(m.get("two_start", {}).get("unit_scale", {}).get(str(s)) for s in sizes))


def unit_keys(m, inst, point, size=None):
    """The data blocks one unit of the instrument reads, in the order its reduce expects them."""
    sizes, starts = declare.unit_blocks(m, inst)
    pts = point if isinstance(point, tuple) else (point,)   # a pair unit reads both of its points, a then b
    return [(pt, s, st) for s in ([size] if inst["unit"] == "point-size" else sizes) for pt in pts for st in starts]


def load_blocks(m, data_root):
    """[(block key, {array name: ndarray})] in data.files order, each array cut to its declared level."""
    cache, out = {}, []
    for b in m["data"]["files"]:
        path = str(Path(data_root) / b["path"])
        if path not in cache:
            cache[path] = np.load(path)
        z, arrs = cache[path], {}
        for name, a in b["arrays"].items():
            v = z if isinstance(z, np.ndarray) else z[a["key"]]
            arrs[name] = np.ascontiguousarray(v[:, a["level"]] if "level" in a else v)
        out.append(((b["point"], b["size"], b["start"]), arrs))
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


def nodefield(x, ctx):
    """The reduce outputs as a NodeField: every leading axis flattened into components (C order)."""
    x = x.reshape(-1, x.shape[-1])
    return admit.nodefield(x) if np.isfinite(x).all() else Null("NOT-EVALUATED", "non-finite value")


def logcoord(x, ctx):
    """ln(s v) when the logged quantity (R, or Delta from a delta stage) keeps one non-zero sign s over the
    estimate and every resample, else a refusal."""
    x, q = (x["delta"] if isinstance(x, dict) else x), ctx.quantity
    s = np.sign(x[0])
    if (s == 0).any():
        return Null("NOT-EVALUATED", f"{q} = 0")
    if not (np.sign(x) == s).all():
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


def off_manifold(x, ctx):
    """A pair runs only when its membership door says RUN or RUN-FLAG-U; any other door value is its refusal."""
    return x if ctx.member["door"] in ("RUN", "RUN-FLAG-U") else Null(ctx.member["door"], ctx.member["reason"])


def steps(x, ctx):
    """The per-step growths re-declared as a NodeField over the size steps (keeps growth, drops which sizes)."""
    return nodefield(x["y_steps"], ctx)
