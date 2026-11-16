"""Plan 1533: the needle `recover-adaptive-v1`. Its numbers are `recover-adaptive-v0`'s (the same grid, the same narrowing, the
same floats); what is new is the report: a stream of typed records, one JSON object per line, each printed and flushed the
moment it is known. The verdict of a step is the total table of navigator.steer over the two end readings of its grid; the
outcome is a fold of the step kinds. A step that is not evaluated is terminal. It opens no file but its own config.
Entry: python -m navigator.recover2 --needle recover2.toml --port P
Exit: 0 = a stream was printed; 2 = RefusedToStart (one stderr line, empty stdout); 1 = Unreachable (one stderr line, empty stdout)."""
import argparse
import json
import sys
import tomllib

from navigator import needle as N
from navigator import reader as R
from navigator import recover as RC
from navigator import report2 as P
from navigator import steer as ST
from navigator.estimate import narrow

STRUCTURE = ST.NEEDLE_V1
OPS = (ST.DECLARE, ST.MEASURE)
DIALS = ()


def parse_cfg(raw):
    """a parsed toml table -> RecoverConfig | Malformed. The v0 parser decides every key but the structure name."""
    if not isinstance(raw, dict):
        return RC.parse_recover_cfg(raw)
    if raw.get("needle_structure") != STRUCTURE:
        return R.Malformed("needle_structure", "unknown structure")
    return RC.parse_recover_cfg({**raw, "needle_structure": RC.STRUCTURE})


def load_cfg(path):
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return R.Malformed("needle", str(e))
    return parse_cfg(raw)


def emit(rec):
    print(json.dumps(rec), flush=True)


def run_steps(w, cfg, nlev, side, put):
    """-> (scans, last, kinds). Each step is handed to `put` before the next measure is asked; a step that is not evaluated is the last."""
    lo, hi = cfg.bracket
    exp, scans, kinds, last = 0, [], [], None
    for r in range(1, cfg.N + 1):
        grid = RC.grid_of(lo, hi, cfg.m)
        exp += cfg.m * (cfg.n_eq + cfg.S * cfg.skip)  # always, evaluated or not
        j = R.judge(w.ask({"op": ST.MEASURE, "Ks": grid, "n_eq": cfg.n_eq, "S": cfg.S, "skip": cfg.skip}), "moments", exp)
        mom = RC._moments(j.reply.fields, cfg.m, nlev) if isinstance(j, R.Evaluated) else None
        if mom is None:
            scan = {"round": r, "grid": grid, "C": None, "C_err": None, "Gs": None, "Gs_err": None, "D": None, "A": None,
                    "B": None, "lo": lo, "hi": hi, "index": exp, "evaluated": False}
            verdict = ST.not_evaluated()
        else:
            C, C_err, Gs, Gs_err = mom
            n = narrow(grid, C, C_err, Gs, Gs_err, cfg.z)
            lo, hi = n.lo, n.hi
            last = (grid, n)
            D = [g[1] - g[0] for g in Gs]
            scan = {"round": r, "grid": grid, "C": C, "C_err": C_err, "Gs": Gs, "Gs_err": Gs_err, "D": D, "A": list(n.A),
                    "B": list(n.B), "lo": lo, "hi": hi, "index": exp, "evaluated": True}
            verdict = ST.scan_verdict(*ST.end_classes(D, Gs_err, cfg.z), side)
        scans.append(scan)
        kinds.append(verdict[0])
        put(P.step(scan, verdict))
        if mom is None:
            break
    return scans, last, kinds


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--needle", required=True)
    ap.add_argument("--port", required=True, type=int)
    a = ap.parse_args(argv)
    cfg = load_cfg(a.needle)
    if isinstance(cfg, R.Malformed):
        return RC.refused(cfg.field, "B")
    try:
        w = N._Wire("127.0.0.1", a.port)
    except OSError as e:
        print(f"Unreachable 127.0.0.1:{a.port} ({type(e).__name__})", file=sys.stderr)
        return 1
    try:
        parsed = w.ask({"op": ST.DECLARE})
        decl = R.parse_declared(parsed.fields) if isinstance(parsed, R.Reply) else R.Malformed("declared", "no declaration")
        if isinstance(decl, R.Malformed):
            return RC.refused(decl.field, "A")
        nlev = decl.raw.get("nlev")
        if isinstance(nlev, bool) or not isinstance(nlev, int) or nlev < 2:
            return RC.refused("nlev", "A")
        if decl.ordered_side not in ST.ORDERED_SIDES:
            return RC.refused("ordered_side", "A")
        knobs_lo, knobs_hi = decl.knobs_K
        if not knobs_lo <= cfg.bracket[0] < cfg.bracket[1] <= knobs_hi:
            return RC.refused("bracket", "A")
        emit(P.start(STRUCTURE, cfg, OPS, DIALS, decl.raw))
        floor = N.refuses_at_floor(cfg.n_eq, decl.k, decl.tau)
        scans, last, kinds = ([], None, []) if floor else run_steps(w, cfg, nlev, decl.ordered_side, emit)
        kind, reason = ST.outcome(kinds)
        located = RC.report(scans, last) if kind == ST.LOCATED else {}
        emit(P.outcome(kind, reason, located, len(scans)))
    finally:
        w.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
