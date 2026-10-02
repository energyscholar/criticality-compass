"""declare.py - plugin loaders, schemas, cross-references, the partition checker, validate (plumbing)."""
import hashlib
import itertools
import os
import tomllib
from collections import namedtuple
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
F = namedtuple("F", "loc msg nxt")
SIGNS = ("SIG-", "NEG", "SLOW-", "ZERO!", "SLOW+", "POS", "SIG+", "UNRES")
RESULT_FIELDS = (  # the result field set that cc.toml [basic] must partition (view.py reads it from here)
    "instrument", "unit", "column", "eps_key", "eps", "estimate", "lo", "hi", "cell", "code", "per_size",
    "flags", "reason", "vector_key", "point", "obtained", "verdict", "verdict_class", "row_line", "why",
    "read", "code_commit", "interval", "reports")
RESERVED = {"door", "declare", "author", "detect", "view", "score", "admit"}
SIDECARS = ("observable", "block_map", "conjugate", "sinks", "two_start")
TEMPLATES = {"chain": {"axis": str}, "pair": {"axis": str, "pairs": list},
             "matched": {"axis": str, "big": int, "small": int}}
HINT = {"family": "a short description of the model", "mechanism": "one sentence on what drives the transition"}
NUM = (int, float)


def fmt(f):
    return f"{f.loc}: {f.msg}\n  Next: {f.nxt}"


def at(p, field, msg, nxt):
    """One finding located at file:field (the file alone when field is empty)."""
    return F(f"{p}:{field}" if field else p, msg, nxt)


def when(cond, p, field, msg, nxt):
    return [at(p, field, msg, nxt)] if cond else []


def rel(p, root=ROOT):
    p = Path(p)
    return str(p.relative_to(root)) if p.is_absolute() and root in p.parents else str(p)


def tn(t):
    return "/".join(x.__name__ for x in (t if isinstance(t, tuple) else (t,)))


def load(p, root=ROOT):
    try:
        return tomllib.loads(Path(p).read_text()), []
    except (OSError, tomllib.TOMLDecodeError) as e:
        return None, [at(rel(p, root), "", f"cannot read: {e}", "fix the TOML syntax of this file")]


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
        hint = f"replace it with {HINT.get(k, 'the real value')}"
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


def row_lines(text):
    return [i + 1 for i, ln in enumerate(text.splitlines()) if ln.strip() == "[[row]]"]


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


class Ctx:
    """What the checks cross-reference: cc.toml, the registry, checks.toml, the data root (overridable)."""

    def __init__(self, root=ROOT, **over):
        self.root, self.over, self.shapes = Path(root), over, {}
        self.cfg = tomllib.loads((self.root / "cc.toml").read_text())
        self.reg = {f.stem: load(f)[0] or {} for f in sorted((self.root / "instruments").glob("*.toml"))}
        self.checks = tomllib.loads(Path(over.get("checks") or self.root / "checks.toml").read_text())
        self.data_root = Path(over.get("data_root") or os.path.expanduser(self.cfg["data"]["root"]))
        self.alpha = self.cfg["alphabets"]

    def truths(self):
        return {f.stem: load_truth(f) for f in sorted((self.root / "cases").glob("*.toml"))}


def id_check(p, field, got, want, what):
    """The id a file declares must be the name of its file or directory (skipped for planted files)."""
    return when(want is not None and got != want, p, field, f"{field} '{got}' differs from {what}",
                f'set {field} = "{want}"')


# ---------------------------------------------------------------- cc.toml
def chk_cc(p, d, c, stem=None):
    top = {k: dict for k in ("defaults", "data", "alphabets", "flags", "obtained_flag", "arrays", "basic", "check")}
    out = header(p, d, "cc") + shape(p, d, top)
    if out:
        return out
    b, keeps, discards = d["basic"], set(d["basic"].get("keeps", [])), set(d["basic"].get("discards", []))
    out += shape(p, b, {"keeps": list, "discards": list, "blank": list, "blank_refuse": bool, "commands": list},
                 pre="basic.")
    out += [at(p, "basic", f"field '{x}' is in neither keeps nor discards", "add it to basic.keeps or basic.discards")
            for x in sorted(set(RESULT_FIELDS) - keeps - discards)]
    out += [at(p, "basic", f"'{x}' is not a result field", "remove it from basic.keeps/discards")
            for x in sorted((keeps | discards) - set(RESULT_FIELDS))]
    out += [at(p, "basic", f"field '{x}' is in both keeps and discards", "keep it in one list")
            for x in sorted(keeps & discards)]
    out += shape(p, d["check"], {"fast_budget_s": int, "slow": list}, pre="check.")
    stems = {Path(t).stem for t in c.checks["roles"]["tests"]}
    return out + [at(p, "check.slow", f"'{x}' is not a test in checks.toml", "name a test stem listed there")
                  for x in d["check"].get("slow", []) if x not in stems]


# ---------------------------------------------------------------- cases and joins
def chk_case(p, d, c, stem=None):
    out = list(todos(p, d))
    if out:
        return out
    req = {"id": str, "family": str, "mechanism": str, "class_truth": str, "controls": dict, "observables": dict,
           "sampler": str, "traps": list, "sources": list, "decoy_of": str, "pairs_with": list, "status": str,
           "studies": list}
    out = header(p, d, "case") + shape(p, d, req, {"breaker_verdict": str, "blind_seal": str})
    if out:
        return out
    out += shape(p, d["controls"], {"names": list, "range": str}, pre="controls.")
    out += shape(p, d["observables"], {"list": list, "conjugate_observable": bool}, pre="observables.")
    out += id_check(p, "id", d["id"], stem, "the file name")
    classes, truths, dec = c.alpha["class_truth"], c.truths(), d["decoy_of"]
    out += inalpha(p, "class_truth", d["class_truth"], classes)
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
    pts, known = list(m["axes"]["point"]), set(c.truths()) | {"none"}
    out += [at(p, f'points."{x}"', "point is not joined", f'add "{x}" = <case id or "none"> to [points]')
            for x in pts if x not in d["points"]]
    out += [at(p, f'points."{x}"', f"{x} is not a point of {d['input']}", "remove it")
            for x in d["points"] if x not in pts]
    return out + [at(p, f'points."{k}"', f"unknown case '{v}'",
                     f'create it with bin/cc new case {v}, or map the point to an existing case or "none"')
                  for k, v in d["points"].items() if v not in known and v != "TODO"]


# ---------------------------------------------------------------- input (m.toml)
def unit_blocks(m, inst):
    """(sizes, starts) the instrument reads at every point: the matched pair, all sizes, the start pair."""
    rels, ax = m.get("relations", {}), m["axes"]
    sizes = [rels["matched"]["big"], rels["matched"]["small"]] if "matched" in inst["relations"] else list(ax["size"])
    pair = rels.get("start", {}).get("pairs", [[ax["main_start"]]])[0]
    return sizes, (list(pair) if "starts" in inst["axes"] else [ax["main_start"]])


def stored(c, path, key):
    """(shape of the stored array, None) or (None, the keys the file does hold); cached per file and key."""
    if (str(path), key) not in c.shapes:
        z = np.load(path)
        if isinstance(z, np.ndarray):
            c.shapes[(str(path), key)] = (z.shape, None)
        else:
            c.shapes[(str(path), key)] = (z[key].shape if key in z.files else None, list(z.files))
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
    shp, keys = stored(c, fp, a["key"])
    if shp is None:
        return out + [at(p, at_, f"key '{a['key']}' absent from {b['path']} (keys: {' '.join(keys)})", "fix the key")]
    got = len(shp) - ("level" in a and len(shp) == 2)
    if "level" in a and len(shp) == 1:
        return out + [at(p, at_, "level given on a 1-D stored array", "remove level")]
    if got != dims[name]:
        return out + [at(p, at_, f"selects a {got}-D array but {name} is {dims[name]}-D in cc.toml [arrays]", "fix level")]
    bad_levels = lv and name in LEVEL_STACKS and len(shp) == 2 and shp[1] != lv[ax["size"].index(b["size"])]
    return out + when(bad_levels, p, at_, f"stored levels {shp[-1]} contradict observable.levels", "fix observable.levels")


def chk_data(p, m, c):
    d, out, blocks, ax = m["data"], [], {}, m["axes"]
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
            out += chk_array(p, loc, name, a, b, fp, m, c)
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
        out += shape(p, r, {"template": str, "provenance": str, "direction_from": str, **t}, pre=f"relations.{rn}.")
        out += inalpha(p, f"relations.{rn}.provenance", r.get("provenance"), ("Coupling", "Continuation"))
        if r["template"] == "matched" and "observable" in d and {r.get("big"), r.get("small")} <= set(sz):
            lb, ls = (d["observable"]["levels"][sz.index(r[k])] for k in ("big", "small"))
            out += when(ls != lb - 1, p, f"relations.{rn}",
                        f"matched needs small levels = big levels - 1 (found {ls} and {lb})",
                        "fix observable.levels or the sizes")
    return out + [at(p, "relations", f"relation '{rn}' is not used by any declared instrument", "delete it")
                  for rn in rels if rn not in need]


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
        out += shape(p, d[name], SIDECAR_SHAPE[name], pre=f"{name}.") if name in d else []
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
    out += shape(p, iv, {"method": str, "resamples": int, "level": NUM, "seed": int},
                 {"b": int, "tau_declared": int}, pre="interval.")
    out += inalpha(p, "interval.method", iv.get("method"), ("block", "iid"))
    out += when(iv.get("method") == "block" and "b" not in iv, p, "interval.b", "block resampling needs b",
                "add b = <block length>")
    out += when(iv.get("method") == "iid" and iv.get("tau_declared") != 1, p, "interval.tau_declared",
                "iid resampling needs tau_declared = 1", "add tau_declared = 1")
    return todo + (out if out else chk_data(p, d, c))


# ---------------------------------------------------------------- manifest, instrument, codes
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    req = {"module": str, "operators": list, "unit": str, "reports": list, "arrays": list, "axes": list,
           "relations": list, "sidecar": list, "flags": list, "pipeline": list, "columns": dict}
    out = header(p, d, "instrument") + shape(p, d, req)
    if out:
        return out
    out += inalpha(p, "unit", d["unit"], ("point", "point-size"))
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
    for step in pl:
        kind, _, name = step.partition(":")
        text, where = (src, f"cc/instruments/{mod}.py") if kind == "stage" else (dp.read_text() if dp.is_file() else "", "cc/door.py")
        out += when(kind not in ("stage", "door"), p, "pipeline", f"unknown step '{step}'",
                    "use stage:<name> or door:<name>")
        out += when(kind in ("stage", "door") and text is not None and f"def {name}(" not in text, p, "pipeline",
                    f"{step}: no def {name}( in {where}", "write the function")
    return out


def code_cols(d):
    return {**d["columns"].get("helper", {}), **d["columns"].get("signature", {})}


def doms(d, nulls):
    """column -> its alphabet followed by the nulls (the verdict domain)."""
    return {k: list(v["alphabet"]) + list(nulls) for k, v in d["columns"]["signature"].items()}


def chk_column(p, loc, col, c, allc):
    """One code column: where it comes from, its map (total, no foreign values) and its combine rule."""
    e = shape(p, col, {"from": (str, list), "alphabet": list, "map": dict}, {"combine": dict}, pre=loc + ".")
    if e:
        return e
    src, alpha, nulls = col["from"], col["alphabet"], c.alpha["nulls"]
    if isinstance(src, str):
        inst, _, column = src.partition(".")
        if column not in c.reg.get(inst, {}).get("columns", {}):
            return [at(p, loc + ".from", f"'{src}' is not a column of a registry instrument",
                       "name <instrument>.<column>")]
        want, needs = list(SIGNS), c.reg[inst]["unit"] == "point-size"
    else:
        if len(src) != 2 or [x for x in src if x not in allc]:
            return [at(p, loc + ".from", f"derived columns name two helper/signature columns, not {src}",
                       "fix the list")]
        want = [f"{a},{b}" for a, b in itertools.product(*(allc[x].get("alphabet", []) for x in src))]
        needs = False
    mk, cb = col["map"], col.get("combine")
    out = [at(p, loc + ".map", f"missing key '{k}'", f'add "{k}" = <code>') for k in want if k not in mk]
    out += [at(p, loc + ".map", f"foreign key '{k}'" + (" (nulls are never keys)" if k in nulls else ""), "remove it")
            for k in mk if k not in want]
    out += [at(p, f'{loc}.map."{k}"', f"'{v}' is not in the alphabet {alpha}", f"use one of: {' '.join(alpha)}")
            for k, v in mk.items() if v not in alpha]
    out += when(needs != (cb is not None), p, loc + ".combine",
                "required for a point-size source" if needs else "only a point-size source combines", "fix")
    if cb is not None:
        out += shape(p, cb, {"over": str, "rank": list}, pre=loc + ".combine.")
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


def chk_partition(p, cols, dom, rows, text, limit=20):
    """Rows (list of dicts column -> allowed values) must be pairwise disjoint and cover the domain."""
    shp, out, lines = [len(x) for x in dom], [], row_lines(text)
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
        body = "".join("\n  [[row]]" + "".join(f"\n  when.{c} = {v}".replace("'", '"') for c, v in b)
                       for b in boxes[:limit])
        more = f"\n  ... ({len(boxes) - limit} more patterns)" if len(boxes) > limit else ""
        out.append(at(p, "", f"{int((owner < 0).sum())} uncovered cells in {len(boxes)} patterns{body}{more}",
                      "add a [[row]] with one of these when-lines, or widen a neighbouring row"))
    return out


def chk_rows(p, d, dom):
    """Every row: known columns, values inside each column's domain, a listed verdict, a why."""
    out, read = [], set()
    for i, r in enumerate(d["row"]):
        loc, w = f"row[{i}]", r.get("when", {})
        out += shape(p, r, {"when": dict, "verdict": str, "why": str}, pre=loc + ".")
        out += [at(p, loc + ".when", f"unknown column '{k}'", "use a signature column") for k in w if k not in dom]
        out += [at(p, f"{loc}.when.{k}", f"'{x}' is not in {dom[k]}", "use values of that column or the nulls")
                for k, v in w.items() if k in dom for x in v if x not in dom[k]]
        out += when(r.get("verdict") not in d["verdicts"], p, loc + ".verdict",
                    f"'{r.get('verdict')}' is not in verdicts", "list it in verdicts")
        out += when(not r.get("why"), p, loc + ".why", "empty", "say why this row gives this verdict")
        read |= set(w)
    return out, read


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
    classes, co, refuse = c.alpha["class_truth"], d.get("class_of", {}), set(d["refuse"])
    out += [at(p, "refuse", f"'{x}' is not in verdicts", "list it in verdicts") for x in sorted(refuse - set(d["verdicts"]))]
    out += [at(p, "class_of", f"'{x}' is both refusing and classed", "keep it in one") for x in sorted(refuse & set(co))]
    out += [at(p, f"class_of.{k}", f"'{v}' is not in {classes}", "use a class") for k, v in co.items() if v not in classes]
    out += [at(p, "verdicts", f"verdict '{v}' is in none of refuse, class_of or the class names",
               "list it in refuse, add it to [class_of], or use a class name")
            for v in d["verdicts"] if v not in refuse and v not in co and v not in classes]
    if set(cols) != set(dom):
        return out
    rows, read = chk_rows(p, d, dom)
    out += rows
    out += [at(p, "columns", f"column '{x}' is neither read by a row nor in ignores",
               "read it in a row or add it to ignores") for x in cols if x not in read and x not in d["ignores"]]
    return out if out else chk_partition(p, cols, [dom[x] for x in cols], [r["when"] for r in d["row"]], text)


KIND = {"case": chk_case, "points": chk_points, "input": chk_input, "instrument": chk_instrument,
        "codes": chk_codes, "verdict": chk_verdict, "data-manifest": chk_manifest, "cc": chk_cc}


def check_file(path, root=ROOT, **over):
    """Findings for one plugin file; `over` swaps cross-references (checks, data_root, codes, input)."""
    c, path = Ctx(Path(root).resolve(), **over), Path(path)
    p = rel(path.resolve() if path.is_absolute() else path, c.root)
    real = c.root in path.resolve().parents and "planted" not in path.parts
    stem = (path.parent.name if path.name in ("m.toml", "points.toml") else path.stem) if real else None
    d, bad = load(path, c.root)
    if bad:
        return bad
    if d.get("kind") not in KIND:
        return [at(p, "", f"unknown kind '{d.get('kind')}'", f"use one of: {' '.join(KIND)}")]
    return KIND[d["kind"]](p, d, c, stem)


def validate(root=ROOT, input_id=None, tables=None):
    """Full validate, or the scoped one (cc.toml, one input, its instruments, one table set, its manifest)."""
    root = Path(root).resolve()
    sets = [tables] if tables else sorted(t.name for t in (root / "tables").glob("*") if t.is_dir())
    if input_id:
        m = root / "inputs" / input_id / "m.toml"
        names = (load(m, root)[0] or {}).get("instruments", [])
        files = [root / "cc.toml", m] + [root / "instruments" / f"{i}.toml" for i in names]
        files += [root / "fixtures" / "data" / f"{input_id}.toml"]
    else:
        ins = sorted((root / "inputs").glob("*/m.toml"))
        files = [root / "cc.toml"] + ins + sorted((root / "instruments").glob("*.toml"))
        files += [root / "fixtures" / "data" / f"{m.parent.name}.toml" for m in ins]
        files += sorted(f for f in (root / "cases").glob("*.toml") if not f.name.startswith("TEMPLATE"))
        files += sorted((root / "inputs").glob("*/points.toml"))
    files += [root / "tables" / s / f for s in sets for f in ("codes.toml", "verdict.toml")]
    out, n = [], {}
    for f in files:
        kind = (load(f, root)[0] or {}).get("kind", "?")
        n[kind] = n.get(kind, 0) + 1
        out += check_file(f, root)
    return out, n
