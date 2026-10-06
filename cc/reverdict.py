"""reverdict.py - a stored result under another table set, from its stored sign cells alone (no data, no instrument).
It lives apart from score.py so the measurement key (schema.measure_hash) can follow `detect.run` into it without following score,
family and view (plan 0876 B). Plumbing."""
import tomllib
from pathlib import Path
import schema
import detect

ROOT = Path(__file__).resolve().parent.parent


def cells_of(res, pt):
    """The sign cells of one point as `<instrument>.<column>` -> cell (a list per size for a point-size column)."""
    return {**{f"declared.{k}": v for k, v in res.get("declared", {}).items()},
            **{f"{r['instrument']}.{r['column']}": [q["cell"] for q in r["per_size"]] if r["per_size"] else r["cell"]
               for r in res["readings"] if r["unit"]["point"] == pt},
            **{f"{r['instrument']}.{r['column']}@door": [q["door"] for q in r["per_size"]]   # plan 0874: the door value each pair read on, beside its cell
               for r in res["readings"] if r["unit"]["point"] == pt and r["per_size"] and "door" in r["per_size"][0]}}


def membership_of(root, name, declared):
    """What a set's membership.toml says that an input could have read: the rules of the instruments the input
    declares, and anything that is not a rule at all. A rule for an instrument the input does not declare moves
    nothing it ran, so it is not part of what the input read."""
    f = Path(root) / "tables" / name / "membership.toml"
    d = tomllib.loads(f.read_text()) if f.is_file() else {}
    return {k: v for k, v in d.items() if k not in ("schema", "kind") and (not isinstance(v, dict) or k in declared)}


def signature_sources(root, name):
    """{signature column: the instruments it is derived from} of a table set (plan 0877)."""
    d = schema.load(Path(root) / "tables" / name / "codes.toml", root)[0] or {"columns": {"signature": {}}}
    cols = schema.code_cols(d)
    return {n: {x.partition(".")[0] for x in detect.sources(n, cols)} - {"declared"} for n in d["columns"]["signature"]}


def replaced(res, new, declared, root=ROOT):
    """(column, instruments) of the first signature column that `new` derives from an instrument the input does not declare while NOT also reading what
    the result's own set read (a REPLACEMENT, e.g. stability.d -> stability_delta.d): the stored cells hold no reading for it, so the column would read a
    null that no cell of the map names. A column that only gains a source (across gains across_delta) keeps its old source, which is its declared fallback."""
    old, nw = signature_sources(root, res["tables"]), signature_sources(root, new)
    return next(((n, sorted(nw[n] - old[n] - set(declared))) for n in nw if n in old and not old[n] <= nw[n] and nw[n] - old[n] - set(declared)), None)


def reverdict_refusal(res, new, root=ROOT):
    """A refusal is a VALUE: the text saying why `res` cannot be re-verdicted under set `new`, else None.
    A set that changes what a door or membership read decided which units ran; those readings are not
    the ones the new set would have measured, so only a re-measure is honest."""
    m = Path(root) / "inputs" / res["input"] / "m.toml"
    declared = tomllib.loads(m.read_text()).get("instruments", []) if m.is_file() else []
    changed = membership_of(root, res["tables"], declared) != membership_of(root, new, declared)
    lacks = bool(schema.declared_cols(schema.load(Path(root) / "tables" / new / "codes.toml", root)[0] or {"columns": {}})) and "declared" not in res   # plan 0870: a declared column is read from couplings.toml at run time
    gone = replaced(res, new, declared, root)
    if gone:
        return (f"REFUSED: tables/{new} derives the column {gone[0]} from {', '.join(gone[1])}, which {res['input']} does not declare, so {res['run_id']} holds no reading of it.\n"
                f"  Next: declare it in inputs/{res['input']}/m.toml and re-measure with bin/cc run {res['input']} --tables {new}")
    return f"REFUSED: tables/{new} reads a declared column that {res['run_id']} was not run with.\n  Next: re-measure with bin/cc run {res['input']} --tables {new}" if lacks else None if not changed else (
        f"REFUSED: tables/{new} changes membership.toml, which decided which units of {res['input']} ran.\n"
        f"  Next: re-measure with bin/cc run {res['input']} --tables {new}")


def recode(rd, codes, direct, cols):
    """One stored reading with its codes re-read under a new set; its numbers and cells are never touched."""
    src = f"{rd['instrument']}.{rd['column']}"
    first = rd["cell"] if rd["per_size"] is None else rd["per_size"][0]["cell"]
    per = None if rd["per_size"] is None else [
        {**q, "code": cols[direct[src]]["map"].get(q["cell"], q["cell"])} for q in rd["per_size"]]
    return {**rd, "code": codes.get(direct.get(src), first), "per_size": per}


def reverdict_result(res, T, commit="none"):
    """The result `res` would have under table set T, from its stored sign cells alone (no data, no instrument)."""
    cols = schema.code_cols(T.codes)
    direct = {s["from"]: n for n, s in cols.items() if isinstance(s["from"], str)}
    readings, signature = [], []
    for old in res["signature"]:
        pt = old["point"]
        codes = detect.codes_of(cells_of(res, pt), T)
        sig = {n: codes[n] for n in T.codes["columns"]["signature"]}
        verdict, cls, line, why = detect.verdict_of(sig, T)
        mine = [recode(rd, codes, direct, cols) for rd in res["readings"] if rd["unit"]["point"] == pt
                and f"{rd['instrument']}.{rd['column']}" in direct]   # plan 0872: a reading the new set does not read (a v06 helper column) is not carried into it
        flags = {s: sorted({f for rd in mine if f"{rd['instrument']}.{rd['column']}" in detect.sources(s, cols)
                            for f in rd["flags"]}) for s in sig}
        readings += mine
        signature.append({"point": pt, "obtained": old["obtained"], **sig, "flags": {s: f for s, f in flags.items() if f},
                          "verdict": verdict, "verdict_class": cls, "row_line": line, "why": why, **detect.axes_of(codes, T)})
    old_id = res["run_id"]
    read = {f"results/{old_id}.json": schema.sha(ROOT / "results" / f"{old_id}.json"),
            **{k: h for k, h in res["read"].items() if not k.startswith("tables/")},
            **{f"tables/{T.name}/{q.name}": schema.sha(q) for q in T.paths},
            **({f"tables/{T.name}/membership.toml": schema.sha(T.membership_path)}
               if T.membership_path and any(k.endswith("/membership.toml") for k in res["read"]) else {})}
    return {**res, "run_id": f"{res['input']}@{T.name}", "tables": T.name, "derived_from": old_id,
            "code_commit": commit, "code_hash": schema.code_hash(ROOT), "read": read, "readings": readings, "signature": signature,
            "signature_columns": list(T.codes["columns"]["signature"])}   # plan 0876 B: the new set's columns, as `run` writes them (the old set's would name a column this set lacks)
