"""Plan 1525: the needle `recover-adaptive-v0`, the first closed loop. It is told no critical coupling. Each round it asks the
wire for moments on an m-point grid of its own bracket, narrows the bracket from what it was told (navigator.estimate.narrow),
and asks again. It opens no file but its own config, writes nothing, has no clock, and prints ONE JSON line.
Entry: python -m navigator.recover --needle recover.toml --port P
Exit: 0 = a report was printed (Located or REFUSE); 2 = RefusedToStart (one stderr line); 1 = Unreachable (one stderr line)."""
import argparse
import json
import math
import sys
import tomllib
from dataclasses import dataclass

from navigator import needle as N
from navigator import reader as R
from navigator.estimate import narrow

STRUCTURE = "recover-adaptive-v0"
KEYS = ("needle_structure", "bracket", "m", "N", "n_eq", "S", "skip", "z")


@dataclass(frozen=True)
class RecoverConfig:
    bracket: tuple
    m: int
    N: int
    n_eq: int
    S: int
    skip: int
    z: float


def _float(d, f, pred=lambda x: True, what="float"):
    v = d.get(f)
    return v if isinstance(v, float) and math.isfinite(v) and pred(v) else R.Malformed(f, what)


def parse_recover_cfg(raw):
    """a parsed toml table -> RecoverConfig | Malformed. Strict: exactly these keys, exactly these types."""
    if not isinstance(raw, dict):
        return R.Malformed("needle", "table required")
    extra = sorted(set(raw) - set(KEYS))
    if extra:
        return R.Malformed(extra[0], "unknown key")
    struct = R._str(raw, "needle_structure")
    if isinstance(struct, str) and struct != STRUCTURE:
        struct = R.Malformed("needle_structure", "unknown structure")
    br = raw.get("bracket")
    if isinstance(br, list) and len(br) == 2 and all(isinstance(x, float) and math.isfinite(x) for x in br) and br[0] < br[1]:
        bracket = (br[0], br[1])
    else:
        bracket = R.Malformed("bracket", "[lo, hi] floats with lo < hi")
    m, Nr, n_eq, S, skip = (R._int(raw, "m", 5), R._int(raw, "N", 1), R._int(raw, "n_eq", 1), R._int(raw, "S", 40),
                            R._int(raw, "skip", 1))
    z = _float(raw, "z", lambda x: x > 0, "float>0")
    bad = R._first_bad([struct, bracket, m, Nr, n_eq, S, skip, z])
    return bad if bad else RecoverConfig(bracket, m, Nr, n_eq, S, skip, z)


def load_cfg(path):
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return R.Malformed("needle", str(e))
    return parse_recover_cfg(raw)


def _floats(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, float) and math.isfinite(x) for x in v)


def _moments(fields, m, nlev):
    """a `moments` reply body -> (C, C_err, Gs, Gs_err) | None (not evaluated). Total: any other shape is None."""
    C, C_err, Gs, Gs_err = (fields.get(k) for k in ("C", "C_err", "Gs", "Gs_err"))
    grids_ok = all(isinstance(g, list) and len(g) == m and all(_floats(row, nlev) for row in g) for g in (Gs, Gs_err))
    return (C, C_err, Gs, Gs_err) if _floats(C, m) and _floats(C_err, m) and grids_ok else None


def grid_of(lo, hi, m):
    return [lo] + [lo + i * (hi - lo) / (m - 1) for i in range(1, m - 1)] + [hi]


def run_rounds(w, cfg, decl, nlev):
    lo, hi = cfg.bracket
    exp, rounds, last = 0, [], None
    for r in range(1, cfg.N + 1):  # all N rounds, never an early stop
        grid = grid_of(lo, hi, cfg.m)
        exp += cfg.m * (cfg.n_eq + cfg.S * cfg.skip)  # always, evaluated or not
        j = R.judge(w.ask({"op": "measure", "Ks": grid, "n_eq": cfg.n_eq, "S": cfg.S, "skip": cfg.skip}), "moments", exp)
        mom = _moments(j.reply.fields, cfg.m, nlev) if isinstance(j, R.Evaluated) else None
        if mom is None:
            rounds.append({"round": r, "grid": grid, "C": None, "C_err": None, "Gs": None, "Gs_err": None, "D": None,
                           "A": None, "B": None, "lo": lo, "hi": hi, "index": exp, "evaluated": False})
            continue
        C, C_err, Gs, Gs_err = mom
        n = narrow(grid, C, C_err, Gs, Gs_err, cfg.z)
        lo, hi = n.lo, n.hi
        last = (grid, n)
        rounds.append({"round": r, "grid": grid, "C": C, "C_err": C_err, "Gs": Gs, "Gs_err": Gs_err,
                       "D": [g[1] - g[0] for g in Gs], "A": list(n.A), "B": list(n.B), "lo": lo, "hi": hi, "index": exp,
                       "evaluated": True})
    return rounds, last


def report(rounds, last):
    """Located iff every round was evaluated; otherwise REFUSE(budget). The final round's A and B give the two hulls."""
    if not all(x["evaluated"] for x in rounds):
        return {"kind": "REFUSE", "reason": "budget", "bracket": None, "A_hull": None, "B_hull": None, "agree": None,
                "rounds": rounds}
    grid, n = last
    a_hull = [grid[min(n.A)], grid[max(n.A)]]
    b_hull = [grid[min(n.B)], grid[max(n.B)]] if n.B else None
    agree = bool(b_hull) and a_hull[0] <= b_hull[1] and b_hull[0] <= a_hull[1]
    return {"kind": "Located", "reason": None, "bracket": [rounds[-1]["lo"], rounds[-1]["hi"]], "A_hull": a_hull,
            "B_hull": b_hull, "agree": agree, "rounds": rounds}


def floor_report():
    return {"kind": "REFUSE", "reason": "floor", "bracket": None, "A_hull": None, "B_hull": None, "agree": None, "rounds": []}


def refused(field, parse):
    print(f"RefusedToStart field={field} parse={parse}", file=sys.stderr)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--needle", required=True)
    ap.add_argument("--port", required=True, type=int)
    a = ap.parse_args(argv)
    cfg = load_cfg(a.needle)
    if isinstance(cfg, R.Malformed):
        return refused(cfg.field, "B")
    try:
        w = N._Wire("127.0.0.1", a.port)
    except OSError as e:
        print(f"Unreachable 127.0.0.1:{a.port} ({type(e).__name__})", file=sys.stderr)
        return 1
    try:
        parsed = w.ask({"op": "declare"})
        decl = R.parse_declared(parsed.fields) if isinstance(parsed, R.Reply) else R.Malformed("declared", "no declaration")
        if isinstance(decl, R.Malformed):
            return refused(decl.field, "A")
        nlev = decl.raw.get("nlev")
        if isinstance(nlev, bool) or not isinstance(nlev, int) or nlev < 2:
            return refused("nlev", "A")
        knobs_lo, knobs_hi = decl.knobs_K
        if not knobs_lo <= cfg.bracket[0] < cfg.bracket[1] <= knobs_hi:
            return refused("bracket", "A")
        if N.refuses_at_floor(cfg.n_eq, decl.k, decl.tau):
            out = floor_report()
        else:
            out = report(*run_rounds(w, cfg, decl, nlev))
    finally:
        w.close()
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
