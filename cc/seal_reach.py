"""cc/seal_reach.py - plan 1282 P1c: the seal's three data-free refusals (seed uniqueness, reach, the licence table), each a VALUE of its output type."""
import dataclasses
import itertools

import detect
import door
import instrument_decl
import sampler
import schema

FAMILIES = ("poc", "decoy")
INVENTORY = ((0, 3_000_000_000, "earlier integer default_rng seeds (PRE A4.4)"),)   # half-open
LICENCE = {**dict.fromkeys(("REFUSE-EQUIL", "REFUSE-SLOW", "REFUSE-FLOW", "REFUSE-WEAK", "REFUSE-OFF", "REFUSE-IRRELEVANT", "REFUSE-UNRES"), "MISS-licensing"),
           **dict.fromkeys(("REFUSE-NEEDLE-UNMEASURED", "REFUSE-TWO-START-UNMEASURED", "REFUSE-FLOW-UNMEASURED", "REFUSE-ACROSS-UNMEASURED",
                            "REFUSE-STABILITY-UNMEASURED", "REFUSE-PROBE-INCOMPLETE", "REFUSE-PROBE-UNKNOWN"), "MISS-input")}   # PRE A2.5


@dataclasses.dataclass(frozen=True)
class Seeds:
    run: tuple
    pilot: tuple


@dataclasses.dataclass(frozen=True)
class SeedClash:
    dups: tuple
    hits: tuple


@dataclasses.dataclass(frozen=True)
class Atom:
    name: str
    why: str


@dataclasses.dataclass(frozen=True)
class Reach:
    atoms: tuple


@dataclasses.dataclass(frozen=True)
class Unreachable:
    atoms: tuple


@dataclasses.dataclass(frozen=True)
class Licensed:
    codes: tuple


@dataclasses.dataclass(frozen=True)
class LicenceGap:
    missing: tuple
    extra: tuple


@dataclasses.dataclass(frozen=True)
class Sealable:
    S: str
    seeds: Seeds
    atoms: tuple


def seal_seeds(S, *, seed_fn=sampler.seed_of, inventory=INVENTORY):
    """Seeds of the 840 run cells and 84 pilot cells, or the SeedClash of every duplicated seed and every seed inside an inventory range."""
    cells = list(itertools.product(FAMILIES, sampler.LABELS, sampler.SIZES, sampler.STARTS))
    keys = [(*c, j) for c in cells for j in (*sampler.CHAINS, "pilot")]
    seed = {k: int(seed_fn(S, *k)) for k in keys}
    by = {}
    for k in keys:
        by.setdefault(seed[k], []).append(k)
    dups = tuple(sorted(((v, tuple(sorted(ks, key=repr))) for v, ks in by.items() if len(ks) > 1), key=lambda d: (d[0], repr(d[1]))))
    hits = tuple(sorted(((seed[k], k, name) for k in keys for lo, hi, name in inventory if lo <= seed[k] < hi), key=lambda h: (h[0], repr(h[1]))))
    run = tuple(seed[k] for k in keys if k[4] != "pilot")
    pilot = tuple(seed[k] for k in keys if k[4] == "pilot")
    return SeedClash(dups, hits) if dups or hits else Seeds(run, pilot)


def atoms_of(T):
    """The registry atoms every code column of the v10 verdict table reads, the columns it ignores left out."""
    cols = schema.code_cols(T.codes)
    return sorted(set().union(*(detect.sources(c, cols) for c in T.verdict["columns"] if c not in T.verdict["ignores"])))


def why_instrument(n, m, root):
    """None when atom prefix `n` is reached; else the first failing clause: (ii) a relation of the instrument not declared, (iii) a per_point instrument with a point no control pair touches."""
    inst = instrument_decl.load(n, root)   # plan 1282 P2a (R-P2.3): the one loader

    def relation():
        return next((f"relation {r} not declared" for r in inst["relations"] if r not in m.get("relations", {})), None)

    def points():
        touched = {p for pair in door.control_pairs(m) for p in pair}
        u = [p for p in m["axes"]["point"] if p not in touched]
        return f"points {u} touched by no control pair" if u else None

    return next((w for w in (relation(), points() if inst["per_point"] and relation() is None else None) if w), None)


DECLARED = {"probe": lambda m, cp: (lambda v: None if v == "COMPLETE" else f"probe_of = {v}")(detect.probe_of(m, cp))}   # total on the declared kinds: another kind is a KeyError


def judge(atom, m, cp, root):
    """The Atom with why None when reached: `declared.<kind>` by the DECLARED table, `<n>.<col>` by its instrument (clause i: n declared)."""
    n, col = atom.split(".", 1)
    why = DECLARED[col](m, cp) if n == "declared" else why_instrument(n, m, root) if n in m["instruments"] else f"instrument {n} not declared"
    return Atom(atom, why)


def reach(m, cp, T, root):
    """Reach of all atoms v10 reads, or the Unreachable of every atom the declaration cannot reach (each with its first failing clause)."""
    judged = [judge(a, m, cp, root) for a in atoms_of(T)]
    bad = tuple(a for a in judged if a.why is not None)
    return Unreachable(bad) if bad else Reach(tuple(a.name for a in judged))


def licence_total(refuse):
    """Licensed (the refuse codes, in order) when every code is in LICENCE and none of LICENCE is missing from `refuse`, else the LicenceGap."""
    missing, extra = tuple(c for c in refuse if c not in LICENCE), tuple(c for c in LICENCE if c not in refuse)
    return LicenceGap(missing, extra) if missing or extra else Licensed(tuple(refuse))


def seal(S, m, cp, T, root):
    """Sealable when the licence table, reach and the seeds all succeed, else the first of LicenceGap, Unreachable, SeedClash."""
    got = (licence_total(T.verdict["refuse"]), reach(m, cp, T, root), seal_seeds(S))
    bad = [v for v in got if not isinstance(v, (Licensed, Reach, Seeds))]
    return bad[0] if bad else Sealable(S, got[2], got[1].atoms)
