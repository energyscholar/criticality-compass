"""Plan 1558 (phase 4): the band writer (contract/SCHEMA-1558.md sections 2.2, 2.3, 4.5). Pure: it opens nothing and prints nothing.
ONE band row for one table of plan 1561's `compass-drift-band/1` shape: the dead band the setpoint needle is measured at, the type
of its setpoint (`admissible`) and that type's description (`about`), all generated from the table's rows and locks, never typed.
The band's domain is a TOTAL table over each run's lock: a HELD run is band evidence, a run that broke the needle's hold is out of
its domain (named, never counted), a run with no evidence is a gap and the table is refused."""
import hashlib
import json
import math

from environment import drift_score as DS
from navigator import holdtab as HT

LAWS = ("ramp", "ramp-reversed", "sine", "walk")     # the band's domain: step drift is report-only
LOCK_CLASS = {"HELD": "band", "RECOVERED": "out", "LOST": "out", "LEFT-RANGE": "out",
              **{k: "gap" for k in ("CUT-SHORT", "REFUSED", "FAILED", "MISSING", "MISMATCH")}}     # any other lock is a KeyError
MEANING = ("the setpoint: an UNSIGNED offset from the critical crossing; the needle parks the dial that far on the dial's "
           "declared SAFE side (away from its ordered_side) after every hold pair")
KNOB = "(hi - lo) / T of the System's declared dial (the System's, read at run time: the reader's sigma().value)"
PROMISE = ("per-run p95 of |park - edge - sigma*g| <= ticks on every HELD run of the laws, at the geometry bound_to names "
           "(this row's own cells); a member is band-measured and sigma*g is strictly outside the band")
COST_UNIT = "sweeps per cycle, an upper bound (SCHEMA-1558 4.4): the precision-lag trade"
cell = lambda r: f"{r['law']}/{r['direction']}/{r['rung']}"
whole = lambda x: int(x) if x == int(x) else x


def _runs(table, rows):
    """(row, seed, class, p95) for every run of every row; a band-class run with no finite p95 is a gap."""
    out = []
    for r in rows:
        num = dict(zip(r["seeds"], r["p95"]))
        for s in sorted([*r["seeds"], *r["missing"]]):
            c = LOCK_CLASS[table["locks"][f"{r['law']}--{r['rung']}--{r['needle']}--s{s}"]]
            ok = type(num.get(s)) in (int, float) and math.isfinite(num[s])
            out.append((r, s, "gap" if c == "band" and not ok else c, num[s] if ok else None))
    return out


def _admits(x, g, ticks):
    n, d = HT.sigma_ticks(x, g)
    return n % d == 0 and n // d > ticks


def _cycle(geometry, cost_at, sigma, side):
    """the setpoint cycle row (drift_score.CYCLE) at the band's geometry and the apparatus the cost is computed at."""
    start = {"needle": HT.SETPOINT, "dials": ["K"], "belief": {"ordered_side": {"declared": {"K": side}}},
             "declared_other": {"dials": [{"max_nudge": cost_at["max_nudge"]}]},
             "settings": {**geometry, "skip": cost_at["skip"], "approach": cost_at["approach"], "sigma": sigma}}
    return DS.cycle(start)


def _label(m, about):
    return (f"sigma {m['sigma']} g = {m['ticks']} ticks from the crossing, on the safe side; band {about['band']['ticks']} ticks; "
            f"cycle <= {m['cycle']['plus']} sweeps on a + dial, {m['cycle']['minus']} on a - dial; "
            f"held on {len(m['domain'])} cells, out of its domain on: {', '.join(m['out']) or 'none'}")


def band(table, cost_at):
    """table, cost_at {approach, skip, max_nudge} -> {geometry, ticks, admissible, about, domain, out, gaps}; ValueError on a gap or no evidence."""
    geometry = table["geometry"]
    rows = [r for r in table["rows"] if r["sigma"] > 0 and r["law"] in LAWS]
    runs = _runs(table, rows)
    gaps = [[r["law"], r["rung"], r["sigma"], s] for r, s, c, _ in runs if c == "gap"]
    if gaps:
        raise ValueError(f"the table has runs with no evidence (law, rung, sigma, seed): {gaps}")
    sigmas = sorted({r["sigma"] for r in rows})
    domain = {x: [cell(r) for r in rows if r["sigma"] == x and {c for q, _, c, _ in runs if q is r} == {"band"}] for x in sigmas}
    out = {x: [cell(r) for r in rows if r["sigma"] == x and "out" in {c for q, _, c, _ in runs if q is r}] for x in sigmas}
    held = [p for r, _, _, p in runs if cell(r) in domain[r["sigma"]]]
    if not held:
        raise ValueError("no HELD sigma > 0 run in the band's laws: the band has no domain")
    ticks = math.ceil(max(held))
    members = [whole(x) for x in sigmas if _admits(x, geometry["g"], ticks)]
    about = {"meaning": MEANING, "units": "sigma, in pair half-widths g",
             "conversion": {"ticks": "sigma * g", "g_ticks": geometry["g"], "knob_per_tick": KNOB},
             "band": {"ticks": ticks, "p95_max": max(held), "laws": list(LAWS), "bound_to": list(HT.BAND_GEOMETRY), "promise": PROMISE},
             "cost": {"unit": COST_UNIT, "max_nudge": cost_at["max_nudge"], "skip": cost_at["skip"], "approach": dict(cost_at["approach"])},
             "provenance": {"sha256": hashlib.sha256((json.dumps(table, indent=1, sort_keys=True) + "\n").encode()).hexdigest()},
             "members": []}
    for x in members:
        m = {"sigma": x, "ticks": HT.offset(x, geometry["g"]),
             "cycle": {"plus": _cycle(geometry, cost_at, x, "+"), "minus": _cycle(geometry, cost_at, x, "-")},
             "domain": domain[x], "out": out[x]}
        about["members"].append({**m, "label": _label(m, about)})
    return {"geometry": geometry, "ticks": ticks, "admissible": members, "about": about,
            "domain": [[r["law"], r["direction"], r["rung"], r["sigma"]] for r in rows if cell(r) in domain[r["sigma"]]],
            "out": [[r["law"], r["rung"], r["sigma"], s] for r, s, c, _ in runs if c == "out"], "gaps": gaps}
