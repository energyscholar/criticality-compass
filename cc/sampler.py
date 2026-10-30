"""cc/sampler.py - plan 1282 P1a: the declared sampler adapter. One call, (K, h, L, start, seed, run) -> the arrays a chain file stores (O, G, L, K).
The sampler is the toolset's heat bath (tools/lattice_field.py), loaded only after its three files match their pins; a mismatch is a VALUE (Mismatch),
never an import of unpinned code. Every table is total: a missing key raises KeyError and nothing catches it into a default. h is not a coupling of
the file (couplings = {"K": K}); it is an argument of the call and is recorded in the Call."""
import dataclasses
import hashlib
import importlib.util
import json
import math
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import formats
import schema

KC = math.log(1 + math.sqrt(2)) / 2
LABELS = {x: float(x) * KC for x in ("0.90", "0.95", "0.98", "1.00", "1.02", "1.05", "1.10")}   # label (K/K_c) -> K
SIZES = {27: 2, 81: 3, 243: 4}                      # L -> the number of block levels stored
STARTS = {"ordered": "plus", "random": "random"}    # the declared start -> the sampler's start name
CHAINS = range(10)
FAMILY_H = {"poc": 0.0, "decoy": 0.02}              # family -> the field h, the only source of h
PINS = {"lattice_field": "4162eb36e9e8f34fec82461e319beebd8bb2099bd533df5ef4a5859584cbb465", "scale": "1dff330d804d067e26f8c6c7dbe86739f0ee75635e5d1661f163d01bcf908f2b",
        "flow": "5f5b225a2cbc49bf2eef8c2168a2059620476c304fe71524eb687b12e1b9cae7"}
Q = {"key": "O", "level": 0}
GL = {27: {}, 81: {"GL": {"key": "G"}}, 243: {"GL": {"key": "G"}}}   # the full-depth G, stored for the sizes that have a second level to compare


@dataclasses.dataclass(frozen=True)
class Run:
    N: int
    skip: int
    burn: int


@dataclasses.dataclass(frozen=True, eq=False)
class Chain:
    O: np.ndarray
    G: np.ndarray
    L: int
    couplings: dict
    M1: np.ndarray = None


@dataclasses.dataclass(frozen=True)
class Call:
    K: float
    h: float
    L: int
    start: str
    seed: int
    run: Run


@dataclasses.dataclass(frozen=True)
class Mismatch:
    file: str


def seed_of(S, F, k, L, s, j):
    """The declared seed of one cell (A4.10): a pure function of the cell's name."""
    return 3_000_000_000 + int(hashlib.sha256(f"1282|{S}|{F}|{k}|{L}|{s}|{j}".encode("utf-8")).hexdigest()[:8], 16) % 1_000_000_000


def toolset_of(data_root):
    return Path(data_root).parent


def load(toolset):
    """The three pinned tools as a namespace (field, scale, flow), or the Mismatch of the first file whose sha256 is not its pin."""
    paths = {n: Path(toolset) / "tools" / f"{n}.py" for n in PINS}
    bad = [n for n, p in paths.items() if hashlib.sha256(p.read_bytes()).hexdigest() != PINS[n]]
    if bad:
        return Mismatch(f"tools/{bad[0]}.py")
    mods = {}
    for n, p in paths.items():
        spec = importlib.util.spec_from_file_location(f"_sampler_{n}", p)
        mods[n] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mods[n])
    return SimpleNamespace(field=mods["lattice_field"], scale=mods["scale"], flow=mods["flow"])


def sample(tools, K, h, L, start, seed, run):
    """(Chain, Call): run.N sweeps of the heat bath, each recorded as the (E, M) row, the g1 of every block level, and the level-1 block magnetisation."""
    begin, nlev = STARTS[start], SIZES[L]
    rng = np.random.default_rng(seed)
    O, G, M1 = [], [], []
    for s in tools.field.field_stream(L, K, h, run.N, run.skip, run.burn, rng, begin):
        lv = tools.scale.levels(s[None], nlev)
        G.append([tools.flow.g1(x)[0] for x in lv])
        O.append(tools.field.observables(s))
        M1.append(lv[1].sum())
    arr = lambda a: np.array(a, dtype=np.float64)   # noqa: E731
    return Chain(arr(O), arr(G), int(s.shape[-1]), {"K": K}, arr(M1)), Call(K, h, L, start, seed, run)


def write(chain, path):
    np.savez(path, O=chain.O, G=chain.G, L=chain.L, **chain.couplings)


def write_call(call, path):
    Path(path).with_suffix(".json").write_text(json.dumps(dataclasses.asdict(call), indent=1) + "\n")


def fname(L, start, chain):
    return f"L{L}_{start}_c{chain}.npz"


def arrays(L, start):
    """The m.toml arrays table of one file: total on (L, start), as the parent input's."""
    return {"plus": {"Q": Q}, "random": {"G": {"key": "G", "level": SIZES[L] - 1}, "E": Q, "Q": Q, **GL[L]}}[STARTS[start]]


def entry(path, point, L, start, chain):
    """One [[data.files]] block of m.toml, as a dict."""
    return {"point": point, "size": L, "start": start, "path": str(path), "chain": chain, "arrays": arrays(L, start)}


def transducer_model(F):
    return f"2D Ising in a uniform field h = {FAMILY_H[F]:g} (held fixed), heat bath (tools/lattice_field.py), K/K_c 0.90-1.10"


CARRIES_L = {"npz-v1": False, "npy-v1": False, "snapshots-v1": False, "image-stack-v1": False, "island-table-v1": False, "npz-sized-v1": True}   # total over cc.toml [alphabets] formats: does the format carry L by construction (A4.9)
CARRIED = tuple(k for k, v in CARRIES_L.items() if v)


def sized(p, loc, b, heads, fp, fmt):
    """The door's L check (plan 1282 P1b, A4.8): [] unless fmt carries L; else the finding, named by its field (.L.header/absent/shape/object/dtype/value), of the first row that does not hold.
    `fmt in CARRIED` is by equality, so a missing, non-str or unknown format never reaches the table (it stays the data.format finding). The dtype is read from L's header, so an object L is never unpickled."""
    if fmt not in CARRIED:
        return []
    h, row = heads(), lambda arm, msg, nxt: [schema.at(p, f"{loc}.L.{arm}", msg, nxt)]   # noqa: E731
    if not isinstance(h, dict):
        return row("header", "the file is not an npz: npz-sized-v1 stores keyed arrays", "write it with np.savez")
    if "L" not in h:
        return row("absent", "`L` missing: the file cannot show its size", "write the file with its 0-d `L` (npz-sized-v1 requires it)")
    if h["L"] != ():
        return row("shape", f"`L` has shape {h['L']}: it must be a 0-d scalar", "store L as a 0-d integer")
    with zipfile.ZipFile(fp) as z, z.open("L.npy") as f:
        dtype = formats.head_of(f)[1]
    if dtype.hasobject:
        return row("object", "`L` is an object array: npz-sized-v1 stores a plain integer", "store L as a 0-d integer")
    if not np.issubdtype(dtype, np.integer):
        return row("dtype", f"`L` has dtype {dtype}: it must be an integer", "store L as a 0-d integer")
    with np.load(fp) as z:
        stored = int(z["L"])
    return row("value", f"`L` stores {stored} but the file is declared at size {b['size']}", "declare the file at the size it stores, or fix the file") if stored != b["size"] else []
