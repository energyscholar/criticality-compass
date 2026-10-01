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


def relations_for(m, name):
    """The declared relation `name`, built through admit.declare (acyclic, one provenance per edge)."""
    r, ax = m["relations"][name], m["axes"]
    if r["template"] == "chain":
        n, edges = len(ax[r["axis"]]), [(i + 1, i) for i in range(len(ax[r["axis"]]) - 1)]
    elif r["template"] == "pair":
        n, edges = 2 * len(r["pairs"]), [(2 * k + 1, 2 * k) for k in range(len(r["pairs"]))]
    else:
        nb = m["observable"]["levels"][ax["size"].index(r["big"])]
        n, edges = 2 * nb - 1, [(k, nb + k - 1) for k in range(1, nb)]
    return admit.declare(n, edges, [Provenance(r["provenance"])] * len(edges))


def context(m, inst, size=None):
    sizes, rel = m["axes"]["size"], {n: relations_for(m, n) for n in inst["relations"]}
    k = len(sizes) - 1
    if "size" in rel:
        prov = Provenance(m["relations"]["size"]["provenance"])
        rel["steps"] = admit.declare(k, [(i + 1, i) for i in range(k - 1)], [prov] * (k - 1))
    nb = m["observable"]["levels"][sizes.index(m["relations"]["matched"]["big"])] if "matched" in rel else 0
    return Ctx(
        level=m["interval"]["level"], eps={c: m["eps"][e] for c, e in inst["columns"].items()}, rel=rel,
        log_ratio=np.log(np.array(sizes[1:], float) / np.array(sizes[:-1], float)),
        log_span=float(np.log(sizes[-1] / sizes[0])), top=k - 1, top_steps=k - 2,
        coarsest=nb - 2, big_final=nb - 1,
        sink_ordered=m.get("sinks", {}).get("ordered"), sink_disordered=m.get("sinks", {}).get("disordered"),
        unit_scale=m.get("two_start", {}).get("unit_scale", {}).get(str(size)))


def unit_keys(m, inst, point, size=None):
    """The data blocks one unit of the instrument reads, in the order its reduce expects them."""
    sizes, starts = declare.unit_blocks(m, inst)
    return [(point, s, st) for s in ([size] if inst["unit"] == "point-size" else sizes) for st in starts]


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
    return admit.nodefield(x) if np.isfinite(x).all() else Null("NOT-EVALUATED", "non-finite value")


def logcoord(x, ctx):
    """ln(s R) when R keeps one non-zero sign s over the estimate and every resample, else a refusal."""
    s = np.sign(x[0])
    if (s == 0).any():
        return Null("NOT-EVALUATED", "R = 0")
    if not (np.sign(x) == s).all():
        return Null("NOT-EVALUATED", "sign of R not constant across the point estimate and every resample")
    return nodefield(project.logcoord(x, s), ctx)


def steps(x, ctx):
    """The per-step growths re-declared as a NodeField over the size steps (keeps growth, drops which sizes)."""
    return nodefield(x["y_steps"], ctx)
