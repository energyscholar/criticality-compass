"""declare.py - plugin loaders, schemas, cross-references, the partition checker, validate (plumbing)."""
import difflib
import fnmatch
import itertools
import os
import re
import tomllib
import zipfile
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path
import numpy as np
import formats
from transducer import chk_transducer
from schema import ROOT, F, at, rel, _parsed, parse, load, row_lines, Ctx, unit_blocks, _SHA_ONCE, hashing_once, _sha, sha, MEASURE_SEEDED, import_closure, measure_hash, code_hash, code_cols, declared_cols  # noqa: F401  (moved by plan 0886; re-exported: the call sites keep `declare.<name>`)

SIGNS = ("SIG-", "NEG", "SLOW-", "ZERO!", "SLOW+", "POS", "SIG+", "UNRES")
RESULT_FIELDS = (  # the result field set that cc.toml [basic] must partition (view.py reads it from here)
    "instrument", "unit", "column", "eps_key", "eps", "estimate", "lo", "hi", "cell", "code", "per_size",
    "flags", "reason", "vector_key", "point", "obtained", "verdict", "verdict_class", "row_line", "why",
    "read", "code_commit", "code_hash", "measure_hash", "peak_rss_mb", "interval", "reports", "derived_from", "pair_readings", "pairs", "geometry", "order", "axis_lines", "declared")
RESERVED = {"door", "declare", "author", "detect", "view", "score", "admit"}
DECLARED = {"probe": ("COMPLETE", "INCOMPLETE", "UNKNOWN")}   # code columns read from an input's declaration (couplings.toml), never from data
SIZE_KEY = "L"                 # the one scalar a data file holds that is the lattice size, not a coupling
SIDECARS = ("observable", "block_map", "conjugate", "sinks", "two_start")
TEMPLATES = {"chain": {"axis": str}, "pair": {"axis": str, "pairs": list}, "all-pairs": {"axis": str},
             "matched": {"axis": str, "big": int, "small": int}, "matched-chain": {"axis": str, "pairs": list}}
SECTION_HINT = {"obtained.": "write one of: truth | navigated | observed (cc.toml alphabets.obtained)",
                "points.": 'write a case id from cases/ (see bin/cc help), or "none"'}
HINT = {"family": "a short description of the model", "mechanism": "one sentence on what drives the transition",
        "key": "the array's key in the data file (np.load(path).files lists them)",
        "template": "one of: chain, pair, all-pairs, matched, matched-chain (and that template's fields)"}
NUM = (int, float)
FIELD_TYPES = {"str": str, "int": int, "num": NUM}   # cc.toml [interval_fields] names a field's type by these words


def fmt(f):
    return f"{f.loc}: {f.msg}\n  Next: {f.nxt}"


def when(cond, p, field, msg, nxt):
    return [at(p, field, msg, nxt)] if cond else []


def tn(t):
    return "/".join(x.__name__ for x in (t if isinstance(t, tuple) else (t,)))


def shape(p, d, req, opt=None, pre=""):
    """Refuse missing, unknown and wrongly typed fields (schema/kind are checked by header)."""
    opt, out = opt or {}, []
    for k, t in {**req, **opt}.items():
        if k in d and not isinstance(d[k], t):
            out.append(at(p, pre + k, f"must be {tn(t)}, found {type(d[k]).__name__}", f"edit {k} in {p}"))
    out += [at(p, pre + k, "missing required field", f"add {k} = ... to {p}") for k in req if k not in d]
    known = set(req) | set(opt) | ({"schema", "kind"} if pre == "" else set())
    out += [at(p, pre + k, "unknown field", f"remove {k}, or check its spelling against the schema")
            for k in d if k not in known]
    return out


def header(p, d, kind):
    if d.get("schema") != 1:
        return [at(p, "", f"schema {d.get('schema')} not supported for kind {kind} (supported: 1)", "set schema = 1")]
    return when(d.get("kind") != kind, p, "", f"kind is '{d.get('kind')}', expected '{kind}'", f'set kind = "{kind}"')


def inalpha(p, field, v, alpha):
    ok = v == "TODO" or isinstance(v, (str, int, float)) and v in alpha
    return when(not ok, p, field, f"'{v}' is not in {list(alpha)}", f"use one of: {' '.join(map(str, alpha))}")


def todos(p, d, pre=""):
    """Every value still left as the template's "TODO", with a Next line."""
    for k, v in d.items():
        hint = SECTION_HINT.get(pre) or f"replace it with {HINT.get(k, 'the real value')}"
        if v == "TODO":
            yield at(p, pre + k, "still TODO", hint)
        elif isinstance(v, dict):
            yield from todos(p, v, f"{pre}{k}.")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if x == "TODO":
                    yield at(p, f"{pre}{k}[{i}]", "still TODO", hint)
                elif isinstance(x, dict):
                    yield from todos(p, x, f"{pre}{k}[{i}].")


@dataclass(frozen=True)
class Case:
    """A case WITHOUT its class: the loader drops the taxonomy truth (score.py alone reads it)."""
    id: str
    family: str
    mechanism: str
    controls: dict
    observables: dict
    sampler: str
    traps: list
    sources: list
    decoy_of: str
    pairs_with: list
    status: str
    studies: list
    breaker_verdict: str = ""
    blind_seal: str = ""


def load_case(path):
    d = tomllib.loads(Path(path).read_text())
    return Case(**{f.name: d[f.name] for f in dc_fields(Case) if f.name in d})


def load_truth(path):
    return tomllib.loads(Path(path).read_text())["class_truth"]


def case_truths(c):
    """{case id: class truth} of cases/ (declare-side: no measurement-closure module calls it, so the taxonomy truth never enters the key)."""
    return {f.stem: load_truth(f) for f in sorted((c.root / "cases").glob("*.toml"))}


def load_order_truth(path):
    return tomllib.loads(Path(path).read_text())["order_truth"]


def id_check(p, field, got, want, what):
    """The id a file declares must be the name of its file or directory (skipped for planted files)."""
    return when(want is not None and got != want, p, field, f"{field} '{got}' differs from {what}",
                f'set {field} = "{want}"')


# ---------------------------------------------------------------- cc.toml
def _regex_ok(x):
    try:
        re.compile(x)
        return True
    except re.error:
        return False


def chk_cc(p, d, c, stem=None):
    top = {k: dict for k in ("defaults", "data", "alphabets", "flags", "obtained_flag", "arrays", "basic", "check", "golden")}
    out = header(p, d, "cc") + shape(p, d, top, {"formats": dict, "transducer": dict, "levels": dict, "interval_fields": dict})
    if out:
        return out
    out += when("interval_method" not in d["alphabets"], p, "alphabets.interval_method", "missing", 'write interval_method = ["block", "iid"]')
    methods, fields_ = d["alphabets"].get("interval_method", []), d.get("interval_fields", {})   # plan 0878: every method of the alphabet has its fields table, and no table names a method outside it
    out += [at(p, f"interval_fields.{k}", "no [interval_fields] table for this method of alphabets.interval_method" if k in methods else "not a method of alphabets.interval_method",
               f"add [interval_fields.{k}] with required = {{...}}" if k in methods else f"delete [interval_fields.{k}]") for k in sorted(set(methods) ^ set(fields_))]
    out += [at(p, f"levels.{k}", "a level's z must be a number above 0", "write the z of that level, e.g. \"0.95\" = 1.959964")
            for k, v in d.get("levels", {}).items() if not (isinstance(v, NUM) and v > 0)]
    if "transducer" in d:   # plan 0883: the transducer file's sentences are data; the kinds are the two this code has a schema for
        out += shape(p, d["transducer"], {"kinds": list, "phase1_output": str, "phase2_output": str, "interval_role": str}, pre="transducer.")
        out += when(d["transducer"].get("kinds") != ["transducer", "record"], p, "transducer.kinds", f"{d['transducer'].get('kinds')} is not ['transducer', 'record']",
                    'write kinds = ["transducer", "record"]')
        if out:
            return out
    for n, v in {n: v for n, v in d.get("formats", {}).items() if isinstance(v, dict)}.items():   # a stack format's schema is data (plan 0873)
        out += inalpha(p, f"formats.{n}", n, d["alphabets"]["formats"]) + shape(p, v, {"reduces": list, "dims": int, "dtypes": list, "readers": dict}, {"pip": dict}, pre=f"formats.{n}.")
        out += [at(p, f"formats.{n}.readers", f"'{x}' is not a reader this code has", f"use one of: {' '.join(formats.READ)}")
                for x in (v["readers"].values() if isinstance(v.get("readers"), dict) else []) if x not in formats.READ]
    b, keeps, discards = d["basic"], set(d["basic"].get("keeps", [])), set(d["basic"].get("discards", []))
    out += shape(p, b, {"keeps": list, "discards": list, "blank": list, "blank_refuse": bool, "commands": list},
                 pre="basic.")
    out += [at(p, "basic", f"field '{x}' is in neither keeps nor discards", "add it to basic.keeps or basic.discards")
            for x in sorted(set(RESULT_FIELDS) - keeps - discards)]
    out += [at(p, "basic", f"'{x}' is not a result field", "remove it from basic.keeps/discards")
            for x in sorted((keeps | discards) - set(RESULT_FIELDS))]
    out += [at(p, "basic", f"field '{x}' is in both keeps and discards", "keep it in one list")
            for x in sorted(keeps & discards)]
    out += shape(p, d["check"], {"fast_budget_s": int, "slow": list, "memory_gb": (int, float), "exclusive": list}, {"replay": str}, pre="check.")
    out += inalpha(p, "check.replay", d["check"]["replay"], d["alphabets"]["replay"]) if "replay" in d["check"] else []   # plan 0886: which inputs test_run_all replays (tests/planted/cc-basic-field-missing.toml predates it)
    classes = d["golden"].get("classes", {})
    out += [at(p, f"golden.classes.{k}", "must have files and match, each a list of strings", "write files = [...] and match = [...]")
            for k, v in sorted(classes.items())
            if not all(isinstance(v.get(f), list) and v[f] and all(isinstance(x, str) for x in v[f]) for f in ("files", "match"))]
    out += [at(p, f"golden.classes.{k}", f"'{x}' is not a regex", "fix the pattern")
            for k, v in sorted(classes.items()) for x in v.get("match", []) if isinstance(x, str) and not _regex_ok(x)]
    stems = {Path(t).stem for t in c.checks["roles"]["tests"]}
    return out + [at(p, "check.slow", f"'{x}' is not a test in checks.toml", "name a test stem listed there")
                  for x in d["check"].get("slow", []) if x not in stems] \
        + [at(p, "check.exclusive", f"'{x}' is not a test in checks.toml", "name a test stem listed there")
           for x in d["check"].get("exclusive", []) if x not in stems]


# ---------------------------------------------------------------- cases and joins
def chk_case(p, d, c, stem=None):
    out = list(todos(p, d))
    if out:
        return out
    req = {"id": str, "family": str, "mechanism": str, "class_truth": str, "controls": dict, "observables": dict,
           "sampler": str, "traps": list, "sources": list, "decoy_of": str, "pairs_with": list, "status": str,
           "studies": list}
    out = header(p, d, "case") + shape(p, d, req, {"breaker_verdict": str, "blind_seal": str, "order_truth": str})
    if out:
        return out
    out += shape(p, d["controls"], {"names": list, "range": str}, pre="controls.")
    out += shape(p, d["observables"], {"list": list, "conjugate_observable": bool}, pre="observables.")
    out += id_check(p, "id", d["id"], stem, "the file name")
    classes, truths, dec = c.alpha["class_truth"], case_truths(c), d["decoy_of"]
    out += inalpha(p, "class_truth", d["class_truth"], classes)
    out += inalpha(p, "order_truth", d["order_truth"], c.alpha["order_truth"]) if "order_truth" in d else when(
        stem is not None, p, "order_truth", "missing required field", f"add order_truth = ... to {p}")
    out += [] if dec == "none" else inalpha(p, "decoy_of", dec, [x for x in classes if x != d["class_truth"]])
    others = {truths[k] for k in truths if k != d["id"]}
    out += when(dec != "none" and dec in classes and dec not in others, p, "decoy_of",
                f"no non-decoy case has class {dec}", f'add a case of class {dec}, or set decoy_of = "none"')
    out += inalpha(p, "status", d["status"], c.alpha["status"])
    out += when(d["status"] in c.alpha["status"][1:] and not d["studies"], p, "studies",
                f"status {d['status']} needs a non-empty studies list", "name the study sections")
    out += [at(p, "pairs_with", f"unknown case '{x}'", "name an existing case id")
            for x in d["pairs_with"] if x not in truths and x != d["id"]]
    return out + [at(p, "sources", f"{s} does not exist", "fix the path")
                  for s in d["sources"] if not Path(os.path.expanduser(s)).is_file()]


def chk_points(p, d, c, stem=None):
    out = header(p, d, "points") + shape(p, d, {"input": str, "points": dict})
    if out:
        return out
    out = list(todos(p, d)) + id_check(p, "input", d["input"], stem, "its directory")
    m, bad = load(c.over.get("input") or c.root / "inputs" / d["input"] / "m.toml", c.root)
    if bad:
        return out + bad
    pts, known = list(m["axes"]["point"]), set(case_truths(c)) | {"none"}
    out += [at(p, f'points."{x}"', "point is not joined", f'add "{x}" = <case id or "none"> to [points]')
            for x in pts if x not in d["points"]]
    out += [at(p, f'points."{x}"', f"{x} is not a point of {d['input']}", "remove it")
            for x in d["points"] if x not in pts]
    return out + [at(p, f'points."{k}"', f"unknown case '{v}'",
                     f'create it with bin/cc new case {v}, or map the point to an existing case or "none"')
                  for k, v in d["points"].items() if v not in known and v != "TODO"]


# ---------------------------------------------------------------- input (m.toml)
def shapes_of(c, path):
    """What a data file declares about its arrays, from the npy HEADERS only (no array is loaded): the shape of a bare .npy, or
    {key: shape} for an .npz in file order; cached per file on the Ctx."""
    if str(path) not in c.heads:
        with open(path, "rb") as f:
            zipped = f.read(4) == b"PK\x03\x04"
        if zipped:
            with zipfile.ZipFile(path) as z:
                c.heads[str(path)] = {n[:-4]: formats.head_of(z.open(n))[0] for n in z.namelist() if n.endswith(".npy")}
        else:
            with open(path, "rb") as f:
                c.heads[str(path)] = formats.head_of(f)[0]
    return c.heads[str(path)]


def stored(c, path, key):
    """(shape of the stored array, None) or (None, the keys the file does hold); cached per file and key."""
    if (str(path), key) not in c.shapes:
        h = shapes_of(c, path)
        c.shapes[(str(path), key)] = (h, None) if isinstance(h, tuple) else (h.get(key), list(h))
    return c.shapes[(str(path), key)]


LEVEL_STACKS = ("G", "GL")      # the array kinds that hold the observable's block levels; E, Q may be any column


def chk_array(p, loc, name, a, b, fp, m, c):
    """One declared array of one data block: its key, its level and its shape against cc.toml [arrays]."""
    dims, ax, lv = c.cfg["arrays"], m["axes"], m.get("observable", {}).get("levels")
    at_ = f"{loc}.arrays.{name}"
    out = when(name not in dims, p, at_, f"array kind '{name}' is not in cc.toml [arrays]",
               f"use one of: {' '.join(dims)}")
    e = shape(p, a, {"key": str}, {"level": int}, pre=at_ + ".")
    if e or name not in dims:
        return out + e
    fmt_ = m["data"]["format"]
    if name in formats.schemas(str(c.root)).get(fmt_, {"reduces": ()})["reduces"]:   # reduced from a raw stack by the door (plan 0873)
        return out + [at(p, f, msg, nxt) for f, msg, nxt in formats.problems(fmt_, loc, name, a, b, fp, m, str(c.root))] + when(
            2 - ("level" in a) != dims[name], p, at_, f"selects a {2 - ('level' in a)}-D array but {name} is {dims[name]}-D in cc.toml [arrays]", "fix level")
    shp, keys = stored(c, fp, a["key"])
    if shp is None:
        return out + [at(p, at_, f"key '{a['key']}' absent from {b['path']} (keys: {' '.join(keys)})", "fix the key")]
    got = len(shp) - ("level" in a and len(shp) == 2)
    if "level" in a and len(shp) == 1:
        return out + [at(p, at_, "level given on a 1-D stored array", "remove level")]
    if got != dims[name]:
        return out + [at(p, at_, f"selects a {got}-D array but {name} is {dims[name]}-D in cc.toml [arrays]", "fix level")]
    bad_levels = lv and name in LEVEL_STACKS and len(shp) == 2 and shp[1] != lv[ax["size"].index(b["size"])]
    return out + ([at(p, at_, f"{name} stores {shp[-1]} levels but observable.levels declares "
                      f"{lv[ax['size'].index(b['size'])]} for size {b['size']}",
                      "DATA: if the file is right, set observable.levels to its level count; CODE: if this array is not "
                      "the observable's level stack, give it another array kind (E and Q take any column)")]
                   if bad_levels else [])


def series_length(m, name, fp, key, c):
    """n, the number of snapshots one declared array holds, from the file's HEADER (a stack's raw N, or the stored array's first axis)."""
    shp = formats.shape_of(m["data"]["format"], fp, key, str(c.root)) if name in formats.schemas(str(c.root)).get(m["data"]["format"], {"reduces": ()})["reduces"] else stored(c, fp, key)[0]
    return shp[0]


def block_floor(p, iv, lengths):
    """plan 0878: with [interval] min_blocks declared (block method), every declared file must hold n // b >= min_blocks blocks, else the input is refused
    (a Null at run, a finding at validate; never a warning). The Next line names the two declared routes."""
    mb, b = iv.get("min_blocks"), iv.get("b")
    if mb is None or iv.get("method") != "block" or not isinstance(b, int) or b < 1:
        return []
    short = sorted((n // b, path, key, n) for path, key, n in lengths)
    if not short or short[0][0] >= mb:
        return []
    k, path, key, n = short[0]
    return [at(p, "interval.min_blocks",
               f"{sum(x[0] < mb for x in short)} of {len(short)} declared arrays hold fewer than min_blocks = {mb} blocks of b = {b} (the shortest: {path} key {key}, n {n} // b {b} = {k})",
               f'declare method = "gamma" (window_s, window_max, door_z, level; cc.toml [interval_fields.gamma]), or keep method = "block" with b <= {n // mb} (n {n} // min_blocks {mb}): '
               f"b must also be >= k*tau for the record's integrated autocorrelation time tau, so this record admits k*tau <= {n // mb}")]


def chk_data(p, m, c):
    d, out, blocks, ax, lengths = m["data"], [], {}, m["axes"], []
    out += shape(p, d, {"format": str, "files": list}, pre="data.")
    out += inalpha(p, "data.format", d.get("format"), c.alpha["formats"])
    for i, b in enumerate(d.get("files", [])):
        loc = f"data.files[{i}]"
        e = shape(p, b, {"point": str, "size": int, "start": str, "path": str, "arrays": dict}, pre=loc + ".")
        if e:
            out += e
            continue
        key = (b["point"], b["size"], b["start"])
        out += when(key in blocks, p, loc, f"duplicate block (point {key[0]}, size {key[1]}, start {key[2]})",
                    "remove one of the two blocks")
        out += inalpha(p, loc + ".point", key[0], ax["point"]) + inalpha(p, loc + ".size", key[1], ax["size"])
        out += inalpha(p, loc + ".start", key[2], ax["starts"])
        blocks[key] = b["arrays"]
        fp = c.data_root / b["path"]
        if not fp.is_file():
            out.append(at(p, loc + ".path", f"{b['path']} does not exist under the data root",
                          "fix the path, or put the file there"))
            continue
        for name, a in b["arrays"].items():
            got = chk_array(p, loc, name, a, b, fp, m, c)
            out += got
            lengths += [] if got else [(b["path"], a["key"], series_length(m, name, fp, a["key"], c))]
    out += block_floor(p, m["interval"], lengths)
    for iname in m["instruments"]:
        inst = c.reg[iname]
        sizes, starts = unit_blocks(m, inst)
        for pt, sz, st, ar in itertools.product(ax["point"], sizes, starts, inst["arrays"]):
            out += when(ar not in blocks.get((pt, sz, st), {}), p, "data.files",
                        f"{iname} needs array {ar} at (point {pt}, size {sz}, start {st})",
                        "add that [[data.files]] block")
    return out


SIDECAR_SHAPE = {
    "observable": {"name": str, "definition": str, "levels": list, "final_size": int},
    "block_map": {"name": str, "factor": int, "keeps": str, "discards": str},
    "conjugate": {"observable": str, "conjugate_to": str, "hamiltonian_knowledge": bool},
    "sinks": {"ordered": NUM, "disordered": NUM},
    "two_start": {"observable": str, "definition": str, "unit_scale": dict}}


def chk_relations(p, d, c, use, sz):
    """Every relation an instrument needs is declared and well formed; no relation is left unused."""
    rels, need, out = d.get("relations", {}), {r for i in use for r in i["relations"]}, []
    out += [at(p, f"relations.{rn}", "missing required relation", f"add [relations.{rn}]")
            for rn in need if rn not in rels]
    for rn, r in rels.items():
        t = TEMPLATES.get(r.get("template"))
        if t is None:
            out.append(at(p, f"relations.{rn}.template", f"unknown template '{r.get('template')}'",
                          f"use one of: {' '.join(TEMPLATES)}"))
            continue
        out += shape(p, r, {"template": str, "provenance": str, "direction_from": str, **t}, {"coupling": str} if rn == "control" else None, pre=f"relations.{rn}.")
        out += inalpha(p, f"relations.{rn}.provenance", r.get("provenance"), ("Coupling", "Continuation"))
        prs = r["pairs"] if r["template"] == "matched-chain" else [[r.get("big"), r.get("small")]]
        for big, small in (x for x in prs if r["template"] in ("matched", "matched-chain") and "observable" in d and len(x) == 2 and set(x) <= set(sz)):
            lb, ls = (d["observable"]["levels"][sz.index(x)] for x in (big, small))
            out += when(ls != lb - 1, p, f"relations.{rn}",
                        f"matched needs small levels = big levels - 1 (found {ls} and {lb})",
                        "fix observable.levels or the sizes")
        out += when(r["template"] == "matched-chain" and any(len(x) != 2 or set(x) - set(sz) for x in prs), p, f"relations.{rn}.pairs",
                    "each pair is [big, small], both declared sizes", "write pairs = [[243, 81], [81, 27]]")
    return out + [at(p, "relations", f"relation '{rn}' is not used by any declared instrument", "delete it")
                  for rn in rels if rn not in need]


SIDECAR_OPT = {"observable": {"level_floor": int}, "block_map": {"limited": str}}   # plan 0873: level 0 exclusion, declared


def limited(p, d, c):
    """A block map that is not a measured site per cell (assigned, resolution-limited) must exclude level 0 from every matched edge."""
    lim, floor = d.get("block_map", {}).get("limited", "none"), d.get("observable", {}).get("level_floor", 0)
    return inalpha(p, "block_map.limited", lim, c.alpha.get("limited", ("none",))) + when(
        lim != "none" and floor < 1, p, "observable.level_floor", f"block_map.limited = '{lim}' but level 0 is not excluded (level_floor {floor})",
        "set [observable] level_floor = 1: the finest level carries the cell or instrument scale, not the system")


def chk_input(p, d, c, stem=None):
    todo = list(todos(p, d))
    if [t for t in todo if not t.loc.split(":", 1)[1].startswith("obtained")]:
        return todo   # a template still full of TODOs: report them, nothing else
    req = {"id": str, "instruments": list, "obtained": dict, "axes": dict, "interval": dict, "eps": dict,
           "kernel": dict, "data": dict}
    out = header(p, d, "input") + shape(p, d, req, {k: dict for k in SIDECARS + ("relations",)})
    out += id_check(p, "id", d.get("id"), stem, "its directory")
    out += [at(p, "instruments", f"'{i}' is not in the instrument registry", f"use one of: {' '.join(c.reg)}")
            for i in d.get("instruments", []) if i not in c.reg]
    ax = d.get("axes", {})
    out += shape(p, ax, {"point": list, "size": list, "starts": list, "main_start": str}, pre="axes.")
    if out:
        return todo + out
    sz, use = ax["size"], [c.reg[i] for i in d["instruments"]]
    need = lambda key: {x for i in use for x in i[key]}  # noqa: E731
    out += when(not (sz and all(isinstance(x, int) for x in sz) and sz == sorted(set(sz))), p, "axes.size",
                "sizes must be integers, strictly ascending", "fix the list")
    out += [at(p, "axes.size", f"{i} accumulates B over the size chain and needs exactly 3 sizes, found {len(sz)}",
               "declare three sizes, or do not declare the instrument") for i in d["instruments"]
            if c.reg.get(i, {}).get("unit") == "pair" and len(sz) != 3]
    out += inalpha(p, "axes.main_start", ax["main_start"], ax["starts"])
    miss, extra = sorted(set(ax["point"]) - set(d["obtained"])), sorted(set(d["obtained"]) - set(ax["point"]))
    out += when(miss or extra, p, "obtained", f"keys differ from axes.point (missing {miss}, extra {extra})",
                "list every point once")
    for k, v in d["obtained"].items():
        out += inalpha(p, f'obtained."{k}"', v, c.alpha["obtained"])
    for name in SIDECARS:
        want = name in need("sidecar")
        out += when(want and name not in d, p, name, "missing required table (a declared instrument needs it)",
                    f"add [{name}]")
        out += when(not want and name in d, p, name, "table present but no declared instrument uses it",
                    f"delete [{name}], or declare the instrument")
        out += shape(p, d[name], SIDECAR_SHAPE[name], SIDECAR_OPT.get(name), pre=f"{name}.") if name in d else []
    out += limited(p, d, c)
    out += when("two_start" in d and isinstance(d["two_start"].get("unit_scale"), dict)
                and sorted(d["two_start"]["unit_scale"]) != sorted(map(str, sz)), p, "two_start.unit_scale",
                f"must declare a unit scale for every size {list(map(str, sz))}", "add the missing sizes, or remove the extra ones")
    out += when(need("relations") and "relations" not in d, p, "relations",
                "missing required table (a declared instrument needs it)", "add [relations.<name>]")
    out += when(not need("relations") and "relations" in d, p, "relations",
                "table present but no declared instrument uses it", "delete [relations], or declare the instrument")
    out += chk_relations(p, d, c, use, sz)
    want = {e for i in use for e in i["columns"].values()}
    out += [at(p, f"eps.{e}", "eps key missing (a declared instrument's column reads it)",
               f"add {e} = <margin> to [eps]") for e in sorted(want - set(d["eps"]))]
    out += [at(p, f"eps.{e}", "eps key not required by any declared instrument", f"delete {e}")
            for e in sorted(set(d["eps"]) - want)]
    out += [at(p, f"eps.{e}", "eps must be a number above 0", "set a positive margin")
            for e, v in d["eps"].items() if not (isinstance(v, NUM) and v > 0)]
    out += shape(p, d["kernel"], {"uses": list}, pre="kernel.")
    out += when(not need("operators") <= set(d["kernel"].get("uses", [])), p, "kernel.uses",
                f"operators {sorted(need('operators') - set(d['kernel'].get('uses', [])))} of declared "
                "instruments are not in kernel.uses", "add them")
    iv = d["interval"]
    out += inalpha(p, "interval.method", iv.get("method"), c.alpha["interval_method"])   # plan 0883: the alphabet is cc.toml data
    spec = c.cfg["interval_fields"].get(iv.get("method"), {})   # plan 0878: the fields of each method are cc.toml data too ([interval_fields.<method>])
    out += shape(p, iv, {k: FIELD_TYPES[t] for k, t in spec.get("required", {}).items()}, {k: FIELD_TYPES[t] for k, t in spec.get("optional", {}).items()}, pre="interval.") if spec else []
    z = c.cfg[spec["level_in"]] if "level_in" in spec else None   # a method that reads z from a declared table refuses a level the table does not hold
    out += when(z is not None and isinstance(iv.get("level"), NUM) and str(iv["level"]) not in z, p, "interval.level",
                f"level {iv.get('level')} has no z in cc.toml [{spec.get('level_in')}] (declared: {' '.join(z or {})})",
                f"use one of the declared levels: {' '.join(z or {})}; or add the z of that level to cc.toml [{spec.get('level_in')}]")
    out += when(iv.get("method") == "iid" and iv.get("tau_declared") != 1, p, "interval.tau_declared",
                "iid resampling needs tau_declared = 1", "add tau_declared = 1")
    return todo + (out if out else chk_data(p, d, c))


# ---------------------------------------------------------------- manifest, instrument, codes
def classify_changes(classes, name, old, new):
    """[(class, line)] for every line a regolden of transcript `name` changes. `classes` is cc.toml [golden.classes]:
    the first class whose files globs match `name` and whose regexes match the line claims it; the rest is 'e'."""
    out = []
    for ln in difflib.unified_diff((old or "").splitlines(), new.splitlines(), lineterm="", n=0):
        if ln[:1] in "+-" and not ln.startswith(("+++", "---")):
            hit = [k for k, c in sorted(classes.items())
                   if any(fnmatch.fnmatch(name, g) for g in c["files"]) and any(re.search(r, ln) for r in c["match"])]
            out.append((hit[0] if hit else "e", ln))
    return out


def chk_manifest(p, d, c, stem=None):
    out = header(p, d, "data-manifest") + shape(p, d, {"input": str, "files": dict})
    if out:
        return out
    out += id_check(p, "input", d["input"], stem, "the file name")
    m, bad = load(c.over.get("input") or c.root / "inputs" / d["input"] / "m.toml", c.root)
    if bad:
        return out + bad
    paths, iid = {b["path"] for b in m["data"]["files"]}, d["input"]
    out += [at(p, "files", f"{x} is used by the input but not pinned", f"bin/cc data add {iid}")
            for x in sorted(paths - set(d["files"]))]
    out += [at(p, "files", f"{x} is pinned but the input does not use it", "delete the entry")
            for x in sorted(set(d["files"]) - paths)]
    return out + [at(p, "", f"{x} changed since it was pinned",
                     f"if intended, make a new input: bin/cc new input {iid}-2 --like {iid}, "
                     f"then bin/cc data add {iid}-2")
                  for x, h in d["files"].items() if (c.data_root / x).is_file() and sha(c.data_root / x) != h]


def chk_instrument(p, d, c, stem=None):
    if list(todos(p, d)):
        return list(todos(p, d))   # a template still full of TODOs: report them, nothing else
    req = {"module": str, "operators": list, "unit": str, "reports": list, "arrays": list, "axes": list,
           "relations": list, "sidecar": list, "flags": list, "pipeline": list, "columns": dict}
    out = header(p, d, "instrument") + shape(p, d, req, {"requires": list, "door_values": list, "quantity": str, "start": str, "per_point": bool, "member_default": str, "door_label": str})
    if out:
        return out
    out += when(d.get("per_point") and d["unit"] != "pair", p, "per_point", "only a pair instrument is read per point (over the control pairs that touch it)",
                'remove per_point, or set unit = "pair"')
    out += inalpha(p, "unit", d["unit"], ("point", "pair", "point-size"))
    out += when(d.get("member_default", "") not in ["", *d.get("door_values", [])], p, "member_default", f"'{d.get('member_default')}' is not in door_values {d.get('door_values', [])}",
                "name one of the instrument's door_values (the door value a set without a membership rule reads)")
    out += [at(p, "requires", f"'{r}' must be a registry instrument with no requires of its own",
               "name an instrument that is read first (one level in v0.1)")
            for r in d.get("requires", []) if r not in c.reg or c.reg[r].get("requires")]
    for f, alpha in (("operators", ("A", "B")), ("axes", ("point", "size", "starts")), ("sidecar", SIDECARS),
                     ("arrays", tuple(c.cfg["arrays"])), ("flags", tuple(c.cfg["flags"]))):
        out += [x for v in d[f] for x in inalpha(p, f, v, alpha)]
    pl, mod, root = d["pipeline"], d["module"], c.root
    out += when(pl[:1] != ["stage:reduce"], p, "pipeline", "the first step must be stage:reduce",
                'start the list with "stage:reduce"')
    mp, dp = root / "cc" / "instruments" / f"{mod}.py", root / "cc" / "door.py"
    out += when(f"cc/instruments/{mod}.py" not in c.checks["roles"]["maths"], p, "module",
                f"'{mod}' is not under checks.toml [roles].maths", f'add "cc/instruments/{mod}.py" to [roles].maths')
    taken = {f.stem for f in (root / "cc").glob("*.py")} | set(c.checks["allow"]["modules"]) | RESERVED
    out += when(mod in taken, p, "module", f"'{mod}' collides with a plumbing or allow-listed module name",
                "pick another module name")
    src = mp.read_text() if mp.is_file() else None
    out += when(src is None, p, "module", f"cc/instruments/{mod}.py does not exist", "write the module")
    out += when(src is not None and "TODO-STAGE" in src, p, "module", f"cc/instruments/{mod}.py still holds the "
                "TODO-STAGE marker", "write the stages, then delete the marker line")
    for step in pl:
        kind, _, name = step.partition(":")
        text, where = (src, f"cc/instruments/{mod}.py") if kind == "stage" else (dp.read_text() if dp.is_file() else "", "cc/door.py")
        out += when(kind not in ("stage", "door"), p, "pipeline", f"unknown step '{step}'",
                    "use stage:<name> or door:<name>")
        out += when(kind in ("stage", "door") and text is not None and f"def {name}(" not in text, p, "pipeline",
                    f"{step}: no def {name}( in {where}", "write the function")
    return out


def doms(d, nulls):
    """column -> its alphabet followed by the nulls (the verdict domain)."""
    return {k: list(v["alphabet"]) + list(nulls) for k, v in d["columns"]["signature"].items()}


def chk_column(p, loc, col, c, allc):
    """One code column: where it comes from, its map (total, no foreign values) and its combine rule."""
    e = shape(p, col, {"from": (str, list), "alphabet": list, "map": dict}, {"combine": dict, "nullable": (bool, str)}, pre=loc + ".")   # nullable: false | true (a null of the 2nd source is a cell) | "either" (plan 0877 D2: a null of either)
    if e:
        return e
    nl = col.get("nullable")
    if isinstance(nl, str) and nl != "either":
        return [at(p, loc + ".nullable", f"'{nl}' is not true, false or \"either\"", "write nullable = true, nullable = false or nullable = \"either\"")]
    src, alpha, nulls = col["from"], col["alphabet"], c.alpha["nulls"]
    if isinstance(src, str):
        inst, _, column = src.partition(".")
        if inst == "declared":      # plan 0870: a column read from the input's declaration; its map keys are the declared alphabet
            if column not in DECLARED:
                return [at(p, loc + ".from", f"'{src}' is not a declared column", f"use one of: {' '.join('declared.' + k for k in DECLARED)}")]
            want, needs = list(DECLARED[column]), False
        elif column not in c.reg.get(inst, {}).get("columns", {}):
            return [at(p, loc + ".from", f"'{src}' is not a column of a registry instrument",
                       "name <instrument>.<column>")]
        else:
            unit = c.reg[inst]["unit"]
            if unit == "pair" and not c.reg[inst].get("per_point"):
                return [at(p, loc + ".from", f"'{src}' is a pair instrument's column and has no per-point cell",
                           f"declare per_point = true in instruments/{inst}.toml (its cells are combined over the control pairs that touch a point), or read a point instrument")]
            want, needs = list(SIGNS), unit == "point-size" or unit == "pair"
    else:
        if len(src) != 2 or [x for x in src if x not in allc]:
            return [at(p, loc + ".from", f"derived columns name two helper/signature columns, not {src}",
                       "fix the list")]
        second = list(allc[src[1]].get("alphabet", [])) + list(nulls) * bool(nl)   # nullable: a null of the 2nd source is a named cell
        first = list(allc[src[0]].get("alphabet", [])) + list(nulls) * (nl == "either")   # "either": a null of the 1st source too (plan 0877 D2)
        want = [f"{a},{b}" for a, b in itertools.product(first, second)]
        needs = False
    mk, cb = col["map"], col.get("combine")
    out = [at(p, loc + ".map", f"missing key '{k}'", f'add "{k}" = <code>') for k in want if k not in mk]
    out += [at(p, loc + ".map", f"foreign key '{k}'" + (" (nulls are never keys)" if k in nulls else ""), "remove it")
            for k in mk if k not in want]
    out += [at(p, f'{loc}.map."{k}"', f"'{v}' is not in the alphabet {alpha}", f"use one of: {' '.join(alpha)}")
            for k, v in mk.items() if v not in alpha and not (nl == "either" and v in nulls and set(k.split(",")) <= set(nulls))]   # a null value only where BOTH sources are null
    out += when(needs != (cb is not None), p, loc + ".combine",
                "required for a point-size source" if needs else "only a point-size source combines", "fix")
    if cb is not None:
        out += shape(p, cb, {"over": str, "rank": list}, {"top_only": list, "agree": list, "disagree": str, "prefer_door": str}, pre=loc + ".combine.")
        out += when(cb.get("prefer_door", "") not in ["", *c.reg.get(src.partition(".")[0] if isinstance(src, str) else "", {}).get("door_values", [])], p, loc + ".combine.prefer_door",
                    f"'{cb.get('prefer_door')}' is not a door value of the instrument the column reads", "name one of its door_values: only the items read on that door value combine, when there is one")
        out += [at(p, loc + f".combine.{k}", f"'{x}' is not in the alphabet {alpha}", "list codes of this column")
                for k in ("top_only", "agree") for x in cb.get(k, []) if x not in alpha]
        out += when(("agree" in cb) != ("disagree" in cb), p, loc + ".combine.agree", "agree and disagree come together",
                    "write both: the codes that count only when every item reads them, and the code a disagreement reads")
        out += when(cb.get("disagree", alpha[0] if alpha else "") not in alpha, p, loc + ".combine.disagree", f"'{cb.get('disagree')}' is not in the alphabet {alpha}", "use a code of this column")
        out += when(sorted(cb.get("rank", [])) != sorted(alpha + nulls), p, loc + ".combine.rank",
                    f"must list {sorted(alpha + nulls)} exactly once each", "fix the list")
    return out


def chk_codes(p, d, c, stem=None):
    out = header(p, d, "codes") + shape(p, d, {"signs": list, "null_rank": list, "columns": dict})
    if out:
        return out
    out += when(tuple(d["signs"]) != SIGNS, p, "signs", f"must be sign.py's eight names {list(SIGNS)}", "restore the list")
    out += when(d["null_rank"] != c.alpha["nulls"], p, "null_rank",
                f"must equal cc.toml alphabets.nulls {c.alpha['nulls']}", "restore the list")
    out += shape(p, d["columns"], {"signature": dict}, {"helper": dict}, pre="columns.")
    allc = code_cols(d)
    for kind in ("helper", "signature"):
        for name, col in d["columns"].get(kind, {}).items():
            out += chk_column(p, f"columns.{kind}.{name}", col, c, allc)
    return out


# ---------------------------------------------------------------- the partition
def patterns(free, cols, dom):
    """Compress a boolean array (True = to list) into boxes: widen the first cell column by column."""
    free, boxes = free.copy(), []
    while free.any():
        box = [[int(v)] for v in np.argwhere(free)[0]]
        for ci in range(len(cols)):
            def whole(v):
                return free[np.ix_(*[sorted(set(box[ci]) | {v}) if j == ci else box[j] for j in range(len(cols))])].all()
            box[ci] = [v for v in range(len(dom[ci])) if whole(v)]
        free[np.ix_(*box)] = False
        boxes.append([(cols[ci], [dom[ci][v] for v in box[ci]]) for ci in range(len(cols)) if len(box[ci]) < len(dom[ci])])
    return boxes


def chk_partition(p, cols, dom, rows, text, limit=20, key="row"):
    """Rows (list of dicts column -> allowed values) must be pairwise disjoint and cover the domain."""
    shp, out, lines = [len(x) for x in dom], [], row_lines(text, key)
    owner = np.full(shp, -1)
    for k, w in enumerate(rows):
        sub = np.ix_(*[[dom[ci].index(v) for v in w.get(col, dom[ci])] for ci, col in enumerate(cols)])
        prev, mine = owner[sub], np.zeros(shp, bool)
        mine[sub] = True
        for j in sorted(set(prev[prev >= 0].tolist())):
            both = mine & (owner == j)
            cell = dict(zip(cols, (dom[ci][v] for ci, v in enumerate(np.argwhere(both)[0]))))
            out.append(at(p, "", f"rows at lines {lines[j]} and {lines[k]} overlap on {int(both.sum())} cells, "
                                 f"first: {cell}", "narrow one of the two rows so they share no cell"))
        owner[sub] = k
    if (owner < 0).any():
        boxes = patterns(owner < 0, cols, dom)
        body = "".join(f"\n  [[{key}]]" + "".join(f"\n  when.{c} = {v}".replace("'", '"') for c, v in b)
                       for b in boxes[:limit])
        more = f"\n  ... ({len(boxes) - limit} more patterns)" if len(boxes) > limit else ""
        out.append(at(p, "", f"{int((owner < 0).sum())} uncovered cells in {len(boxes)} patterns{body}{more}",
                      "add a [[row]] with one of these when-lines, or widen a neighbouring row"))
    return out


def chk_rows(p, d, dom, key="row"):
    """Every row: known columns, values inside each column's domain, a listed verdict, a why."""
    out, read = [], set()
    for i, r in enumerate(d[key]):
        loc, w = f"{key}[{i}]", r.get("when", {})
        out += shape(p, r, {"when": dict, "verdict": str, "why": str}, pre=loc + ".")
        out += [at(p, loc + ".when", f"unknown column '{k}'", "use a signature column") for k in w if k not in dom]
        out += [at(p, f"{loc}.when.{k}", f"'{x}' is not in {dom[k]}", "use values of that column or the nulls")
                for k, v in w.items() if k in dom for x in v if x not in dom[k]]
        out += when(r.get("verdict") not in d["verdicts"], p, loc + ".verdict",
                    f"'{r.get('verdict')}' is not in verdicts", "list it in verdicts")
        out += when(not r.get("why"), p, loc + ".why", "empty", "say why this row gives this verdict")
        read |= set(w)
    return out, read


def chk_classes(p, d, c):
    """refuse, class_of and verdicts agree: every verdict refuses, is classed, or is a class name."""
    classes, co, refuse = c.alpha["class_truth"], d.get("class_of", {}), set(d["refuse"])
    out = [at(p, "refuse", f"'{x}' is not in verdicts", "list it in verdicts") for x in sorted(refuse - set(d["verdicts"]))]
    out += [at(p, "class_of", f"'{x}' is both refusing and classed", "keep it in one") for x in sorted(refuse & set(co))]
    out += [at(p, f"class_of.{k}", f"'{v}' is not in {classes}", "use a class") for k, v in co.items() if v not in classes]
    return out + [at(p, "verdicts", f"verdict '{v}' is in none of refuse, class_of or the class names",
                     "list it in refuse, add it to [class_of], or use a class name")
                  for v in d["verdicts"] if v not in refuse and v not in co and v not in classes]


def chk_verdict(p, d, c, stem=None):
    req = {"columns": list, "ignores": list, "verdicts": list, "refuse": list, "row": list}
    out = header(p, d, "verdict") + shape(p, d, req, {"ignores_reason": str, "class_of": dict})
    if out:
        return out
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    if bad:
        return bad
    cols, dom, text = d["columns"], doms(codes, c.alpha["nulls"]), Path(c.root, p).read_text()
    out += when(set(cols) != set(dom), p, "columns", f"must equal the signature columns of codes.toml {list(dom)}",
                "fix the list")
    out += when(d["ignores"] and not d.get("ignores_reason"), p, "ignores_reason",
                "required when ignores is not empty", "say why those columns are ignored")
    out += [at(p, "ignores", f"'{x}' is not a column", "fix the list") for x in d["ignores"] if x not in cols]
    out += chk_classes(p, d, c)
    if set(cols) != set(dom):
        return out
    rows, read = chk_rows(p, d, dom)
    out += rows
    out += [at(p, "columns", f"column '{x}' is neither read by a row nor in ignores",
               "read it in a row or add it to ignores") for x in cols if x not in read and x not in d["ignores"]]
    return out if out else chk_partition(p, cols, [dom[x] for x in cols], [r["when"] for r in d["row"]], text)


def same(p, loc, got, want, what):
    """A declared list or key set must equal `want` (order ignored)."""
    return when(sorted(map(str, got)) != sorted(map(str, want)), p, loc, f"{what}: must be exactly {sorted(map(str, want))}",
                "fix the list")


EDGE_AXES = (("descent", "edge_code", "descent_rank"), ("ascent", "ascent_code", "ascent_rank"))   # plan 0871 E1: each declared edge axis is one factor of the bracket table


def bracket_axes(b):
    """[(axis, step -> edge code, rank)] of the edge axes a bracket section declares (v01-v04: descent only); the table is over these and mid."""
    return [(n, b[c], b[r]) for n, c, r in EDGE_AXES if c in b]


def chk_family(p, d, c, stem=None):
    """A set's family rule: the three fingerprint sections against the codes, the registry and the alphabets, then the
    partition over (bracket, f1, f2) (every cell of the product has exactly one row). Plan 0871: a set that lists the column `points`
    also reads the interior's per-point geometry and the two LINE-END sides (`points`, `lower`, `upper`; sections points, side, side_row)."""
    ext = "points" in (d["columns"] if isinstance(d.get("columns"), list) else [])
    req = {"columns": list, "verdicts": list, "refuse": list, "alphabets": dict, "bracket": dict, "f1": dict, "f2": dict, "row": list}
    out = header(p, d, "family") + shape(p, d, {**req, **({"points": dict, "side": dict, "side_row": list} if ext else {})}, {"class_of": dict})
    if out:
        return out
    cols, al, nulls, b = ["bracket", "f1", "f2", *SIDE_COLS * ext], d["alphabets"], c.alpha["nulls"], d["bracket"]
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    if bad:
        return bad
    out += same(p, "columns", d["columns"], cols, "columns") + same(p, "alphabets", al, cols, "alphabets")
    out += [at(p, f"alphabets.{k}", f"must include {x}", f"add {x}") for k in al for x in ("UNRES", *nulls) if x not in al[k]]
    out += chk_classes(p, d, c)
    out += shape(p, b, {"reads": str, "rank": dict, "edge_code": dict, "descent_rank": list, "point_code": dict,
                        "mid_rank": list, "table": dict}, {"ascent_code": dict, "ascent_rank": list}, pre="bracket.")
    out += when(("ascent_code" in b) != ("ascent_rank" in b), p, "bracket.ascent_code", "ascent_code and ascent_rank come together", "declare both or neither")
    out += shape(p, d["f1"], {"reads": str, "relation": str, "eps": str, "code": dict, "rank": list}, pre="f1.")
    out += shape(p, d["f2"], {"reads": str, "relation": str, "code": dict, "rank": list}, pre="f2.")
    if out or set(al) != set(cols):
        return out
    sig, reg = codes["columns"]["signature"], c.reg
    out += when(b["reads"] not in sig, p, "bracket.reads", f"'{b['reads']}' is not a signature column", f"use one of: {' '.join(sig)}")
    out += same(p, "bracket.rank", b["rank"], sig.get(b["reads"], {}).get("alphabet", []), "rank keys = that column's alphabet")
    out += same(p, "bracket.point_code", b["point_code"], b["rank"], "point_code keys = rank keys")
    out += same(p, "bracket.edge_code", b["edge_code"], ("SIG-", "UNRES", "SIG+"), "edge_code keys (eps 0 reaches three cells)")
    axes = bracket_axes(b)
    out += [x for n, code, rank in axes for x in same(p, f"bracket.{n}_rank", rank, [*nulls, *set(code.values())], f"{n}_rank")]
    out += [x for n, code, _ in axes[1:] for x in same(p, f"bracket.{n}_code", code, ("SIG-", "UNRES", "SIG+"), f"{n}_code keys")]
    out += same(p, "bracket.mid_rank", b["mid_rank"], [*nulls, *set(b["point_code"].values())], "mid_rank")
    out += same(p, "bracket.table", b["table"], [",".join(k) for k in itertools.product(*[r for _, _, r in axes], b["mid_rank"])], "table keys (total)")
    out += [at(p, f'bracket.table."{k}"', f"'{v}' is not in alphabets.bracket", "use a bracket value")
            for k, v in b["table"].items() if v not in al["bracket"]]
    inst, _, col = d["f1"]["reads"].partition(".")
    out += when(col not in reg.get(inst, {}).get("columns", {}), p, "f1.reads", f"'{d['f1']['reads']}' is not a column of a registry instrument",
                "name <instrument>.<column>")
    out += when(reg.get(inst, {}).get("columns", {}).get(col, d["f1"]["eps"]) != d["f1"]["eps"], p, "f1.eps",
                "must be the eps key of that column in the registry", "fix the key")
    out += when(d["f1"]["relation"] != "all-pairs" or d["f2"]["relation"] != "chain", p, "f1.relation",
                "f1 reads an all-pairs relation, f2 a chain", "fix the relations")
    out += when(reg.get(d["f2"]["reads"], {}).get("unit") != "pair", p, "f2.reads", "must be a registry instrument of unit pair", "fix it")
    extra = reg.get(d["f2"]["reads"], {}).get("door_values", [])
    for f, keys in (("f1", SIGNS), ("f2", [*SIGNS, *extra])):
        out += same(p, f"{f}.code", d[f]["code"], keys, f"{f} code keys")
        out += same(p, f"{f}.rank", d[f]["rank"], al[f], f"{f} rank")
        out += [at(p, f"{f}.code.{k}", f"'{v}' is not in alphabets.{f}", "use a value of that alphabet")
                for k, v in d[f]["code"].items() if v not in al[f]]
    rows, read = chk_rows(p, d, al)
    out += rows
    out += [at(p, "columns", f"column '{x}' is not read by any row", "read it in a row") for x in cols if x not in read]
    out += chk_sides(p, d, c, codes, al) if ext else []
    return out if out else chk_partition(p, cols, [al[x] for x in cols], [r["when"] for r in d["row"]], Path(c.root, p).read_text())


SIDE_COLS = ("points", "lower", "upper")
SIDE_KEYS = ("boundary_needle", "boundary_flow", "beyond_needles", "beyond_order")


def chk_sides(p, d, c, codes, al):
    """Plan 0871 E2: `points` reads the geometry' of the interior points; `side` codes the points beyond a boundary; `side_row` is a
    total partition over (boundary needle, boundary flow, beyond needles, beyond order). Every key set is the declared alphabet it reads."""
    here, sig, pt, sd = Path(c.root, p).parent, codes["columns"]["signature"], d["points"], d["side"]
    out = shape(p, pt, {"reads": str, "code": dict, "rank": list}, pre="points.")
    out += shape(p, sd, {"needle_code": dict, "needle_rank": list, "order_code": dict, "order_rank": list, "ends": list}, pre="side.")
    out += when(al["lower"] != al["upper"], p, "alphabets.upper", "must equal alphabets.lower (one side alphabet)", "fix the list")
    probe, order = (load(here / f"{n}.toml", c.root) for n in ("probe", "order"))
    geom = (probe[0] or load(here / "geometry.toml", c.root)[0] or {}).get("verdicts", [])
    out += when(not order[0], p, "side", "needs order.toml in this set", "copy order.toml into the set")
    if out:
        return out
    needles = sig["needle"]["alphabet"]
    flows = sig["flow"]["alphabet"]
    ovals = [f"{o},{s}" for o in order[0]["values"] for s in [*sig["two_start"]["alphabet"], *c.alpha["nulls"]]]
    out += when(pt["reads"] != "geometry", p, "points.reads", "must be geometry (the axis value after the probe)", "fix it")
    out += same(p, "points.code", pt["code"], geom, "points.code keys = the geometry values of probe.toml")
    out += same(p, "points.rank", pt["rank"], al["points"], "points.rank")
    out += [at(p, f"points.code.{k}", f"'{v}' is not in alphabets.points", "use a value of that alphabet") for k, v in pt["code"].items() if v not in al["points"]]
    out += [at(p, "side.ends", f"'{x}' is not in alphabets.lower", "list side codes that name an end") for x in sd["ends"] if x not in al["lower"]]
    out += same(p, "side.needle_code", sd["needle_code"], needles, "side.needle_code keys = the needle alphabet")
    out += same(p, "side.needle_rank", sd["needle_rank"], [*c.alpha["nulls"], *set(sd["needle_code"].values()), "NONE"], "side.needle_rank (nulls, the codes, NONE for no point)")
    out += same(p, "side.order_code", sd["order_code"], ovals, "side.order_code keys = order value x two_start (nulls included)")
    out += same(p, "side.order_rank", sd["order_rank"], [*set(sd["order_code"].values()), "NONE"], "side.order_rank (the codes, NONE for no point)")
    dom = {"boundary_needle": [*needles, *c.alpha["nulls"]], "boundary_flow": [*flows, *c.alpha["nulls"]],
           "beyond_needles": sd["needle_rank"], "beyond_order": sd["order_rank"]}
    rows, _ = chk_rows(p, {**d, "verdicts": al["lower"]}, dom, "side_row")
    out += rows
    return out if out else chk_partition(p, list(SIDE_KEYS), [dom[x] for x in SIDE_KEYS], [r["when"] for r in d["side_row"]],
                                         Path(c.root, p).read_text(), key="side_row")


def chk_family_decl(p, d, c, stem=None):
    """A family declaration: an input, >= 2 interior points of it, and (when it declares a pair instrument) control edges."""
    import door
    out = list(todos(p, d))
    out = out or header(p, d, "family-decl") + shape(p, d, {"id": str, "input": str, "interior": (list, str)})
    out = out or id_check(p, "id", d["id"], stem, "the file name")
    if out:
        return out
    m, bad = load(c.root / "inputs" / d["input"] / "m.toml", c.root)
    if bad:
        return [at(p, "input", f"no input '{d['input']}'",
                   f"use one of: {' '.join(sorted(q.parent.name for q in (c.root / 'inputs').glob('*/m.toml')))}")]
    if isinstance(d["interior"], str):   # plan 0879: the interior is a declared rule (cc/family.py interior_of), not a list
        return inalpha(p, "interior", d["interior"], c.alpha["interior_rule"])
    if m.get("obtained") and set(m["obtained"].values()) == {"observed"}:   # nobody knows the interior of an all-observed record
        return [at(p, "interior", f"{d['input']} has only observed points, so a hand list would be written from the answer", 'use interior = "mid-run-open"')]
    pts, inner = m["axes"]["point"], d["interior"]
    out += when(len(inner) < 2, p, "interior", "a family needs at least two points", "list two or more points of the input")
    out += [at(p, "interior", f"'{x}' is not a point of {d['input']}", f"use points of {' '.join(pts)}") for x in inner if x not in pts]
    out += when(len(set(inner)) != len(inner), p, "interior", "a point is listed twice", "list each point once")
    out += when([x for x in pts if x in inner] != [x for x in inner if x in pts], p, "interior",
                "interior must follow the input's axes.point order", f"order: {' '.join(pts)}")
    pair = any(c.reg.get(i, {}).get("unit") == "pair" for i in m["instruments"])
    edges = {tuple(e) for e in door.control_pairs(m)} if pair else set()
    return out + [at(p, "interior", f"{a}->{b} is not an edge of {d['input']}'s relations.control",
                     "declare the control chain over these points, or drop the pair instrument")
                  for a, b in zip(inner, inner[1:]) if pair and (a, b) not in edges]


def feeding(allc, name):
    """The instruments a code column is derived from (through its helper columns)."""
    src = allc[name]["from"]
    return {src.partition(".")[0]} - {"declared"} if isinstance(src, str) else feeding(allc, src[0]) | feeding(allc, src[1])


def chk_membership(p, d, c, stem=None):
    """One section per instrument that runs door:off_manifold: which signature column it reads, and how its codes
    become membership, a rank and a door value. Keys are checked here, so a gap fails validate and never a run."""
    out = header(p, d, "membership")
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    if out or bad:
        return out + bad
    sig, allc, nulls = codes["columns"]["signature"], code_cols(codes), c.alpha["nulls"]
    for name, r in ((k, v) for k, v in d.items() if k not in ("schema", "kind")):
        loc, inst = name, c.reg.get(name, {})
        out += when(not {"door:off_manifold", "door:basis"} & set(inst.get("pipeline", [])), p, loc,
                    f"'{name}' is not a registry instrument with a door:off_manifold or door:basis step", "name such an instrument")
        e = shape(p, r, {"reads": str, "map": dict, "rank": list, "door": dict}, pre=loc + ".")
        if e or r["reads"] not in sig:
            out += e + when(not e, p, loc + ".reads", f"'{r['reads']}' is not a signature column", f"use one of: {' '.join(sig)}")
            continue
        want = list(sig[r["reads"]]["alphabet"]) + list(nulls)
        out += [at(p, loc + ".map", f"missing key '{k}'", f'add "{k}" = <membership>') for k in want if k not in r["map"]]
        out += [at(p, loc + ".map", f"foreign key '{k}'", "remove it") for k in r["map"] if k not in want]
        out += when(sorted(r["rank"]) != sorted(set(r["map"].values())), p, loc + ".rank",
                    "must list every membership value of map exactly once", "fix the list")
        out += when(set(r["door"]) != set(r["rank"]), p, loc + ".door", "keys must equal rank", "fix the keys")
        ok = {"RUN", "RUN-FLAG-U", *nulls, *inst.get("door_values", [])}
        out += [at(p, f"{loc}.door.{k}", f"'{v}' is not RUN, RUN-FLAG-U, a null or a door value of {name}",
                   f"use one of: {' '.join(sorted(ok))}") for k, v in r["door"].items() if v not in ok]
        out += [at(p, loc + ".reads", f"{name} must list '{i}' in requires (its codes feed '{r['reads']}')",
                   f"add {i} to requires in instruments/{name}.toml") for i in sorted(feeding(allc, r["reads"]))
                if i not in inst.get("requires", [])]
    return out


# ---------------------------------------------------------------- the axes: geometry, order, compose
def axis_cols(p, c):
    """(code column -> its alphabet followed by the nulls, findings): every helper and signature column an axis may read."""
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    return ({k: list(v["alphabet"]) + list(c.alpha["nulls"]) for k, v in code_cols(codes).items()} if codes else {}), bad


def chk_axis(p, d, c, kind, vals, extra):
    """geometry.toml or order.toml: the columns it reads, its values, and a partition of those columns' domain."""
    out = header(p, d, kind) + shape(p, d, {"columns": list, vals: list, "row": list, **extra}, {"class_of": dict})
    allc, bad = axis_cols(p, c)
    if out or bad:
        return out + bad
    cols = d["columns"]
    out += [at(p, "columns", f"'{x}' is not a code column of codes.toml {list(allc)}", "fix the list") for x in cols if x not in allc]
    if out:
        return out
    dom = {x: allc[x] for x in cols}
    rows, read = chk_rows(p, {**d, "verdicts": d[vals]}, dom)
    out += rows + [at(p, "columns", f"column '{x}' is not read by any row", "read it in a row or remove it") for x in cols if x not in read]
    return out if out else chk_partition(p, cols, [dom[x] for x in cols], [r["when"] for r in d["row"]], Path(c.root, p).read_text())


def chk_geometry(p, d, c, stem=None):
    return chk_axis(p, d, c, "geometry", "verdicts", {"refuse": list}) + (chk_classes(p, d, c) if "refuse" in d and "verdicts" in d else [])


def chk_probe(p, d, c, stem=None):
    """probe.toml (plan 0870): a total projection over (probe, geometry) -> geometry'. A refusal named here replaces a positive
    geometry that one probed direction cannot certify; every other cell is @geometry. A partition of the product of the two alphabets."""
    out = header(p, d, "probe") + shape(p, d, {"columns": list, "verdicts": list, "refuse": list, "row": list}, {"class_of": dict})
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    geo, bad2 = load(Path(c.root, p).parent / "geometry.toml", c.root)
    if out or bad or bad2 or "probe" not in (codes or {}).get("columns", {}).get("signature", {}):
        return out + bad + bad2 + when(not (out or bad or bad2), p, "columns", "codes.toml has no signature column 'probe'", "declare it in codes.toml")
    dom = {"probe": list(codes["columns"]["signature"]["probe"]["alphabet"]) + list(c.alpha["nulls"]), "geometry": list(geo["verdicts"])}
    out += same(p, "columns", d["columns"], ["probe", "geometry"], "columns")
    out += [at(p, "verdicts", f"geometry value '{x}' is not in verdicts", "list every geometry value (a pass-through is @geometry)") for x in geo["verdicts"] if x not in d["verdicts"]]
    rows, _ = chk_rows(p, {**d, "verdicts": [*d["verdicts"], "@geometry"]}, dom)
    out += rows + chk_classes(p, d, c)
    return out if out else chk_partition(p, ["probe", "geometry"], [dom["probe"], dom["geometry"]], [r["when"] for r in d["row"]], Path(c.root, p).read_text())


def scalar_keys(m, c):
    """The 0-d arrays (the sampler's parameters) the data files of an input hold, minus the size key: [] when none are stored."""
    keys = set()
    for path in sorted({c.data_root / b["path"] for b in m["data"]["files"]}):
        h = shapes_of(c, path) if path.is_file() else ()
        keys |= {k for k, shp in (h.items() if isinstance(h, dict) else []) if shp == ()}
    return sorted(keys - {SIZE_KEY})


def chk_couplings(p, d, c, stem=None):
    """inputs/<id>/couplings.toml (plan 0870): the sampler's free parameters, declared from the Hamiltonian, and the ones the per-point
    instruments probe. Checked against the scalars the data files store, so a declaration cannot choose its own verdict."""
    out = header(p, d, "couplings") + shape(p, d, {"id": str, "names": (list, str), "probes": list})
    out += id_check(p, "id", d.get("id"), stem, "its directory")
    m, bad = load(Path(c.root, p).parent / "m.toml", c.root)
    if out or bad:
        return out + bad
    names, probes, have = d["names"], d["probes"], scalar_keys(m, c)
    out += when(names != "unknown" and (not names or not all(isinstance(x, str) for x in names)), p, "names",
                "must be a list of coupling names, or the string unknown", 'write names = ["K"] or names = "unknown"')
    out += when(names == "unknown" and have, p, "names", f"unknown, but the data store the scalars {have}", f"declare names = {have}")
    out += when(isinstance(names, list) and have and sorted(names) != have, p, "names",
                f"must equal the scalars the data files store (minus {SIZE_KEY}): {have}", f"write names = {have}")
    out += [at(p, "probes", f"'{x}' is not a declared coupling", "probes must be a subset of names") for x in probes
            if isinstance(names, list) and x not in names]
    across = "across" in m["instruments"]
    ctl = m.get("relations", {}).get("control", {}).get("coupling")
    if "across_delta" in m["instruments"]:   # plan 0872 F2: a Delta over the control chain is across only when the chain moves the coupling across probes
        out += when(not across, p, "probes", "the input declares across_delta but not across (across_delta replaces across's reading, it does not replace the instrument)",
                    "add across to instruments in m.toml, or remove across_delta")
        out += when(ctl is None, p, "probes", "the input declares across_delta, a Delta over the control chain, but relations.control.coupling is not declared",
                    'write coupling = "<name>" in [relations.control] of m.toml: the coupling the control chain moves')
        out += when(ctl is not None and ctl not in probes, p, "probes", f"across_delta reads a chain over {ctl}, but across probes {probes}: the chain's coupling is not the probed coupling",
                    f"declare a control chain over a probed coupling ({', '.join(probes) or 'none declared'}), or remove across_delta from instruments in m.toml")
    out += when(across and names != "unknown" and not probes, p, "probes", "the input declares across, which probes a coupling", "name it in probes")
    out += when(not across and probes, p, "probes", "the input declares no across, so nothing is probed", "write probes = []")
    return out


def chk_order(p, d, c, stem=None):
    out = chk_axis(p, d, c, "order", "values", {"score": dict})
    sc, vals = d.get("score", {}), d.get("values", [])
    return out + same(p, "score", sc, vals, "score keys = the order values") + [
        at(p, f"score.{k}", f"'{v}' is not in {c.alpha['order_truth']} or REFUSE", "use one of those")
        for k, v in sc.items() if v not in [*c.alpha["order_truth"], "REFUSE"]]


def chk_compose(p, d, c, stem=None):
    """compose.toml: a partition of (geometry value x order value); a verdict of verdict.toml, or @geometry."""
    out = header(p, d, "compose") + shape(p, d, {"columns": list, "row": list})
    names = ("geometry", "order", "verdict") + ("probe",) * (Path(c.root, p).parent / "probe.toml").is_file()
    tabs = {n: load(Path(c.root, p).parent / f"{n}.toml", c.root) for n in names}
    if out or any(b for _, b in tabs.values()):
        return out + [f for _, b in tabs.values() for f in b]
    o, v = (tabs[n][0] for n in ("order", "verdict"))
    out += same(p, "columns", d["columns"], ["geometry", "order"], "columns")
    dom = {"geometry": tabs.get("probe", tabs["geometry"])[0].get("verdicts", []), "order": o.get("values", [])}   # with a probe projection, compose reads geometry'
    rows, read = chk_rows(p, {**d, "verdicts": [*v["verdicts"], "@geometry"]}, dom)
    out += rows + [at(p, "", f"geometry value '{x}' is not a verdict of verdict.toml", "fix geometry.toml") for x in dom["geometry"] if x not in v["verdicts"]]
    return out if out else chk_partition(p, ["geometry", "order"], [dom["geometry"], dom["order"]], [r["when"] for r in d["row"]], Path(c.root, p).read_text())


def table_values(d, dom, cols, key="verdict", vocab=None):
    """The array of every row's `key` over the product of `dom` (column -> alphabet) in the order of `cols`; with a `vocab`
    (name -> int, grown here) the values are int16 codes, which keeps a product of tens of millions of cells in memory."""
    owner = np.full([len(dom[x]) for x in cols], -1)
    for k, row in enumerate(d["row"]):
        owner[np.ix_(*[[dom[x].index(v) for v in row["when"].get(x, dom[x])] for x in cols])] = k
    vals = [r[key] for r in d["row"]]
    return (np.array(vals) if vocab is None else np.array([vocab.setdefault(x, len(vocab)) for x in vals], np.int16))[owner]


def lifted(arr, cols, full, dom):
    """`arr` (over `cols`) as an array over the columns `full`, broadcast along the columns it does not read."""
    arr = np.transpose(arr, np.argsort([full.index(x) for x in cols]))
    return arr.reshape([len(dom[x]) if x in cols else 1 for x in full])


def factorisation(root, tset):
    """(findings, rows proved): compose(geometry, order) equals verdict.toml's verdict on every row of the domain of the
    signature columns and every column an axis reads (a set with none of the three files has nothing to prove)."""
    t, nulls = Path(root) / "tables" / tset, tomllib.loads((Path(root) / "cc.toml").read_text())["alphabets"]["nulls"]
    have = [n for n in ("geometry", "order", "compose") if (t / f"{n}.toml").is_file()]
    pr = tomllib.loads((t / "probe.toml").read_text()) if (t / "probe.toml").is_file() else None
    at_ = f"tables/{tset}/compose.toml"
    if not have:
        return [], 0
    if len(have) < 3:
        return [at(at_, "", f"geometry, order and compose go together; this set has only {have}", "add the missing files, or remove these")], 0
    codes, v, g, o, cm = (parse((t / f).read_text()) for f in ("codes.toml", "verdict.toml", "geometry.toml", "order.toml", "compose.toml"))
    dom = {k: list(x["alphabet"]) + list(nulls) for k, x in code_cols(codes).items()}
    full, voc = v["columns"] + [x for x in dict.fromkeys(g["columns"] + o["columns"]) if x not in v["columns"]], {}
    cdom = {"geometry": pr["verdicts"] if pr else g["verdicts"], "order": o["values"]}
    pdom = {"probe": dom.get("probe", []), "geometry": g["verdicts"]}
    vv, gv, ov = (lifted(table_values(tb, dom, tb["columns"], vocab=voc), tb["columns"], full, dom) for tb in (v, g, o))
    pv = table_values(pr, pdom, ["probe", "geometry"], vocab=voc) if pr else None
    comp = table_values(cm, cdom, ["geometry", "order"], vocab=voc)
    names, keep = list(voc), voc.get("@geometry", -1)
    lut = lambda alpha: np.array([alpha.index(n) if n in alpha else 0 for n in names], np.int16)   # noqa: E731  vocabulary code -> index in `alpha`
    if pr:   # the probe projection: geometry' = (probe, geometry) -> @geometry or a refusal
        got_p = pv[lifted(np.arange(len(pdom["probe"]), dtype=np.int16), ["probe"], full, dom), lut(pdom["geometry"])[gv]]
        gv = np.where(got_p == keep, gv, got_p)
    c = comp[lut(cdom["geometry"])[gv], lut(cdom["order"])[ov]]
    got, vb = np.broadcast_arrays(np.where(c == keep, gv, c), vv)
    bad = got != vb
    if not bad.any():
        return [], int(vb.size)
    first = tuple(np.argwhere(bad)[0])
    cell = dict(zip(full, (dom[x][i] for x, i in zip(full, first))))
    return [at(at_, "", f"compose(geometry, order) differs from verdict.toml on {int(bad.sum())} of {int(vb.size)} rows, first: {cell} "
                        f"(composed {names[int(got[first])]}, verdict {names[int(vb[first])]})",
               "fix geometry.toml, order.toml or compose.toml so the factorisation holds on every row")], 0


KIND = {"membership": chk_membership, "case": chk_case, "points": chk_points, "input": chk_input, "instrument": chk_instrument,
        "codes": chk_codes, "verdict": chk_verdict, "data-manifest": chk_manifest, "cc": chk_cc,
        "family": chk_family, "family-decl": chk_family_decl, "geometry": chk_geometry, "order": chk_order,
        "compose": chk_compose, "probe": chk_probe, "couplings": chk_couplings,
        "transducer": chk_transducer, "record": chk_transducer}


def check_file(path, root=ROOT, ctx=None, **over):
    """Findings for one plugin file; `over` swaps cross-references (checks, data_root, codes, input). `ctx`: the Ctx a caller
    that checks many files builds once (it carries no `over`)."""
    c, path = ctx or Ctx(Path(root).resolve(), **over), Path(path)
    p = rel(path.resolve() if path.is_absolute() else path, c.root)
    real = c.root in path.resolve().parents and "planted" not in path.parts
    stem = (path.parent.name if path.name in ("m.toml", "points.toml", "couplings.toml", "transducer.toml") else path.stem) if real else None
    d, bad = load(path, c.root)
    if bad:
        return bad
    if d.get("kind") not in KIND:
        return [at(p, "", f"unknown kind '{d.get('kind')}'", f"use one of: {' '.join(KIND)}")]
    return KIND[d["kind"]](p, d, c, stem)


def validate(root=ROOT, input_id=None, tables=None):
    """Full validate, or the scoped one (cc.toml, one input, its instruments, one table set, its manifest).
    Read-only: ONE Ctx for the whole call, and each manifest-pinned file is hashed once."""
    root = Path(root).resolve()
    with hashing_once():
        return _validate(root, Ctx(root), input_id, tables)


def _validate(root, ctx, input_id, tables):
    sets = [tables] if tables else sorted(t.name for t in (root / "tables").glob("*") if t.is_dir())
    if input_id:
        m = root / "inputs" / input_id / "m.toml"
        names = (load(m, root)[0] or {}).get("instruments", [])
        files = [root / "cc.toml", m] + [root / "instruments" / f"{i}.toml" for i in names]
        files += [root / "fixtures" / "data" / f"{input_id}.toml"]
        tfiles = [root / "inputs" / input_id / "transducer.toml"]
    else:
        ins = sorted((root / "inputs").glob("*/m.toml"))
        files = [root / "cc.toml"] + ins + sorted((root / "instruments").glob("*.toml"))
        files += [root / "fixtures" / "data" / f"{m.parent.name}.toml" for m in ins]
        files += sorted(f for f in (root / "cases").glob("*.toml") if not f.name.startswith("TEMPLATE"))
        files += sorted((root / "inputs").glob("*/points.toml"))
        tfiles = [m.parent / "transducer.toml" for m in ins]
    files += [root / "tables" / s / f for s in sets for f in ("codes.toml", "verdict.toml")]
    files += [f for s in sets if not input_id for n in ("membership", "family") if (f := root / "tables" / s / f"{n}.toml").is_file()]
    files += [f for s in sets for n in ("geometry", "order", "probe", "compose") if (f := root / "tables" / s / f"{n}.toml").is_file()]
    files += [f for f in sorted((root / "inputs").glob("*/couplings.toml")) if not input_id or f.parent.name == input_id]
    files += sorted((root / "families").glob("*.toml")) if not input_id and (root / "families").is_dir() else []
    out, n = [], {}
    files += [f for f in tfiles if f.is_file()]
    out += [at(rel(f, root), "", "missing", f"copy inputs/TEMPLATE.transducer.toml.in to inputs/{f.parent.name}/transducer.toml and fill every TODO") for f in tfiles if not f.is_file()]   # plan 0883: total, a refusal never a skip
    for f in files:
        kind = (load(f, root)[0] or {}).get("kind", "?")
        n[kind] = n.get(kind, 0) + 1
        out += check_file(f, root, ctx)
    reads_decl = [s for s in sets if declared_cols((load(root / "tables" / s / "codes.toml", root)[0] or {"columns": {}}))]   # a set with a declared column needs every input's couplings.toml
    out += [at(f"inputs/{i}/couplings.toml", "", f"missing, and tables/{reads_decl[0]} reads a declared column",
               f"write it: kind = \"couplings\", id, names (from the Hamiltonian) and probes (which of them across probes)")
            for i in ([input_id] if input_id else sorted(q.parent.name for q in (root / "inputs").glob("*/m.toml")))
            if reads_decl and not (root / "inputs" / i / "couplings.toml").is_file()]
    if not out:
        out += [x for s in sets for x in factorisation(root, s)[0]]
    return out + (member_need(root, input_id, tables, ctx) if input_id and tables else []), n


def member_need(root, input_id, tset, ctx=None):
    """A table set must hold a valid membership rule for every declared instrument that runs door:off_manifold."""
    m, c = load(root / "inputs" / input_id / "m.toml", root)[0] or {}, ctx or Ctx(root)
    mp = root / "tables" / tset / "membership.toml"
    have = (load(mp, root)[0] or {}) if mp.is_file() else {}
    need = [n for n in m.get("instruments", []) if "door:off_manifold" in c.reg.get(n, {}).get("pipeline", [])]
    return [at(f"tables/{tset}/membership.toml", n, f"{n} runs door:off_manifold on {input_id} but this set has no rule for it",
               f"copy tables/v01-rules/membership.toml into tables/{tset}/, or fork from v01-rules (bin/cc tables fork v01-rules <new-name>)")
            for n in need if not isinstance(have.get(n), dict)] + (check_file(mp, root, ctx) if need and mp.is_file() else [])
