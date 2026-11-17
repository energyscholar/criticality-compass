"""Plan 1558 — the hold setpoint sigma (contract/SCHEMA-1558.md), as a black box. Each needle test runs the needle as a separate
process against the scripted apparatus of contract/holdwire.py (plan 1552's fixture, FROZEN, imported unchanged) and holds it to
what it sent on the wire, what it wrote on stdout and what it appended to its map. FROZEN: the Generator makes this green; it does
not edit it.

What it pins:
  t01  a setpoint settings table outside its domain is refused before the wire (parse B): the key set, the band row, the park, and
       sigma, in the declared order. An inadmissible sigma cannot be written: the band row's type (`admissible`: band-measured,
       whole in ticks, strictly outside the band) refuses any list holding one, and a sigma that is not a member is refused however
       good a free number it is (owner ruling 2026-11-17); the type's description (`about`) is complete or the row is refused;
  t02  the door (parse A): a setpoint whose hold cannot fit on the dial is refused at `sigma` after `declare`; one that fits runs;
  t03  the start record and the map head of a setpoint drop;
  t04  the park cycle, FEEDBACK ON: after every hold pair, whole strides then one park reading AT the setpoint, sigma*g ticks from
       the new centre on the side AWAY from the declared ordered side; then strides back to the next low probe;
  t05  the park reading enters no table: the hold steps of a setpoint drop are the hold steps of plan 1552's needle;
  t06  the safe side is the DIAL's declared ordered_side, never the observable's sign and never the readings;
  t07  FEEDBACK OFF: the park is a scan of the setpoint, nothing moves, the centre never moves;
  t08  the dial's end: a setpoint that would leave the dial is a range kind (OFF-DIAL), no clamp and no refused call;
  t09  the horizon: the wire's refusal ends a setpoint stream with a step that has no reading;
  t10  the reader: every prefix of a setpoint report reads, its map is the map of its report, one changed park field is unreadable,
       and a plan 1552 map that names a park phase is refused;
  t11  the reader's numbers: sigma in both units, the settle times with the park, and the needle's MEASURED dead band;
  t12  the scorer: setpoint_score's keys and numbers, the mirrored truth as the null, and score() unchanged for a setpoint stream;
  t13  the orchestrator: a setpoint run writes setpoint.json beside score.json (and a plan 1552 run does not); a dead-band sigma is
       refused before a server;
  t14  sigma = 0 IS plan 1552: `hold-pair-v1` writes the same bytes, stdout and map, as at base, on nine pinned worlds;
  t15  the tables are total, and with a reach of g on both sides they are plan 1552's tables;
  t16  the two shipped setpoint settings files hold the declared numbers (their band COMPUTED from contract/drift-band.json,
       plan 1561's compass-drift-band/1 table, over the HELD runs only); every setpoint run of that table has a lock and a number;
       every rung measured at sigma 0 is measured at every measured sigma; the shipped type is the table's at the table's geometry;
       its description is complete and every number in it is the members' (ticks = sigma*g, the cycle row, derived labels, the
       table's sha); ramp's first rung is in the setpoint needle's domain; plan 1552's contract files are byte-identical;
  t17  every lag rule of navigator/hold.py goes through holdtab: no line names the lag outside HT.settled / HT.commanded except
       the lines plan 1552's base already has (code only; comments are cut).

RED at base (no `hold-setpoint-v1`: every setpoint settings file is refused at `dead_band`, the first key 1552 does not know).
Run from the repo root:  python contract/test_hold_setpoint.py   (or pytest)
"""
import copy
import hashlib
import json
import math
from fractions import Fraction
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import holdwire as W  # noqa: E402
import test_hold_score as S  # noqa: E402   (plan 1552's orchestrator helpers, FROZEN: _setup, _run, _rows, WORLD)

ROOT = W.ROOT
G = 12
BAND_TABLE = json.loads((Path(__file__).resolve().parent / "drift-band.json").read_text())   # the band's INPUT: compass-drift-band/1 (plan 1561)
BAND_LAWS = ("ramp", "ramp-reversed", "sine", "walk")   # the band's domain (coordinator with the 1561 audit): step drift is REPORT-ONLY
BAND_ROWS = [r for r in BAND_TABLE["rows"] if r["sigma"] > 0 and r["law"] in BAND_LAWS]   # setpoint rows in the band's laws (sigma 0 = plan 1552's centre)
# The band's domain is a TOTAL table over each band run's lock (rev 5, cold audit B1; coordinator ruling): a HELD run contributes
# its p95; a broken run contributes nothing and takes its rung out of the setpoint needle's domain (a REPORT row); a run with no
# evidence is a gap, and a table with a gap is refused (t16). An unknown lock or a run with no lock is a KeyError, never a default.
LOCK_CLASS = {"HELD": "band", "RECOVERED": "out", "LOST": "out", "LEFT-RANGE": "out",
              **{k: "gap" for k in ("CUT-SHORT", "REFUSED", "FAILED", "MISSING", "MISMATCH")}}


def band_runs(table, rows):
    """(row, seed, class, p95) for every run of every row: the seeds with a number and the seeds `missing` (a gap)."""
    out = []
    for r in rows:
        num = dict(zip(r["seeds"], r["p95"]))
        for s in sorted([*r["seeds"], *r["missing"]]):
            c = LOCK_CLASS[table["locks"][f"{r['law']}--{r['rung']}--{r['needle']}--s{s}"]]
            ok = s in num and type(num[s]) in (int, float) and math.isfinite(num[s])
            out.append((r, s, c if ok or c != "band" else "gap", num[s] if ok else None))
    return out


BAND_RUNS = band_runs(BAND_TABLE, BAND_ROWS)
cell = lambda r: f"{r['law']}/{r['direction']}/{r['rung']}"         # a band cell, as the description names it
MEASURED = sorted({r["sigma"] for r in BAND_ROWS})                    # the sigmas the band run measured (its candidates)
# THE DOMAIN, per measured sigma (rev 6, cold audit M4): a cell HELD on every seed is in it; a cell with any broken seed is OUT.
# The description states both, so Finding D reaches every tooltip. The band is the max over the DOMAIN cells only (rev 6, cold
# audit m4, coordinator ruling on plan 1561's full table): a rung is a band row at a sigma only if it HELD on every seed there,
# so a surviving seed of a broken cell never sets the band (survivorship), and the band and the domain agree.
DOMAIN = {x: [cell(r) for r in BAND_ROWS if r["sigma"] == x and {c for q, s, c, p in BAND_RUNS if q is r} == {"band"}] for x in MEASURED}
OUT = {x: [cell(r) for r in BAND_ROWS if r["sigma"] == x and "out" in {c for q, s, c, p in BAND_RUNS if q is r}] for x in MEASURED}
HELD_P95 = [p for r, s, c, p in BAND_RUNS if cell(r) in DOMAIN[r["sigma"]]]   # every run of a domain cell is HELD
assert HELD_P95, "no HELD sigma > 0 run in the band's laws: the band has no domain (a finding for the owner, never a default band)"
DEAD_BAND = math.ceil(max(HELD_P95))                                  # COMPUTED over the HELD runs, from the table, never typed (owner ruling, audit 2 N1)
OUT_OF_DOMAIN = sorted({(r["law"], r["direction"], r["rung"], r["sigma"]) for r, s, c, p in BAND_RUNS if c == "out"})
GAPS = [(r["law"], r["rung"], r["needle"], s) for r, s, c, p in BAND_RUNS if c == "gap"]
# The cases below are proven at bands of 15 and 22; they assume 12 <= DEAD_BAND <= 24 (INT_OUT + 1 and the quarter-g cases sit
# inside one g of the band). t16 names a band outside that range (rev 6, m3): never an import-time death with no named pair.
PROVEN = (12, 24)
# Every case below is COMPUTED from DEAD_BAND: a new table needs a re-pin, never a new test (coordinator, revision 3).
# The shipped sigmas live on a grid of half a g: SIGMA_LO is the least sigma on it whose sigma*g is strictly outside the band,
# SIGMA_HI the next (15 ticks: 1.5 and 2). Cases off that grid use quarters of a g (3 ticks): SIGMA_IN is the largest quarter
# inside the band (closed), INT_OUT the least whole sigma outside it.
whole = lambda x: int(x) if x == int(x) else x                       # 2.0 is written 2 (the shipped files' TOML types)
SIGMA_LO = whole((DEAD_BAND // (G // 2) + 1) / 2)
SIGMA_HI = whole(SIGMA_LO + 0.5)
SIGMA_IN = whole(DEAD_BAND // (G // 4) / 4)
INT_OUT = DEAD_BAND // G + 1
OFF_HI = int(SIGMA_HI * G)                                           # the high setpoint's offset in ticks (24 at a band of 15)
MAX_NUDGE = 32                                                       # holdwire's declared max_nudge (plan 1552's fixture, FROZEN)
IGNITE_GRID = W.CFG["ignite"]["steps"][0]                            # the door's ignite row: T is a whole number of ignite steps
T_DOOR = -(-((INT_OUT + 6) * G) // IGNITE_GRID) * IGNITE_GRID        # the door's dial, well clear of the band (100 at a band of 15)
FIT = (T_DOOR - G) // G                                              # the largest whole sigma that fits it: FIT*g + g <= T_DOOR < (FIT+1)*g + g
BIND = ("S", "n_eq", "z", "g", "step", "park")  # the hold geometry the band was measured at (the park's length sets the lag): a band carries it, and must match
SHAPE = "hold-setpoint-v1"
ORDER = ("needle_structure", "ops", "g", "step", "n_eq", "S", "skip", "z", "dead_band", "sigma", "ignite", "approach", "park", "lost", "M")


def adm(x, g, ticks):
    """x is a member a band row of `ticks` at half-width `g` can hold: a finite number > 0, never a bool, x*g whole and > ticks."""
    if not (type(x) in (int, float) and 0 < x < math.inf):
        return False
    q = Fraction(repr(x)) * g
    return q.denominator == 1 and q > ticks


ADMISSIBLE = [x for x in MEASURED if adm(x, G, DEAD_BAND)]          # THE TYPE (owner ruling 2026-11-17): measured AND outside the band


def admissible(sigma, g=G, ticks=DEAD_BAND):
    """a band row's admissible list: the table's members at this g and band, plus the case's own sigma when it would be one (so a
    case reaches the rule it tests); a sigma that cannot be a member is left OUT, never written into the list."""
    return [whole(x) for x in sorted({*(x for x in MEASURED if adm(x, g, ticks)), *([sigma] if adm(sigma, g, ticks) else [])})]


BAND_SHA = hashlib.sha256((Path(__file__).resolve().parent / "drift-band.json").read_bytes()).hexdigest()
ABOUT = ("meaning", "units", "conversion", "band", "cost", "provenance", "members")   # the description's fields (holdtab.ABOUT)


def ticks_of(x, g):
    return int(Fraction(repr(x)) * g)                                 # an admissible member's offset: whole by the type


def cycle_upper(cfg, sigma, side, max_nudge):
    """SCHEMA-1558 4.4's setpoint cycle row (an upper bound, in sweeps) at these settings, side and max_nudge; re-derived here, not
    imported (the module must load against the unbuilt tree): a walk of d ticks is ceil(|d|/M) - 1 whole strides."""
    r = lambda x: x["n_eq"] + x["S"] * cfg["skip"]
    off, s, g = ticks_of(sigma, cfg["g"]), {"+": -1, "-": 1}[side], cfg["g"]
    n = lambda d: max(0, -(-abs(d) // max_nudge) - 1)
    w = max(n(m + s * off - g) + n(s * off + g) for m in (-cfg["step"], 0, cfg["step"]))
    return 2 * r(cfg) + r(cfg["park"]) + w * r(cfg["approach"])


def label(m, about):
    """a member's label: DERIVED from the description's fields, never written by a surface."""
    return (f"sigma {m['sigma']} g = {m['ticks']} ticks from the crossing, on the safe side; band {about['band']['ticks']} ticks; "
            f"cycle <= {m['cycle']['plus']} sweeps on a + dial, {m['cycle']['minus']} on a - dial; "
            f"held on {len(m['domain'])} cells, out of its domain on: {', '.join(m['out']) or 'none'}")


def describe(g, ticks, members, max_nudge=MAX_NUDGE):
    """THE description of the admissible type at the table's geometry (owner ruling 2026-11-17): data, from the band table, the
    one source every surface renders its tooltip from. The band writer (Phase 4) writes it; the shipped files carry it. Its cost
    is the cycle at the TABLE's geometry (a case's own cells may be wrong: that is what it tests) with plan 1552's approach and skip;
    `g` is the row's (a case may move it with its band, e.g. 0.57 at g 100)."""
    cfg = {**BAND_TABLE["geometry"], "g": g, "skip": W.CFG["skip"], "approach": W.CFG["approach"]}
    about = {
        "meaning": "the setpoint: an UNSIGNED offset from the critical crossing; the needle parks the dial that far on the dial's "
                   "declared SAFE side (away from its ordered_side) after every hold pair",
        "units": "sigma, in pair half-widths g",
        "conversion": {"ticks": "sigma * g", "g_ticks": cfg["g"],
                       "knob_per_tick": "(hi - lo) / T of the System's declared dial (the System's, read at run time: the reader's sigma().value)"},
        "band": {"ticks": ticks, "p95_max": max(HELD_P95), "laws": list(BAND_LAWS), "bound_to": list(BIND),
                 "promise": "per-run p95 of |park - edge - sigma*g| <= ticks on every HELD run of the laws, at the geometry bound_to names "
                            "(this row's own cells); a member is band-measured and sigma*g is strictly outside the band"},
        "cost": {"unit": "sweeps per cycle, an upper bound (SCHEMA-1558 4.4): the precision-lag trade", "max_nudge": max_nudge,
                 "skip": cfg["skip"], "approach": dict(cfg["approach"])},
        "provenance": {"sha256": BAND_SHA},   # the band table's sha ONLY: its file name carries a word M2 forbids in any map
        "members": [],
    }
    for x in members:
        m = {"sigma": x, "ticks": ticks_of(x, cfg["g"]),
             "cycle": {"plus": cycle_upper(cfg, x, "+", max_nudge), "minus": cycle_upper(cfg, x, "-", max_nudge)},
             "domain": DOMAIN.get(x, []), "out": OUT.get(x, [])}   # law/direction/rung cells: HELD on every seed / any seed broke
        about["members"].append({**m, "label": label(m, about)})
    return about


def band(cfg, ticks=DEAD_BAND):
    g = cfg["g"] if type(cfg["g"]) is int and cfg["g"] > 0 else G   # a case with a bad g is refused at g, before dead_band
    adm_ = admissible(cfg["sigma"], g, ticks)
    return {"ticks": ticks, **{k: cfg[k] for k in BIND}, "admissible": adm_, "about": describe(g, ticks, adm_)}


def with_sigma(cfg, sigma):
    """cfg at another sigma, its band declaring that sigma measured (so a case reaches the rule it tests, not the membership)."""
    adm_ = admissible(sigma, cfg["g"], cfg["dead_band"]["ticks"])
    return {**cfg, "sigma": sigma, "dead_band": {**cfg["dead_band"], "admissible": adm_, "about": describe(cfg["g"], cfg["dead_band"]["ticks"], adm_)}}


def unband(cfg):
    return {k: v for k, v in cfg.items() if k != "dead_band"}


def setpoint_cfg(base=W.CFG, sigma=SIGMA_LO, ticks=DEAD_BAND, park=None, **over):
    """a hold-setpoint-v1 table built from a plan 1552 table: the 15 keys in the schema's order; the band bound to its geometry."""
    park = park or {"S": base["S"], "n_eq": base["n_eq"]}
    d = {**base, "needle_structure": SHAPE, "sigma": sigma, "park": park, **over}
    d["dead_band"] = over.get("dead_band", band(d, ticks))   # .get: a case may pass its OWN (wrong) band; else the bound one (minor 5)
    return {k: d[k] for k in ORDER if k in d} | {k: v for k, v in d.items() if k not in ORDER}


SET = setpoint_cfg()                                  # navigator/setpoint-settled.toml
SET2 = setpoint_cfg(sigma=SIGMA_HI)                   # navigator/setpoint-settled-2.toml
SHORT = {"horizon": 60000}
COMMON = {"segment", "pos", "window", "values", "errors", "settled", "classes", "kernel"}
FROZEN_1552 = {
    "contract/holdwire.py": "d5d0ea62cbae2afe6abbd6c3186bf8db25356bbe43f2f5a368450c57e463a22d",
    "contract/test_hold_needle.py": "c7b0a4debf13b3a4db2a373d6fdf1632592c81d9c9eb5cceb16147466295714d",
    "contract/test_hold_reader.py": "bb82b9687ca7abfa4d862dc3aa2bd276d429653e7fc16bde66b2de6bccd949f9",
    "contract/test_hold_score.py": "66fc632baad7160b00737b1293335a173bc58d7b6d6b47ca5c749b537d7faf01",
    "contract/SCHEMA-1552.md": "35c76fa4ccb0a512bde063dac63193a9063498b0838e87a289f567e1bdc931d5",
    "navigator/hold-settled.toml": "50e53bdbd9911418d82255d8eaf7cf548ccf0645ffa28df9d59869f0db9a2bc2",
    "navigator/hold-mid.toml": "568146d27ee2f468fa4b7c8f821a06acf7bd66998d60b4d1dbd38d2d89ed1773",
}
# t14: sha256 of (stdout + "\n#MAP\n" + map) of plan 1552's needle (navigator/hold.py sha256 45ac04ef..., the same at 8ad9bbe, 9535e0c, e3790a0 and the base 4df8a87), on the worlds of _v1_worlds()
V1_PINS = {
    ("settled", "sign"): "06dc81873a1170d134ca7bc827d6a2a361b28e0c81b5cdda5e52363edd984d96",
    ("settled", "drift"): "467053d4a997bef838b635ada538c387369504bf561454cecbb3142ae8c5f525",
    ("settled", "minus"): "3afc7cebb3a887c8ec0ee62d5e95090e35e6298482947732f36b433df689f46e",
    ("mid", "sign"): "3b0ec7fe51851ddb27943e8abee264ae8766c41611cc40b948ea49d4264295d9",
    ("mid", "drift"): "6526b7517644bd544011f6343cebcd01461c0af65a221e62da96f3ba6ff37aac",
    ("mid", "minus"): "9233d81a20a1d52d049be63d1adb0987a4cc331e38b15812e4f4f5636a9c2ff0",
    ("off", "sign"): "02ef2299d68f0b0943a6acc3c17f63f4320a5be3e55315c23519a43c95b38140",
    ("off", "drift"): "29d8d6cb84fca4027d6af94d94bc17c60660af996fdf5491ad627a5f15f0c3ab",
    ("off", "minus"): "63091f3e640f6003fcb38296ac3c576a3e5cfc7bd66729b9a8165293fc641b15",
}


def lin(x, slope=0.004):
    at = x if callable(x) else (lambda index: x)
    return lambda tick, index, n: slope * (tick - at(index))


def refusal(got):
    return got.err.strip().splitlines()[-1] if got.err.strip() else ""


def of(got, phase):
    return [s for s in got.steps if s["phase"] == phase and s["evaluated"]]


def _lib():
    from environment import hold_score as HS
    from needlestream import read as NS
    from needlestream import read_hold as RH
    return HS, NS, RH


# ---------------------------------------------------------------- refusals
def test_t01_setpoint_settings_outside_their_domain_are_refused_before_the_wire(tmp):
    no = lambda k: {a: b for a, b in SET.items() if a != k}
    cases = [
        ("dead_band", no("dead_band")), ("park", no("park")), ("extra", {**SET, "extra": 1}),
        ("dead_band", {**W.CFG, "dead_band": SET["dead_band"]}),                # plan 1552's shape knows no dead band
        ("dead_band", {**SET, "needle_structure": "hold-setpoint-v2"}),          # a name that is no shape reads as plan 1552's table
        # each sigma below is refused as a NON-MEMBER: none can be written into the type (admissible() leaves it out, as the band
        # writer does), so the rule that keeps it out is the type's, tested on the admissible list further down
        ("sigma", with_sigma(SET, 0)), ("sigma", with_sigma(SET, -1)), ("sigma", with_sigma(SET, True)),
        ("sigma", with_sigma(SET, "1")), ("sigma", with_sigma(SET, 0.3)),     # 3.6 ticks: not a whole number of ticks
        ("sigma", with_sigma(SET, 0.25)),                                       # 3 ticks: inside the dead band
        ("sigma", with_sigma(SET, whole(SIGMA_IN - 0.25))), ("sigma", with_sigma(SET, SIGMA_IN)),   # inside the declared band (closed)
        ("sigma", setpoint_cfg(sigma=SIGMA_LO, ticks=int(SIGMA_LO * G))),     # the shipped sigma, its band raised to it: inside (closed)
        ("sigma", setpoint_cfg(sigma=0.75, ticks=9)),                            # 9 ticks = a dead band of 9: inside (the band is closed)
        ("sigma", setpoint_cfg(sigma=0.5, ticks=6)), ("sigma", with_sigma(SET, float("inf"))),
        ("sigma", setpoint_cfg(sigma=0.8, ticks=8)),                             # 9.6 ticks: outside the band, but not whole: refused, never floored
        ("sigma", {**SET, "sigma": INT_OUT + 1}),                                # outside the band and whole, but never band-measured (B2, M3)
        # THE TYPE: the band row's admissible list is non-empty, strictly increasing, every member a finite number > 0 (never a
        # bool), whole in ticks and strictly outside the band; a list holding any other member is not the type (owner ruling)
        *(("dead_band", {**SET, "dead_band": {**SET["dead_band"], "admissible": v}}) for v in
          ([], "x", 1.5, [True], [0], [-1.5], [float("inf")], ["1.5"], [ADMISSIBLE[-1], ADMISSIBLE[0]], [ADMISSIBLE[0], ADMISSIBLE[0]],
           [whole(SIGMA_IN), *ADMISSIBLE], [whole(SIGMA_IN - 0.25), *ADMISSIBLE],     # a member at or inside the band (closed)
           [0.3, *ADMISSIBLE], [*ADMISSIBLE, ADMISSIBLE[-1] + 0.01])),                 # a member that is not whole in ticks
        # a member EXACTLY at the band (closed), whatever the band: the row's band raised to its least member's ticks, its description
        # regenerated for it (rev 6: at a band of 13 no quarter-g sigma sits on the band, so the closed edge needs its own case)
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "ticks": int(ADMISSIBLE[0] * G),
                                            "about": describe(G, int(ADMISSIBLE[0] * G), list(ADMISSIBLE))}}),
        # a sigma that is NOT a member is refused, however good a free float it would be (owner ruling: no free sigma field)
        ("sigma", {**SET, "sigma": whole(SIGMA_HI + 0.5)}), ("sigma", {**SET, "sigma": float(INT_OUT + 1)}),
        ("sigma", {**SET, "sigma": ADMISSIBLE[0] + 0.01}),          # a hair from a member (a fraction of a tick): never "close enough"
        # the description is part of the type: a band row without it, or with a field missing or added, is refused
        ("dead_band", {**SET, "dead_band": {k: v for k, v in SET["dead_band"].items() if k != "about"}}),
        *(("dead_band", {**SET, "dead_band": {**SET["dead_band"], "about": a}}) for a in
          ("x", {k: v for k, v in SET["dead_band"]["about"].items() if k != "cost"}, {**SET["dead_band"]["about"], "note": "x"})),
        ("dead_band", {**SET, "dead_band": {k: v for k, v in SET["dead_band"].items() if k != "admissible"}}),
        ("dead_band", {**SET, "dead_band": 8}),                                  # a bare number: no geometry, refused
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "ticks": -1}}), ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "ticks": 8.0}}),
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "ticks": True}}),
        # a band measured at another geometry is never reused: each bound key changed in the table, or in the band
        *(("dead_band", {**SET, k: v}) for k, v in (("S", 40), ("n_eq", 449), ("z", 3.0), ("g", 11), ("step", 4), ("park", {"S": 5000, "n_eq": 450}))),
        *(("dead_band", {**SET, "dead_band": {**SET["dead_band"], k: v}}) for k, v in (("S", 40), ("n_eq", 449), ("z", 3.0), ("g", 11), ("step", 4),
                                                                                       ("park", {"S": 5000, "n_eq": 450}))),
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "z": 2}}),      # the same value, another type
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "park": {"S": 500.0, "n_eq": 450}}}),   # ... inside the park's table too
        ("dead_band", {**SET, "dead_band": {**SET["dead_band"], "park": {"S": 500, "n_eq": 450, "skip": 1}}}),
        ("dead_band", {**SET, "dead_band": {k: v for k, v in SET["dead_band"].items() if k != "z"}}),
        # a park outside its domain, its band bound to it (so the band passes and the park is the first refusal)
        ("park", setpoint_cfg(park={"S": 39, "n_eq": 0})), ("park", setpoint_cfg(park={"S": 500})),
        ("park", setpoint_cfg(park={"S": 500, "n_eq": -1})), ("park", setpoint_cfg(park={"S": 500, "n_eq": 0, "skip": 1})),
        # the order of the table: the first field outside its domain, in ORDER
        ("dead_band", {**SET, "dead_band": "x", "sigma": 0}), ("n_eq", {**with_sigma(SET, 0), "n_eq": -1}),
        ("g", {**SET, "g": 0, "sigma": 0}), ("sigma", setpoint_cfg(sigma=0, park={"S": 1, "n_eq": 0})),
        ("z", {**SET, "z": 0.0, "dead_band": "x"}), ("sigma", {**with_sigma(SET, 0), "ignite": "x", "approach": "x"}),
    ]
    for n, (field, cfg) in enumerate(cases):
        got = W.drop(tmp, W.sign_world(603.5), cfg, name=f"c{n}", map_name=f"m{n}.jsonl", **SHORT)
        assert got.rc == 2 and refusal(got) == f"RefusedToStart field={field} parse=B", (n, field, got.rc, got.err[-300:])
        assert got.out == "" and got.map is None and got.fake.requests == [], (n, field, got.out[:100])
    for n, sigma in enumerate((INT_OUT, float(INT_OUT), SIGMA_LO, SIGMA_LO + 0.25, SIGMA_IN + 0.25, INT_OUT + 1)):   # all outside the band
        got = W.drop(tmp, W.sign_world(603.5), with_sigma(SET, sigma), name=f"ok{n}", map_name=f"ok{n}.jsonl", horizon=20000)
        assert got.rc == 0 and got.steps and got.records[0]["sigma"]["ticks"] == int(sigma * G), (sigma, got.rc, got.err[-200:])
    # whole in ticks EXACTLY: 0.57 * 100 is 56.99999999999999 in floats, 57 ticks as written; it passes parse B (the door then refuses g)
    got = W.drop(tmp, W.sign_world(603.5), setpoint_cfg(g=100, sigma=0.57), name="exact", map_name="exact.jsonl", **SHORT)
    assert got.rc == 2 and refusal(got) == "RefusedToStart field=g parse=A", got.err[-200:]


def test_t02_the_door_a_hold_that_cannot_fit_on_the_dial(tmp):
    for n, (sigma, side) in enumerate(((FIT + 1, "+"), (FIT + 1, "-"), (FIT + 2, "+"))):         # sigma*g + g > T_DOOR
        got = W.drop(tmp, W.sign_world(50.5), with_sigma(SET, sigma), name=f"d{n}", map_name=f"d{n}.jsonl", T=T_DOOR, horizon=20000,
                     declared={"ordered_side": {"K": side}})
        assert got.rc == 2 and refusal(got) == "RefusedToStart field=sigma parse=A", (sigma, side, got.rc, got.err[-200:])
        assert got.out == "" and got.map is None and got.fake.requests == [{"op": "declare"}], got.fake.requests[:3]
    fits = W.drop(tmp, W.sign_world(T_DOOR - 9.5), with_sigma(SET, FIT), name="fits", map_name="fits.jsonl", T=T_DOOR, horizon=20000)
    assert fits.rc == 0 and fits.records[0]["rec"] == "start", (fits.rc, fits.err[-200:])          # FIT*g + g <= T_DOOR
    # a setpoint needle reads its pair SETTLED (n_eq >= the declared lag + skip = 49): a mid-move pair is refused at the door
    for n, (cfg, want) in enumerate(((setpoint_cfg(n_eq=0), "n_eq"), (setpoint_cfg(n_eq=48), "n_eq"), (setpoint_cfg(n_eq=0, sigma=FIT + 1), "sigma"),
                                     (setpoint_cfg(park={"S": 500, "n_eq": 0}), "park"), (setpoint_cfg(park={"S": 500, "n_eq": 48}), "park"),
                                     (setpoint_cfg(n_eq=0, park={"S": 500, "n_eq": 0}), "n_eq"))):   # the park reads settled too
        got = W.drop(tmp, W.sign_world(50.5), cfg, name=f"m{n}", map_name=f"mm{n}.jsonl", T=T_DOOR if want == "sigma" else 1200, horizon=20000)
        assert got.rc == 2 and refusal(got) == f"RefusedToStart field={want} parse=A", (n, got.rc, got.err[-200:])
        assert got.out == "" and got.map is None and got.fake.requests == [{"op": "declare"}], got.fake.requests[:3]
    edge = W.drop(tmp, W.sign_world(603.5), setpoint_cfg(n_eq=49, park={"S": 500, "n_eq": 49}), name="edge", map_name="edge.jsonl", horizon=40000)
    holds = of(edge, "hold")
    assert edge.rc == 0 and len(holds) >= 3 and all(all(s["pair"]["settled"]) for s in holds), (edge.rc, edge.err[-200:])
    v1 = W.drop(tmp, W.sign_world(603.5), W.MID, name="v1mid", map_name="v1mid.jsonl", horizon=40000)
    assert v1.rc == 0 and v1.records[0]["rec"] == "start", v1.err[-200:]                       # plan 1552's mid-move needle is unchanged


# ---------------------------------------------------------------- the start record, the park cycle
def test_t03_the_start_record_and_the_map_head(tmp):
    got = W.drop(tmp, W.sign_world(603.5), SET2, **SHORT)
    assert got.rc == 0, got.err[-300:]
    s = got.records[0]
    assert s["needle"] == SHAPE and s["settings"] == SET2, s["needle"]
    assert s["sigma"] == {"offset": SIGMA_HI, "unit": "g", "measured": "pair-half-width", "ticks": OFF_HI, "dead_band": SET2["dead_band"]}, s["sigma"]
    h = got.entries[0]
    assert h["needle"] == SHAPE and h["map"] == "compass-map/1", h
    assert h["n_eq"] == {"ignite": 450, "approach": 48, "hold": 450, "walk": 48, "park": 450}, h["n_eq"]   # total over the shape's PHASES: a walk reads at the approach settle


def test_t04_the_park_cycle_feedback_on(tmp):
    drifting = lin(lambda i: 603.5 + i * 0.001)              # the crossing moves, so the hold moves its centre before most parks
    mid = whole(SIGMA_LO + 0.25)
    for cfg, sigma, world, k in ((SET, SIGMA_LO, lin(603.5), "a"), (SET2, SIGMA_HI, lin(603.5), "b"),
                                 (setpoint_cfg(sigma=mid, park={"S": 120, "n_eq": 96}), mid, lin(603.5), "c"),
                                 (SET, SIGMA_LO, drifting, "d"), (setpoint_cfg(sigma=INT_OUT + 2), INT_OUT + 2, lin(603.5), "e")):   # e: the walk BACK strides too
        got = W.drop(tmp, world, cfg, name=f"p{k}", map_name=f"p{k}.jsonl", horizon=80000)
        assert got.rc == 0, got.err[-300:]
        off = int(sigma * G)
        steps = got.steps
        first = next(i for i, s in enumerate(steps) if s["phase"] == "hold")
        parks = moved = 0
        for i in range(first, len(steps) - 1):
            s = steps[i]
            if s["phase"] != "hold" or not s["evaluated"] or s["verdict"][0]["kind"] in ("range-low", "range-high"):
                continue
            centre = s["pair"]["centre"] + s["verdict"][0]["ticks"]
            j = i + 1
            while j < len(steps) and steps[j]["phase"] == "walk":
                w = steps[j]
                assert w["verdict"][0]["kind"] == "moving" and abs(w["verdict"][0]["ticks"]) == MAX_NUDGE and w["leg"]["d"] == w["verdict"][0]["ticks"], w
                j += 1
            if j >= len(steps) or not steps[j]["evaluated"]:
                break
            p = steps[j]
            assert p["phase"] == "park", (sigma, i, p["phase"])
            v = p["verdict"][0]
            assert v["kind"] == "park" and v["ticks"] is None and v["reason"] == p["park"]["classes"][0], v
            assert set(p["park"]) == COMMON | {"n", "centre", "setpoint"}, sorted(p["park"])
            assert p["park"]["n"] == s["pair"]["n"] and p["park"]["centre"] == centre and p["park"]["setpoint"] == centre - off, p["park"]
            assert p["park"]["pos"] == [centre - off] and s["pair"]["setpoint"] == s["pair"]["centre"] - off, (p["park"]["pos"], s["pair"])
            parks += 1
            moved += s["verdict"][0]["ticks"] != 0
        assert parks >= 5 and (k != "d" or moved >= 5), (sigma, parks, moved)       # the park reads the centre AFTER the hold's move
        moves = [m for m in got.measured if m["op"] == "nudge"]
        assert all(abs(m["d"][0]) <= MAX_NUDGE for m in moves) and got.fake.refused == 1, got.fake.refused      # only the horizon is refused
        served = iter(got.fake.readings)                     # the readings in the order served: each evaluated step holds the next len(pos)
        for s in got.steps:
            mine = [next(served) for _ in (s[{"ignite": "grid", "approach": "leg", "hold": "pair", "walk": "leg", "park": "park"}[s["phase"]]]["pos"]
                                           if s["evaluated"] else ())]
            if s["phase"] == "park" and s["evaluated"]:
                assert [(r["op"], r["tick"], r["n_eq"], r["S"]) for r in mine] == [("nudge", s["park"]["setpoint"], cfg["park"]["n_eq"], cfg["park"]["S"])], mine
                assert mine[0]["D"] < 0, "a park on the ordered side"
            if s["phase"] == "walk":
                assert [(r["op"], r["n_eq"], r["S"]) for r in mine] == [("nudge", cfg["approach"]["n_eq"], cfg["approach"]["S"])], mine
        walks = of(got, "walk")
        # from the high probe the park is (sigma+1) g away: no walk while that fits one nudge; from the low probe sigma g away
        want = (len(walks) == 0 if off + G <= MAX_NUDGE else 0 < len(walks) if off <= MAX_NUDGE else len(walks) > len(of(got, "park")))
        assert want, (sigma, off, len(walks))


def test_t05_the_park_reading_enters_no_table(tmp):
    for wn, f in (("sign", W.sign_world(603.5)), ("linear", lin(603.5)), ("steep", lin(611.5, 0.02))):
        for base, cfg in ((W.CFG, SET2), (W.CFG, SET), ({**W.CFG, "ops": W.OFF_OPS}, {**SET, "ops": W.OFF_OPS})):
            v1 = W.drop(tmp, f, base, name="v1", map_name=f"v1{wn}.jsonl", horizon=100000)
            sp = W.drop(tmp, f, cfg, name="sp", map_name=f"sp{wn}.jsonl", horizon=100000)
            a = [(s["pair"]["centre"], s["pair"]["classes"], s["verdict"][0]["kind"], s["verdict"][0]["ticks"]) for s in of(v1, "hold")]
            b = [(s["pair"]["centre"], s["pair"]["classes"], s["verdict"][0]["kind"], s["verdict"][0]["ticks"]) for s in of(sp, "hold")]
            k = min(len(a), len(b))
            assert k >= 8 and a[:k] == b[:k], (wn, cfg["ops"], k, next((i for i in range(k) if a[i] != b[i]), None))


def test_t06_the_safe_side_is_the_dials_declared_ordered_side(tmp):
    minus_world = lambda t, i, n: -lin(603.5)(t, i, n)
    roles = [{"name": "D", "role": "crossing", "ordered_sign": "-"}, {"name": "C", "role": "peak"}]
    cases = (("side", minus_world, {"ordered_side": {"K": "-"}}, "-", +1), ("role", minus_world, {"roles": roles}, "+", -1),
             ("both", lin(603.5), {"roles": roles, "ordered_side": {"K": "-"}}, "-", +1), ("plain", lin(603.5), None, "+", -1))
    for name, f, declared, side, direction in cases:
        got = W.drop(tmp, f, SET2, name=name, map_name=f"{name}.jsonl", horizon=80000, declared=declared)
        assert got.rc == 0, (name, got.err[-200:])
        parks = of(got, "park")
        assert len(parks) >= 5 and all(p["park"]["setpoint"] == p["park"]["centre"] + direction * OFF_HI for p in parks), name
        # the hold pair's own setpoint is signed the same way, on a "-" dial too (the ONE setpoint line, cold audit minor 8)
        assert all(s["pair"]["setpoint"] == s["pair"]["centre"] + direction * OFF_HI for s in of(got, "hold")), name
        # the true ordered side of the dial, from the world: the park is never on it
        assert all((r["tick"] > 603.5) != (side == "+") for r in got.fake.readings if r["tick"] in {p["park"]["setpoint"] for p in parks}), name


def test_t07_feedback_off(tmp):
    off = {**SET2, "ops": W.OFF_OPS}
    got = W.drop(tmp, lin(lambda i: 603.5 + i * 0.0004), off, horizon=80000)
    assert got.rc == 0, got.err[-200:]
    assert all(m["op"] == "scan" for m in got.measured), {m["op"] for m in got.measured}
    assert not of(got, "walk") and not [s for s in got.steps if s["phase"] == "approach"]
    parks, holds = of(got, "park"), of(got, "hold")
    assert len(parks) >= 5 and len({s["pair"]["centre"] for s in holds}) == 1 and len({p["park"]["setpoint"] for p in parks}) == 1
    scans = [m for m in got.measured if m["ticks"] == [[parks[0]["park"]["setpoint"]]]]
    assert len(scans) == len(parks) and all((m["n_eq"], m["S"]) == (off["park"]["n_eq"], off["park"]["S"]) for m in scans)


def test_t08_a_setpoint_off_the_dial_is_a_range_kind(tmp):
    for name, x, side, want in (("low", 30.5, "+", "range-low"), ("high", 1169.5, "-", "range-high")):
        world = W.sign_world(x) if side == "+" else (lambda t, i, n, x=x: -W.sign_world(x)(t, i, n))
        v1 = W.drop(tmp, world, name=f"v1{name}", map_name=f"v1{name}.jsonl", horizon=40000, declared={"ordered_side": {"K": side}})
        sp = W.drop(tmp, world, with_sigma(SET, INT_OUT + 1), name=name, map_name=f"{name}.jsonl", horizon=40000, declared={"ordered_side": {"K": side}})
        assert v1.records[-1]["kind"] == "HORIZON", (name, v1.records[-1])                       # plan 1552's hold fits here
        assert sp.rc == 0 and sp.records[-1]["kind"] == "OFF-DIAL" and sp.steps[-1]["verdict"][0]["kind"] == want, (name, sp.records[-1])
        assert sp.fake.refused == 0, name                                                       # no clamp and no refused call


def test_t09_the_horizon(tmp):
    cut = set()
    for h in (30000, 31000, 32500, 34000, 35100):
        got = W.drop(tmp, lin(603.5), SET2, name=f"h{h}", map_name=f"h{h}.jsonl", horizon=h)
        last = got.steps[-1]
        assert got.rc == 0 and got.records[-1]["kind"] == "HORIZON" and not last["evaluated"], (h, got.records[-1])
        assert last["verdict"][0]["kind"] == "no-reading" and got.fake.refused == 1, h
        cut.add(last["phase"])
    assert {"hold", "park"} <= cut, cut                                  # the five horizons cut a hold pair AND a park reading


# ---------------------------------------------------------------- the reader
def _text(recs):
    return "".join(json.dumps(r) + "\n" for r in recs)


def test_t10_the_reader_reads_a_setpoint_report_and_its_map(tmp):
    HS, NS, RH = _lib()
    for n, cfg in enumerate((SET2, SET, {**SET, "ops": W.OFF_OPS})):
        got = W.drop(tmp, lin(lambda i: 603.5 + i * 0.0004), cfg, map_name=f"m{n}.jsonl", horizon=60000)
        lines = got.out.splitlines(keepends=True)
        for k in range(1, len(lines) + 1):
            assert isinstance(RH.read("".join(lines[:k])), RH.Stream), (cfg["ops"], k)
        st, mp = RH.read(got.out), RH.read_map(got.map)
        assert isinstance(mp, RH.Map) and len(mp.drops) == 1 and RH.check(st, mp.drops[0]) is None, (cfg["ops"], mp)
        assert RH.places(st, "t") == got.entries, cfg["ops"]
        i = next(k for k, r in enumerate(got.records) if r.get("phase") == "park")   # .get: start/outcome records have no phase
        for key, val in (("setpoint", got.records[i]["park"]["setpoint"] + 1), ("centre", got.records[i]["park"]["centre"] - 6),
                         ("n", got.records[i]["park"]["n"] + 1)):
            bad = copy.deepcopy(got.records)
            bad[i]["park"][key] = val
            assert isinstance(RH.read(_text(bad)), NS.Unreadable), key
        for kind, reason in (("stay", None), ("park", "SIG+")):
            bad = copy.deepcopy(got.records)
            bad[i]["verdict"][0]["kind"] = kind
            bad[i]["verdict"][0]["reason"] = reason or bad[i]["verdict"][0]["reason"]
            assert isinstance(RH.read(_text(bad)), NS.Unreadable), kind
        moved = copy.deepcopy(got.records)
        moved[0]["sigma"]["dead_band"]["ticks"] += 1
        assert isinstance(RH.read(_text(moved)), NS.Unreadable), "a start record whose sigma is not its settings'"
    v1 = W.drop(tmp, lin(603.5), name="v1", map_name="v1.jsonl", **SHORT)
    entries = [json.loads(x) for x in v1.map.splitlines()]
    entries[3]["call"]["phase"] = "park"
    assert isinstance(RH.read_map("".join(json.dumps(e) + "\n" for e in entries)), NS.Unreadable), "a plan 1552 map with a park phase"


def test_t11_the_readers_numbers(tmp):
    HS, NS, RH = _lib()
    got = W.drop(tmp, lin(603.5), SET2, horizon=80000)
    st = RH.read(got.out)
    assert RH.sigma(st) == {"g": SIGMA_HI, "ticks": OFF_HI, "value": OFF_HI * 0.3 / 1200, "ticks_per_g": G}, RH.sigma(st)
    se = RH.settle(st)
    assert se["n_eq"] == {"ignite": 450, "approach": 48, "hold": 450, "park": 450} and set(se["mid_move"]) == set(se["n_eq"]), se
    band = RH.deadband(st)
    n = len(of(got, "hold"))
    assert band == {"n": n, "flat": 0, "median": 5.0, "p95": 5.0} or (band["n"] == n and band["flat"] == 0
                                                                   and abs(band["median"] - 5.0) < 1e-9 and abs(band["p95"] - 5.0) < 1e-9), band
    sg = W.drop(tmp, W.sign_world(lambda i: 603.5 + i * 0.004), SET2, name="sg", map_name="sg.jsonl", horizon=80000)   # it outruns the pair
    b2 = RH.deadband(RH.read(sg.out))
    pairs = of(sg, "hold")
    flat = sum(1 for s in pairs if s["pair"]["values"]["D"][0] == s["pair"]["values"]["D"][1])
    assert flat > 0 and b2["n"] == len(pairs) and b2["flat"] == flat, (b2, flat, len(pairs))           # a flat pair is counted, never dropped
    assert flat < len(pairs), (flat, len(pairs))                                                 # the fixture has unflat pairs too
    assert abs(b2["median"] - 2 * 0.01 / (0.6 / 24)) < 1e-9, b2                              # 0.8 ticks: z err over the pair's slope
    v1 = RH.read(W.drop(tmp, lin(603.5), name="v1", map_name="v1.jsonl", **SHORT).out)
    assert RH.settle(v1)["n_eq"] == {"ignite": 450, "approach": 48, "hold": 450}                  # plan 1552's three, unchanged


# ---------------------------------------------------------------- the scorer, the orchestrator
SP_KEYS = {"plan", "offset_K", "needle", "sigma", "sigma_ticks", "g", "dead_band_ticks", "ordered_side", "feedback", "outcome", "park_steps",
           "safe_fraction", "mean_margin_g", "min_margin_g", "rms_set_e_g", "ordered_share", "ordered_depth_max", "ordered_depth_p95",
           "edge_error_p95", "band_holds", "parks"}
PARK_KEYS = {"step", "index", "centre", "setpoint", "actual", "truth_tick", "margin", "cell"}
SP_STATS = ("safe_fraction", "mean_margin_g", "min_margin_g", "rms_set_e_g", "ordered_share", "ordered_depth_max", "ordered_depth_p95",
            "edge_error_p95", "band_holds")


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))]


def test_t12_the_setpoint_score(tmp):
    HS, NS, RH = _lib()
    cfg = HS.ScoreCfg(0.0, 3, "1558")
    got = W.drop(tmp, lin(603.5), SET2, horizon=80000)
    st = RH.read(got.out)
    rows = S._rows(got.fake, lambda i: 603.5)
    sp = HS.setpoint_score(st, rows, cfg)
    assert set(sp) == SP_KEYS and sp["needle"] == SHAPE and sp["sigma_ticks"] == OFF_HI and sp["ordered_side"] == "+", sorted(sp)
    parks = of(got, "park")
    assert sp["park_steps"] == len(parks) and [set(p) for p in sp["parks"]] == [PARK_KEYS] * len(parks)
    want = [603.5 - p["park"]["setpoint"] for p in parks]                                     # safe side is below: margin = truth - setpoint
    assert all(abs(q["margin"] - m) < 1e-6 for q, m in zip(sp["parks"], want)) and all(q["cell"] == "SAFE" for q in sp["parks"])
    assert sp["safe_fraction"] == 1.0 and abs(sp["mean_margin_g"] - sum(want) / len(want) / G) < 1e-6
    assert abs(sp["min_margin_g"] - min(want) / G) < 1e-6
    assert abs(sp["rms_set_e_g"] - (sum((m - OFF_HI) ** 2 for m in want) / len(want)) ** 0.5 / G) < 1e-6
    assert sp["dead_band_ticks"] == DEAD_BAND and abs(sp["edge_error_p95"] - p95([abs(m - OFF_HI) for m in want])) < 1e-6
    assert sp["band_holds"] is (sp["edge_error_p95"] <= DEAD_BAND) and all(q["actual"] == q["setpoint"] for q in sp["parks"])
    for ticks, holds in ((sp["edge_error_p95"], True), (sp["edge_error_p95"] - 0.5, False)):     # the band is CLOSED: equal holds
        st2 = copy.deepcopy(st)
        st2.start["settings"]["dead_band"]["ticks"] = ticks
        assert HS.setpoint_score(st2, rows, cfg)["band_holds"] is holds, (ticks, holds)
    # the park is scored where the dial ACTUALLY was (the truth row's dial runs), never where it was commanded: a park whose
    # window was spent half at tick 610 and half at 622 (both past the crossing, on the ordered side) is scored there
    ws = {tuple(p["park"]["window"][0]): p["park"]["setpoint"] for p in parks}
    lag_rows = copy.deepcopy(rows)
    for row in lag_rows:
        for pt in row["points"]:
            if tuple(pt["window"]) in ws:
                a, b = pt["window"]; t = ws[tuple(pt["window"])]; half = (b - a + 1) // 2
                pt["dial"] = [[pt["dial"][0][0], [610]], [a + half, [622]]]
    lag = HS.setpoint_score(st, lag_rows, cfg)
    for q, p in zip(lag["parks"], parks):
        a, b = p["park"]["window"][0]; t = p["park"]["setpoint"]; half = (b - a + 1) // 2
        act = (half * 610 + (b - a + 1 - half) * 622) / (b - a + 1)
        assert abs(q["actual"] - act) < 1e-9 and abs(q["margin"] - (603.5 - act)) < 1e-9 and q["setpoint"] == t, (q, act)
    assert lag["safe_fraction"] == 0.0 and lag["ordered_share"] > sp["ordered_share"], (lag["safe_fraction"], lag["ordered_share"])
    # the edge error is the 95th percentile, never the worst park: ONE park of the 22 dragged 40 ticks off leaves it where it was
    assert len(parks) >= 21, len(parks)     # a property of THIS fixture (lin(603.5), SET2, horizon 40000: 22 parks), not of the needle:
                                            # with fewer than 21 parks one outlier would move the p95 and the case would test nothing
    one_rows, w0 = copy.deepcopy(rows), tuple(parks[0]["park"]["window"][0])
    for row in one_rows:
        for pt in row["points"]:
            if tuple(pt["window"]) == w0:
                pt["dial"] = [[pt["dial"][0][0], [pt["dial"][0][1][0] + 40]]]
    one = HS.setpoint_score(st, one_rows, cfg)
    errs = [abs(q["margin"] - OFF_HI) for q in one["parks"]]
    assert max(errs) >= 30 and abs(one["edge_error_p95"] - p95(errs)) < 1e-9 and one["edge_error_p95"] < max(errs), (one["edge_error_p95"], max(errs))
    # the probe's exposure in ticks (owner ruling OQ-3: reported, never barred): how far past the true crossing the dial went
    for score, rws in ((sp, rows), (lag, lag_rows)):
        at, tt = HS.actual_ticks(rws), HS.truth_ticks(rws, st.dial, cfg.offset_K)
        deep = [max(0, at[tuple(w)] - tt[tuple(w)]) for r in st.steps if r["phase"] in ("hold", "walk", "park") and r["evaluated"]   # side "+":
                for w in r[{"hold": "pair", "walk": "leg", "park": "park"}[r["phase"]]]["window"]]                           # past = above
        assert score["ordered_depth_max"] == max(deep) and score["ordered_depth_p95"] == p95(deep) and max(deep) > 0, (score["ordered_depth_max"], max(deep))
    assert lag["ordered_depth_max"] >= 610 - 603.5, lag["ordered_depth_max"]       # every lagged park sat at least 6.5 ticks past
    held = [(t, 603.5) for s in got.steps if s["phase"] in ("hold", "walk", "park") and s["evaluated"]
            for t in s[{"hold": "pair", "walk": "leg", "park": "park"}[s["phase"]]]["pos"]]
    assert sp["ordered_share"] == sum(1 for t, x in held if t > x) / len(held), sp["ordered_share"]
    # the null: the same readings scored against the MIRRORED truth (the crossing reflected through the setpoint's far side)
    mirrored = S._rows(got.fake, lambda i: 603.5 - 2 * OFF_HI - G)
    null = HS.setpoint_score(st, mirrored, cfg)
    assert null["safe_fraction"] == 0.0 and all(q["cell"] == "UNSAFE" for q in null["parks"]) and null["mean_margin_g"] < 0, null["safe_fraction"]
    # a dial whose ordered side is "-": the safe side is ABOVE, the margin is setpoint - truth, read from the declaration
    mg = W.drop(tmp, lambda t, i, n: -lin(603.5)(t, i, n), SET2, name="mg", map_name="mg.jsonl", horizon=80000, declared={"ordered_side": {"K": "-"}})
    smg = HS.setpoint_score(RH.read(mg.out), S._rows(mg.fake, lambda i: 603.5), cfg)
    wmg = [p["park"]["setpoint"] - 603.5 for p in of(mg, "park")]
    assert smg["ordered_side"] == "-" and smg["safe_fraction"] == 1.0 and len(wmg) >= 5, (smg["ordered_side"], smg["safe_fraction"])
    assert all(abs(q["margin"] - m) < 1e-6 for q, m in zip(smg["parks"], wmg)) and all(m > 0 for m in wmg)
    hmg = [t for s in mg.steps if s["phase"] in ("hold", "walk", "park") and s["evaluated"] for t in s[{"hold": "pair", "walk": "leg", "park": "park"}[s["phase"]]]["pos"]]
    assert smg["ordered_share"] == sum(1 for t in hmg if t < 603.5) / len(hmg), smg["ordered_share"]
    # score() of a setpoint stream: plan 1552's key set, hold steps only, the walks and parks counted in no stat
    sc = HS.score(st, rows, cfg)
    v1 = W.drop(tmp, lin(603.5), name="v1", map_name="v1.jsonl", horizon=80000)
    sv1 = HS.score(RH.read(v1.out), S._rows(v1.fake, lambda i: 603.5), cfg)
    assert set(sc) == set(sv1) and sc["hold_steps"] == len(of(got, "hold")) and sc["segments"] == 1, (sorted(set(sc) ^ set(sv1)), sc["segments"])
    nos = HS.setpoint_score(RH.read(v1.out), S._rows(v1.fake, lambda i: 603.5), cfg)
    assert nos["park_steps"] == 0 and nos["parks"] == [] and all(nos[k] == HS.NO_STEPS for k in SP_STATS)
    try:
        HS.setpoint_score(st, rows[:-3], cfg)
        raise AssertionError("scored a reading with no truth row")
    except KeyError:
        pass


def test_t13_the_orchestrator(tmp):
    HS, NS, RH = _lib()
    short = setpoint_cfg(sigma=SIGMA_HI, n_eq=49, S=89, park={"S": 89, "n_eq": 49}, ignite={**W.CFG["ignite"], "n_eq": 0}, approach={"S": 40, "n_eq": 0})
    res, run = S._run(tmp / "a", needle=short)
    assert res.returncode == 0 and run is not None, (res.returncode, res.stderr[-600:])
    have = {p.name for p in run.iterdir()}
    assert {"report.jsonl", "map.jsonl", "truth.json", "score.json", "map-truth.json", "setpoint.json"} <= have, sorted(have)
    st, rows = RH.read((run / "report.jsonl").read_text()), json.loads((run / "truth.json").read_text())["rows"]
    cfg = HS.ScoreCfg(-0.0018, 3, "1552")
    assert json.loads((run / "score.json").read_text()) == {**HS.score(st, rows, cfg), "run_id": run.name}
    assert json.loads((run / "setpoint.json").read_text()) == {**HS.setpoint_score(st, rows, cfg), "noise_band": RH.deadband(st), "run_id": run.name}
    res1, run1 = S._run(tmp / "b")
    assert res1.returncode == 0 and "setpoint.json" not in {p.name for p in run1.iterdir()}, "a plan 1552 run wrote setpoint.json"
    for n, nd in enumerate(({**short, "sigma": 0.25}, {**short, "sigma": 0}, setpoint_cfg(**{**unband(short), "sigma": 0.75}, ticks=9))):
        res2, run2 = S._run(tmp / f"r{n}", needle=nd)
        sigma = nd["sigma"]
        assert res2.returncode == 2 and "RefusedToStart field=sigma parse=B" in res2.stderr, (sigma, res2.returncode, res2.stderr[-300:])
        assert {p.name for p in run2.iterdir()} == {"refused.json"}, sigma
    res3, run3 = S._run(tmp / "mid", needle=setpoint_cfg(**{**unband(short), "n_eq": 0, "S": 40}))      # a mid-move setpoint pair: refused at the door (the lag is declared there)
    assert res3.returncode == 2 and json.loads((run3 / "refused.json").read_text()) == {"kind": "RefusedToStart", "field": "n_eq", "parse": "A"}, res3.stderr[-300:]
    assert not {"report.jsonl", "map.jsonl", "score.json", "setpoint.json"} & {p.name for p in run3.iterdir()}


# ---------------------------------------------------------------- sigma = 0, the tables, the shipped files
def _v1_worlds():
    return {"sign": (W.sign_world(603.5), {"horizon": 60000}),
            "drift": (lin(lambda i: 603.5 + i * 0.0004), {"horizon": 120000}),
            "minus": (lambda t, i, n: -lin(lambda i: 603.5 - i * 0.0004)(t, i, n), {"horizon": 120000, "declared": {"ordered_side": {"K": "-"}}})}


def test_t14_sigma_zero_is_plan_1552_byte_for_byte(tmp):
    for cn, cfg in (("settled", W.CFG), ("mid", W.MID), ("off", {**W.CFG, "ops": W.OFF_OPS})):
        for wn, (f, kw) in _v1_worlds().items():
            got = W.drop(tmp, f, cfg, name="t", map_name=f"{cn}{wn}.jsonl", **kw)
            sha = hashlib.sha256((got.out + "\n#MAP\n" + got.map).encode()).hexdigest()
            assert got.rc == 0 and sha == V1_PINS[(cn, wn)], (cn, wn, got.rc, sha)


def test_t15_the_tables_are_total_and_reduce_to_plan_1552():
    from navigator import holdtab as HT
    assert HT.SETPOINT == SHAPE and HT.SHAPES == ("hold-pair-v1", SHAPE)
    assert set(HT.SAFE) == {"+", "-"} and set(HT.PHASES) == set(HT.SHAPES) == set(HT.PARKS)
    assert HT.PAYLOAD == {"ignite": "grid", "approach": "leg", "hold": "pair"}
    assert HT.PHASE_PAYLOAD == {**HT.PAYLOAD, "walk": "leg", "park": "park"} and HT.PARKS == {"hold-pair-v1": (), SHAPE: ("park",)}
    assert HT.reach(12, 0, "+") == HT.reach(12, 0, "-") == (12, 12) and HT.reach(12, 24, "+") == (24, 12) and HT.reach(12, 24, "-") == (12, 24)
    assert HT.reach(12, 9, "+") == (12, 12)
    for c in range(-40, 1241):
        for kind in ("stay", "raise", "lower", "no-signal", "bracketed"):
            assert HT.placed_at(kind, c, 12, 12, 1200) == HT.placed(kind, c, 12, 1200), (kind, c)
    classes = ("SIG-", "UNRES", "SIG+")
    for side in ("+", "-"):
        for sign in ("+", "-"):
            view = HT.ORIENT[(side, sign)]
            for a in classes:
                for b in classes:
                    for mode in ("ON", "OFF"):
                        for c in (5, 12, 13, 600, 1187, 1188, 1195):
                            assert HT.hold_kind_at([a, b], view, mode, c, 6, 12, 12, 1200) == HT.hold_kind([a, b], view, mode, c, 6, 12, 1200)
    for br in ([], [100, 120], [0, 20], [1180, 1200]):
        assert HT.ignite_kind_at(br, 12, 12, 1200) == HT.ignite_kind(br, 12, 1200)
    for bad in ("0", "?", None):
        for fn in (lambda: HT.SAFE[bad], lambda: HT.reach(12, 24, bad), lambda: HT.setpoint(600, 24, bad)):
            try:
                fn()
                raise AssertionError(f"a side {bad!r} has a cell")
            except KeyError:
                pass
    assert HT.offset(2, 12) == 24 and HT.offset(1.5, 12) == 18 and HT.setpoint(600, 24, "+") == 576 and HT.setpoint(600, 24, "-") == 624


def test_t16_the_shipped_setpoint_files_and_plan_1552s_files():
    # the band's input is plan 1561's table shape, read as written: every setpoint row measured on every seed it names
    assert BAND_TABLE["schema"] == "compass-drift-band/1" and BAND_ROWS, BAND_TABLE.get("schema")
    keys = {"law", "direction", "rung", "needle", "sigma", "seeds", "p95", "p95_max", "p95_median", "missing", "within_declared_band"}
    assert all(set(r) == keys for r in BAND_TABLE["rows"]), [sorted(set(r) ^ keys) for r in BAND_TABLE["rows"]]
    assert all(r["missing"] == [] and len(r["p95"]) == len(r["seeds"]) > 0 and r["p95_max"] == max(r["p95"]) for r in BAND_ROWS), BAND_ROWS
    assert not GAPS, f"band runs with no evidence (no lock class, no number): {GAPS[:6]}"
    assert PROVEN[0] <= DEAD_BAND <= PROVEN[1], f"DEAD_BAND {DEAD_BAND} is outside {PROVEN}, where the cases were proven: re-derive them (a finding)"
    # completeness from the sigma = 0 rows (1561's held-count prefix), never from the rows present: every rung measured at sigma 0
    # in the band's laws is measured at every sigma the band names
    cells = {(r["law"], r["direction"], r["rung"]) for r in BAND_TABLE["rows"] if r["sigma"] == 0 and r["law"] in BAND_LAWS}
    have = {(r["law"], r["direction"], r["rung"], r["sigma"]) for r in BAND_ROWS}
    assert not [(*c, x) for c in sorted(cells) for x in MEASURED if (*c, x) not in have], "a rung measured at sigma 0 lacks a sigma > 0 row"
    # the shipped sigmas were band-measured (B2): if the band moved them, band-run is repeated with the new pair (plan, order step 3b)
    assert SIGMA_LO in ADMISSIBLE and SIGMA_HI in ADMISSIBLE, f"band-run must measure sigma {SIGMA_LO} and {SIGMA_HI} (admissible {ADMISSIBLE})"
    # the band is keyed by geometry: the table names the geometry it was measured at, and a shipped file has exactly that one
    # (an unmeasured geometry has no row; per-use-case precision adds rows, never a schema break)
    for name in ("setpoint-settled", "setpoint-settled-2"):
        c = tomllib.loads((ROOT / "navigator" / f"{name}.toml").read_text())
        assert {k: c[k] for k in BIND} == BAND_TABLE["geometry"], (name, BAND_TABLE["geometry"])
        assert c["dead_band"]["admissible"] == ADMISSIBLE, (name, c["dead_band"]["admissible"], ADMISSIBLE)
        # the type SELF-DOCUMENTS (owner ruling 2026-11-17): its description is complete, and every number in it is the members'
        ab = c["dead_band"]["about"]
        assert set(ab) == set(ABOUT) and all(ab[k] not in ("", [], {}) for k in ABOUT if k != "members"), (name, list(ab))
        assert ab["conversion"]["g_ticks"] == c["g"] and ab["band"]["ticks"] == c["dead_band"]["ticks"] == DEAD_BAND, (name, ab["band"])
        assert ab["band"]["p95_max"] == max(HELD_P95) and ab["band"]["bound_to"] == list(BIND), (name, ab["band"])
        assert ab["provenance"] == {"sha256": BAND_SHA}, (name, ab["provenance"])
        assert ab["cost"]["max_nudge"] == MAX_NUDGE and ab["cost"]["skip"] == c["skip"] and ab["cost"]["approach"] == c["approach"], name
        assert [m["sigma"] for m in ab["members"]] == ADMISSIBLE, (name, ab["members"])
        for m in ab["members"]:
            assert Fraction(repr(m["sigma"])) * c["g"] == m["ticks"] > DEAD_BAND, (name, m)          # ticks = sigma * g, outside the band
            assert m["cycle"] == {"plus": cycle_upper(c, m["sigma"], "+", MAX_NUDGE), "minus": cycle_upper(c, m["sigma"], "-", MAX_NUDGE)}, (name, m)
            assert m["domain"] == DOMAIN[m["sigma"]] and m["out"] == OUT[m["sigma"]], (name, m["sigma"], m["out"], OUT)   # Finding D, stated
            assert m["label"] == label(m, ab), (name, m["label"])                                     # derived, never written
    # ramp's first rung (table order) is in the setpoint needle's domain at every measured sigma; if not, that is a finding
    first = next(r["rung"] for r in BAND_ROWS if r["law"] == "ramp")
    assert not [o for o in OUT_OF_DOMAIN if o[0] == "ramp" and o[2] == first], f"ramp {first} is out of the setpoint needle's domain: a finding"
    names = sorted(p.name for p in (ROOT / "navigator").glob("setpoint*.toml"))
    assert names == ["setpoint-settled-2.toml", "setpoint-settled.toml"], names        # no mid-move setpoint file: the door refuses one
    for name, want in (("setpoint-settled", SET), ("setpoint-settled-2", SET2)):
        got = tomllib.loads((ROOT / "navigator" / f"{name}.toml").read_text())
        assert got == want, (name, sorted(set(got) ^ set(want)))
    for rel, sha in FROZEN_1552.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, f"{rel} was edited: plan 1558 adds files and edits none of plan 1552's contract"



# t17: the lines of plan 1552's base navigator/hold.py (45ac04ef...) that name the lag outside HT.settled / HT.commanded, stripped
BASE_LAG_LINES = {
    'DECLARED = {"op", "wire", "dials", "pos", "fixed", "ordered_side", "roles", "index", "horizon", "lag", "tau", "k", "L",',
    'and _int(0)(pos) and pos <= dl["T"] and all(_int(0)(d[k]) for k in ("index", "lag", "horizon", "k"))',
    'self.max_nudge, self.lag, self.horizon, self.skip = dl["max_nudge"], d["lag"], d["horizon"], cfg["skip"]',
    'self.cmd, self.since = self.pos, self.index - self.lag',
    'clock = {k: d[k] for k in ("index_unit", "index_kind", "clock", "lag", "k", "tau")}',
}


def _strip_calls(line, names=("HT.settled(", "HT.commanded(")):
    """the line with every call to the named holdtab functions removed, parentheses balanced."""
    for nm in names:
        while nm in line:
            i = line.index(nm); j, depth = i + len(nm), 1
            while depth:
                depth += {"(": 1, ")": -1}.get(line[j], 0); j += 1
            line = line[:i] + "CALL" + line[j:]
    return line


def test_t17_every_lag_rule_goes_through_holdtab():
    # cross-plan review finding 4, cold audit M4: plan 1565 Phase 4 changes the clock rule in holdtab ONLY; an inline copy here would
    # keep the old rule silently. Every line naming the lag, its holdtab calls removed, is one plan 1552's base already had.
    import io, tokenize
    text = (ROOT / "navigator" / "hold.py").read_text()
    src = text.splitlines()
    for t in tokenize.generate_tokens(io.StringIO(text).readline):      # code only: a comment is cut off its line
        if t.type == tokenize.COMMENT:
            src[t.start[0] - 1] = src[t.start[0] - 1][:t.start[1]]
    new = [ln.strip() for ln in src if "lag" in _strip_calls(ln)]
    assert set(new) <= BASE_LAG_LINES, sorted(set(new) - BASE_LAG_LINES)


if __name__ == "__main__":
    import tempfile
    _tmp = [test_t01_setpoint_settings_outside_their_domain_are_refused_before_the_wire, test_t02_the_door_a_hold_that_cannot_fit_on_the_dial,
            test_t03_the_start_record_and_the_map_head, test_t04_the_park_cycle_feedback_on, test_t05_the_park_reading_enters_no_table,
            test_t06_the_safe_side_is_the_dials_declared_ordered_side, test_t07_feedback_off, test_t08_a_setpoint_off_the_dial_is_a_range_kind,
            test_t09_the_horizon, test_t10_the_reader_reads_a_setpoint_report_and_its_map, test_t11_the_readers_numbers,
            test_t12_the_setpoint_score, test_t13_the_orchestrator, test_t14_sigma_zero_is_plan_1552_byte_for_byte]
    _plain = [test_t15_the_tables_are_total_and_reduce_to_plan_1552, test_t16_the_shipped_setpoint_files_and_plan_1552s_files,
              test_t17_every_lag_rule_goes_through_holdtab]
    only = set(sys.argv[1:])
    _fail = _ran = 0
    for _t in _tmp + _plain:
        if only and not any(o in _t.__name__ for o in only):
            continue
        _ran += 1
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)) if _t in _tmp else _t()
                print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1
                print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    print(f"{_ran - _fail}/{_ran} passed")
    sys.exit(1 if _fail else 0)
