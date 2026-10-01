"""declare.py - plugin loaders, schemas, cross-references, the partition checker, validate (plumbing)."""
import hashlib
import itertools
import os
import re
import tomllib
from collections import namedtuple
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
F = namedtuple("F", "loc msg nxt soft", defaults=(False,))
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


def rel(p, root=ROOT):
    p = Path(p)
    return str(p.relative_to(root)) if p.is_absolute() and root in p.parents else str(p)


def tn(t):
    return "/".join(x.__name__ for x in (t if isinstance(t, tuple) else (t,)))


def load(p, root=ROOT):
    try:
        return tomllib.loads(Path(p).read_text()), []
    except (OSError, tomllib.TOMLDecodeError) as e:
        return None, [F(rel(p, root), f"cannot read: {e}", "fix the TOML syntax of this file")]


def shape(p, d, req, opt=None, pre=""):
    """Refuse missing, unknown and wrongly typed fields (schema/kind are checked by header)."""
    opt, out = opt or {}, []
    for k, t in {**req, **opt}.items():
        if k in d and not isinstance(d[k], t):
            out.append(F(f"{p}:{pre}{k}", f"must be {tn(t)}, found {type(d[k]).__name__}", f"edit {k} in {p}"))
    out += [F(f"{p}:{pre}{k}", "missing required field", f"add {k} = ... to {p}") for k in req if k not in d]
    out += [F(f"{p}:{pre}{k}", "unknown field", f"remove {k}, or check its spelling against the schema")
            for k in d if k not in req and k not in opt and not (pre == "" and k in ("schema", "kind"))]
    return out


def header(p, d, kind):
    if d.get("schema") != 1:
        return [F(p, f"schema {d.get('schema')} not supported for kind {kind} (supported: 1)", "set schema = 1")]
    return [] if d.get("kind") == kind else [F(p, f"kind is '{d.get('kind')}', expected '{kind}'",
                                                f'set kind = "{kind}"')]


def inalpha(p, field, v, alpha):
    ok = v == "TODO" or isinstance(v, (str, int, float)) and v in alpha
    return [] if ok else [F(f"{p}:{field}", f"'{v}' is not in {list(alpha)}", f"use one of: {' '.join(map(str, alpha))}")]


def todos(p, d, pre=""):
    for k, v in d.items():
        if v == "TODO":
            yield F(f"{p}:{pre}{k}", "still TODO", f"replace it with {HINT.get(k, 'the real value')}")
        elif isinstance(v, dict):
            yield from todos(p, v, f"{pre}{k}.")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if x == "TODO":
                    yield F(f"{p}:{pre}{k}[{i}]", "still TODO", f"replace it with {HINT.get(k, 'the real value')}")
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
        self.reg = {}
        for f in sorted((self.root / "instruments").glob("*.toml")):
            self.reg[f.stem] = load(f)[0] or {}
        self.checks = tomllib.loads(Path(over.get("checks") or self.root / "checks.toml").read_text())
        self.data_root = Path(over.get("data_root") or os.path.expanduser(self.cfg["data"]["root"]))
        self.alpha = self.cfg["alphabets"]

    def truths(self):
        return {f.stem: load_truth(f) for f in sorted((self.root / "cases").glob("*.toml"))}


# ---------------------------------------------------------------- cc.toml
def chk_cc(p, d, c, stem=None):
    out = header(p, d, "cc") + shape(p, d, {"defaults": dict, "data": dict, "alphabets": dict, "flags": dict, "obtained_flag": dict,
                       "arrays": dict, "basic": dict, "check": dict})
    if out:
        return out
    b, allf = d["basic"], set(RESULT_FIELDS)
    out += shape(p, b, {"keeps": list, "discards": list, "blank": list, "blank_refuse": bool, "commands": list},
                 pre="basic.")
    both = set(b.get("keeps", [])) & set(b.get("discards", []))
    got = set(b.get("keeps", [])) | set(b.get("discards", []))
    out += [F(f"{p}:basic", f"field '{x}' is in neither keeps nor discards", "add it to basic.keeps or basic.discards")
            for x in sorted(allf - got)]
    out += [F(f"{p}:basic", f"'{x}' is not a result field", "remove it from basic.keeps/discards")
            for x in sorted(got - allf)]
    out += [F(f"{p}:basic", f"field '{x}' is in both keeps and discards", "keep it in one list") for x in sorted(both)]
    ck = d["check"]
    out += shape(p, ck, {"fast_budget_s": int, "slow": list}, pre="check.")
    stems = {Path(t).stem for t in c.checks["roles"]["tests"]}
    return out + [F(f"{p}:check.slow", f"'{x}' is not a test in checks.toml", "name a test stem listed there")
                  for x in ck.get("slow", []) if x not in stems]


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
    out += [] if stem is None or d["id"] == stem else [F(f"{p}:id", f"id '{d['id']}' differs from the file name", f"set id = \"{stem}\"")]
    classes, truths = c.alpha["class_truth"], c.truths()
    out += inalpha(p, "class_truth", d["class_truth"], classes)
    dec = d["decoy_of"]
    out += [] if dec == "none" else inalpha(p, "decoy_of", dec, [x for x in classes if x != d["class_truth"]])
    nondecoy = {truths[k] for k in truths if k != d["id"]} if dec != "none" else set()
    out += [F(f"{p}:decoy_of", f"no non-decoy case has class {dec}", f"add a case of class {dec}, or set decoy_of = \"none\"")
            for _ in [0] if dec != "none" and dec not in nondecoy and dec in classes]
    out += inalpha(p, "status", d["status"], c.alpha["status"])
    out += [F(f"{p}:studies", f"status {d['status']} needs a non-empty studies list", "name the study sections")
            for _ in [0] if d["status"] in c.alpha["status"][1:] and not d["studies"]]
    out += [F(f"{p}:pairs_with", f"unknown case '{x}'", "name an existing case id")
            for x in d["pairs_with"] if x not in truths and x != d["id"]]
    return out + [F(f"{p}:sources", f"{s} does not exist", "fix the path") for s in d["sources"]
                  if not Path(os.path.expanduser(s)).is_file()]


def chk_points(p, d, c, stem=None):
    out = header(p, d, "points") + shape(p, d, {"input": str, "points": dict})
    if out:
        return out
    out = list(todos(p, d))
    out += [] if stem is None or d["input"] == stem else [F(f"{p}:input", f"input '{d['input']}' differs from its directory", f"set input = \"{stem}\"")]
    mp = c.over.get("input") or c.root / "inputs" / d["input"] / "m.toml"
    m, bad = load(mp, c.root)
    if bad:
        return out + bad
    pts, known = list(m["axes"]["point"]), set(c.truths()) | {"none"}
    out += [F(f"{p}:points.\"{x}\"", "point is not joined", f"add \"{x}\" = <case id or \"none\"> to [points]") for x in pts if x not in d["points"]]
    out += [F(f"{p}:points.\"{x}\"", f"{x} is not a point of {d['input']}", "remove it") for x in d["points"] if x not in pts]
    return out + [F(f"{p}:points.\"{k}\"", f"unknown case '{v}'",
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
    k = (str(path), key)
    if k not in c.shapes:
        z = np.load(path)
        c.shapes[k] = (z.shape, None) if isinstance(z, np.ndarray) else (z[key].shape if key in z.files else None, list(z.files))
    return c.shapes[k]


def chk_data(p, m, c):
    d, out, blocks = m["data"], [], {}
    out += shape(p, d, {"format": str, "files": list}, pre="data.")
    out += inalpha(p, "data.format", d.get("format"), c.alpha["formats"])
    ax, dims, lv = m["axes"], c.cfg["arrays"], m.get("observable", {}).get("levels")
    for i, b in enumerate(d.get("files", [])):
        loc = f"data.files[{i}]"
        e = shape(p, b, {"point": str, "size": int, "start": str, "path": str, "arrays": dict}, pre=loc + ".")
        if e:
            out += e
            continue
        key = (b["point"], b["size"], b["start"])
        out += [F(f"{p}:{loc}", f"duplicate block (point {key[0]}, size {key[1]}, start {key[2]})", "remove one of the two blocks")
                for _ in [0] if key in blocks]
        out += inalpha(p, loc + ".point", key[0], ax["point"]) + inalpha(p, loc + ".size", key[1], ax["size"])
        out += inalpha(p, loc + ".start", key[2], ax["starts"])
        blocks[key] = b["arrays"]
        fp = c.data_root / b["path"]
        if not fp.is_file():
            out.append(F(f"{p}:{loc}.path", f"{b['path']} does not exist under the data root", "fix the path, or put the file there"))
            continue
        for name, a in b["arrays"].items():
            out += [F(f"{p}:{loc}.arrays.{name}", f"array kind '{name}' is not in cc.toml [arrays]", f"use one of: {' '.join(dims)}")
                    for _ in [0] if name not in dims]
            e = shape(p, a, {"key": str}, {"level": int}, pre=f"{loc}.arrays.{name}.")
            if e or name not in dims:
                out += e
                continue
            shp, keys = stored(c, fp, a["key"])
            if shp is None:
                out.append(F(f"{p}:{loc}.arrays.{name}", f"key '{a['key']}' absent from {b['path']} (keys: {' '.join(keys)})", "fix the key"))
                continue
            got = len(shp) - ("level" in a and len(shp) == 2)
            if "level" in a and len(shp) == 1:
                out.append(F(f"{p}:{loc}.arrays.{name}", "level given on a 1-D stored array", "remove level"))
            elif got != dims[name]:
                out.append(F(f"{p}:{loc}.arrays.{name}", f"selects a {got}-D array but {name} is {dims[name]}-D in cc.toml [arrays]", "fix level"))
            elif lv and len(shp) == 2 and shp[1] != lv[ax["size"].index(b["size"])]:
                out.append(F(f"{p}:{loc}.arrays.{name}", f"stored levels {shp[1]} contradict observable.levels", "fix observable.levels"))
    for iname in m["instruments"]:
        inst = c.reg[iname]
        sizes, starts = unit_blocks(m, inst)
        for pt, sz, st, ar in itertools.product(ax["point"], sizes, starts, inst["arrays"]):
            if ar not in blocks.get((pt, sz, st), {}):
                out.append(F(f"{p}:data.files", f"{iname} needs array {ar} at (point {pt}, size {sz}, start {st})",
                             "add that [[data.files]] block"))
    return out


def chk_input(p, d, c, stem=None):
    todo = list(todos(p, d))
    if [t for t in todo if not t.loc.split(":", 1)[1].startswith("obtained")]:
        return todo   # a template still full of TODOs: report them, nothing else
    req = {"id": str, "instruments": list, "obtained": dict, "axes": dict, "interval": dict, "eps": dict,
           "kernel": dict, "data": dict}
    opt = {k: dict for k in SIDECARS + ("relations",)}
    out = header(p, d, "input") + shape(p, d, req, opt)
    out += [] if stem is None or d.get("id") == stem else [F(f"{p}:id", f"id '{d.get('id')}' differs from its directory", f'set id = "{stem}"')]
    bad = [i for i in d.get("instruments", []) if i not in c.reg]
    out += [F(f"{p}:instruments", f"'{i}' is not in the instrument registry", f"use one of: {' '.join(c.reg)}") for i in bad]
    ax = d.get("axes", {})
    out += shape(p, ax, {"point": list, "size": list, "starts": list, "main_start": str}, pre="axes.")
    if out:
        return todo + out
    sz = ax["size"]
    out += [F(f"{p}:axes.size", "sizes must be integers, strictly ascending", "fix the list")
            for _ in [0] if not (all(isinstance(x, int) for x in sz) and sz == sorted(set(sz)) and sz)]
    out += inalpha(p, "axes.main_start", ax["main_start"], ax["starts"])
    out += [F(f"{p}:obtained", f"keys differ from axes.point (missing {sorted(set(ax['point']) - set(d['obtained']))}, extra {sorted(set(d['obtained']) - set(ax['point']))})",
              "list every point once") for _ in [0] if set(d["obtained"]) != set(ax["point"])]
    for k, v in d["obtained"].items():
        out += inalpha(p, f"obtained.\"{k}\"", v, c.alpha["obtained"])
    use = [c.reg[i] for i in d["instruments"]]
    need = lambda key: {x for i in use for x in i[key]}  # noqa: E731
    for name in SIDECARS + ("relations",):
        want = name == "relations" and bool(need("relations")) or name in need("sidecar")
        out += [F(f"{p}:{name}", "missing required table (a declared instrument needs it)", f"add [{name}]")
                for _ in [0] if want and name not in d]
        out += [F(f"{p}:{name}", "table present but no declared instrument uses it", f"delete [{name}], or declare the instrument")
                for _ in [0] if not want and name in d]
    sc = {"observable": ({"name": str, "definition": str, "levels": list, "final_size": int}, {}),
          "block_map": ({"name": str, "factor": int, "keeps": str, "discards": str}, {}),
          "conjugate": ({"observable": str, "conjugate_to": str, "hamiltonian_knowledge": bool}, {}),
          "sinks": ({"ordered": NUM, "disordered": NUM}, {}),
          "two_start": ({"observable": str, "definition": str, "unit_scale": dict}, {})}
    for name, (r, o) in sc.items():
        out += shape(p, d[name], r, o, pre=f"{name}.") if name in d else []
    rels = d.get("relations", {})
    for rn in need("relations"):
        r = rels.get(rn)
        out += [F(f"{p}:relations.{rn}", "missing required relation", f"add [relations.{rn}]") for _ in [0] if r is None]
    for rn, r in rels.items():
        t = TEMPLATES.get(r.get("template"))
        if t is None:
            out.append(F(f"{p}:relations.{rn}.template", f"unknown template '{r.get('template')}'", f"use one of: {' '.join(TEMPLATES)}"))
            continue
        out += shape(p, r, {"template": str, "provenance": str, "direction_from": str, **t}, pre=f"relations.{rn}.")
        out += inalpha(p, f"relations.{rn}.provenance", r.get("provenance"), ("Coupling", "Continuation"))
    out += [F(f"{p}:relations", f"relation '{rn}' is not used by any declared instrument", "delete it") for rn in rels if rn not in need("relations")]
    want = {e for i in use for e in i["columns"].values()}
    out += [F(f"{p}:eps.{e}", "eps key missing (a declared instrument's column reads it)", f"add {e} = <margin> to [eps]") for e in sorted(want - set(d["eps"]))]
    out += [F(f"{p}:eps.{e}", "eps key not required by any declared instrument", f"delete {e}") for e in sorted(set(d["eps"]) - want)]
    out += [F(f"{p}:eps.{e}", "eps must be a number above 0", "set a positive margin") for e, v in d["eps"].items() if not (isinstance(v, NUM) and v > 0)]
    k = d["kernel"]
    out += shape(p, k, {"uses": list}, pre="kernel.")
    out += [F(f"{p}:kernel.uses", f"operators {sorted(need('operators') - set(k['uses']))} of declared instruments are not in kernel.uses", "add them")
            for _ in [0] if not need("operators") <= set(k.get("uses", []))]
    iv = d["interval"]
    out += shape(p, iv, {"method": str, "resamples": int, "level": NUM, "seed": int}, {"b": int, "tau_declared": int}, pre="interval.")
    out += inalpha(p, "interval.method", iv.get("method"), ("block", "iid"))
    out += [F(f"{p}:interval.b", "block resampling needs b", "add b = <block length>") for _ in [0] if iv.get("method") == "block" and "b" not in iv]
    out += [F(f"{p}:interval.tau_declared", "iid resampling needs tau_declared = 1", "add tau_declared = 1") for _ in [0] if iv.get("method") == "iid" and iv.get("tau_declared") != 1]
    return todo + (out if out else chk_data(p, d, c))


# ---------------------------------------------------------------- manifest, instrument, codes
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chk_manifest(p, d, c, stem=None):
    out = header(p, d, "data-manifest") + shape(p, d, {"input": str, "files": dict})
    if out:
        return out
    out += [] if stem is None or d["input"] == stem else [F(f"{p}:input", f"input '{d['input']}' differs from the file name", f'set input = "{stem}"')]
    m, bad = load(c.over.get("input") or c.root / "inputs" / d["input"] / "m.toml", c.root)
    if bad:
        return out + bad
    paths = {b["path"] for b in m["data"]["files"]}
    out += [F(f"{p}:files", f"{x} is used by the input but not pinned", f"bin/cc data add {d['input']}") for x in sorted(paths - set(d["files"]))]
    out += [F(f"{p}:files", f"{x} is pinned but the input does not use it", "delete the entry") for x in sorted(set(d["files"]) - paths)]
    return out + [F(p, f"{x} changed since it was pinned",
                    f"if intended, make a new input: bin/cc new input {d['input']}-2 --like {d['input']}, then bin/cc data add {d['input']}-2")
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
        for x in d[f]:
            out += inalpha(p, f, x, alpha)
    pl = d["pipeline"]
    out += [F(f"{p}:pipeline", "the first step must be stage:reduce", 'start the list with "stage:reduce"') for _ in [0] if pl[:1] != ["stage:reduce"]]
    mod, root = d["module"], c.root
    mp, dp = root / "cc" / "instruments" / f"{mod}.py", root / "cc" / "door.py"
    out += [F(f"{p}:module", f"'{mod}' is not under checks.toml [roles].maths", f'add "cc/instruments/{mod}.py" to [roles].maths', not mp.is_file())
            for _ in [0] if f"cc/instruments/{mod}.py" not in c.checks["roles"]["maths"]]
    taken = {f.stem for f in (root / "cc").glob("*.py")} | set(c.checks["allow"]["modules"]) | RESERVED
    out += [F(f"{p}:module", f"'{mod}' collides with a plumbing or allow-listed module name", "pick another module name") for _ in [0] if mod in taken]
    src, dsrc = (mp.read_text() if mp.is_file() else None), (dp.read_text() if dp.is_file() else "")
    out += [F(f"{p}:module", f"cc/instruments/{mod}.py does not exist", "write the module (phase 3)", True) for _ in [0] if src is None]
    for step in pl:
        kind, _, name = step.partition(":")
        text = src if kind == "stage" else dsrc
        out += [F(f"{p}:pipeline", f"unknown step '{step}'", "use stage:<name> or door:<name>") for _ in [0] if kind not in ("stage", "door")]
        out += [F(f"{p}:pipeline", f"{step}: no def {name}( in {'cc/instruments/' + mod + '.py' if kind == 'stage' else 'cc/door.py'}",
                  "write the function", True) for _ in [0] if kind in ("stage", "door") and text is not None and f"def {name}(" not in text]
    return out


def code_cols(d):
    return {**d["columns"].get("helper", {}), **d["columns"].get("signature", {})}


def doms(d, nulls):
    """column -> its alphabet followed by the nulls (the verdict domain)."""
    return {k: list(v["alphabet"]) + list(nulls) for k, v in d["columns"]["signature"].items()}


def chk_codes(p, d, c, stem=None):
    out = header(p, d, "codes") + shape(p, d, {"signs": list, "null_rank": list, "columns": dict})
    if out:
        return out
    out += [F(f"{p}:signs", f"must be sign.py's eight names {list(SIGNS)}", "restore the list") for _ in [0] if tuple(d["signs"]) != SIGNS]
    out += [F(f"{p}:null_rank", f"must equal cc.toml alphabets.nulls {c.alpha['nulls']}", "restore the list") for _ in [0] if d["null_rank"] != c.alpha["nulls"]]
    out += shape(p, d["columns"], {"signature": dict}, {"helper": dict}, pre="columns.")
    allc, nulls = code_cols(d), c.alpha["nulls"]
    for kind in ("helper", "signature"):
        for name, col in d["columns"].get(kind, {}).items():
            loc = f"columns.{kind}.{name}"
            e = shape(p, col, {"from": (str, list), "alphabet": list, "map": dict}, {"combine": dict}, pre=loc + ".")
            if e:
                out += e
                continue
            src, alpha = col["from"], col["alphabet"]
            if isinstance(src, str):
                i, _, k = src.partition(".")
                if k not in c.reg.get(i, {}).get("columns", {}):
                    out.append(F(f"{p}:{loc}.from", f"'{src}' is not a column of a registry instrument", "name <instrument>.<column>"))
                    continue
                want = list(SIGNS)
                needs = c.reg[i]["unit"] == "point-size"
            else:
                if len(src) != 2 or [x for x in src if x not in allc]:
                    out.append(F(f"{p}:{loc}.from", f"derived columns name two helper/signature columns, not {src}", "fix the list"))
                    continue
                want = [f"{a},{b}" for a, b in itertools.product(allc[src[0]].get("alphabet", []), allc[src[1]].get("alphabet", []))]
                needs = False
            mk = col["map"]
            out += [F(f"{p}:{loc}.map", f"missing key '{k}'", f"add \"{k}\" = <code>") for k in want if k not in mk]
            out += [F(f"{p}:{loc}.map", f"foreign key '{k}'" + (" (nulls are never keys)" if k in nulls else ""), "remove it") for k in mk if k not in want]
            out += [F(f"{p}:{loc}.map.\"{k}\"", f"'{v}' is not in the alphabet {alpha}", f"use one of: {' '.join(alpha)}") for k, v in mk.items() if v not in alpha]
            cb = col.get("combine")
            out += [F(f"{p}:{loc}.combine", "required for a point-size source" if needs else "only a point-size source combines", "fix") for _ in [0] if needs != (cb is not None)]
            if cb is not None:
                out += shape(p, cb, {"over": str, "rank": list}, pre=loc + ".combine.")
                out += [F(f"{p}:{loc}.combine.rank", f"must list {sorted(alpha + nulls)} exactly once each", "fix the list")
                        for _ in [0] if sorted(cb.get("rank", [])) != sorted(alpha + nulls)]
    return out


# ---------------------------------------------------------------- the partition
def patterns(free, cols, dom):
    """Compress a boolean array (True = to list) into boxes: widen the first cell column by column."""
    free, boxes = free.copy(), []
    while free.any():
        first = np.argwhere(free)[0]
        box = [[int(v)] for v in first]
        for ci in range(len(cols)):
            box[ci] = [v for v in range(len(dom[ci])) if free[np.ix_(*[box[j] if j != ci else sorted(set(box[ci]) | {v}) for j in range(len(cols))])].all()]
        free[np.ix_(*box)] = False
        boxes.append([(cols[ci], [dom[ci][v] for v in box[ci]]) for ci in range(len(cols)) if len(box[ci]) < len(dom[ci])])
    return boxes


def chk_partition(p, cols, dom, rows, text, limit=20):
    """Rows (list of dicts column -> allowed values) must be pairwise disjoint and cover the domain."""
    shp, out, lines = [len(x) for x in dom], [], row_lines(text)
    owner = np.full(shp, -1)
    for k, w in enumerate(rows):
        sub = np.ix_(*[[dom[ci].index(v) for v in w.get(col, dom[ci])] for ci, col in enumerate(cols)])
        prev, mk = owner[sub], np.zeros(shp, bool)
        mk[sub] = True
        for j in sorted(set(prev[prev >= 0].tolist())):
            both = mk & (owner == j)
            cell = [dom[ci][v] for ci, v in enumerate(np.argwhere(both)[0])]
            out.append(F(p, f"rows at lines {lines[j]} and {lines[k]} overlap on {int(both.sum())} cells, first: {dict(zip(cols, cell))}",
                         "narrow one of the two rows so they share no cell"))
        owner[sub] = k
    if (owner < 0).any():
        boxes = patterns(owner < 0, cols, dom)
        body = "".join("\n  [[row]]" + "".join(f"\n  when.{c} = {v}".replace("'", '"') for c, v in b) for b in boxes[:limit])
        more = f"\n  ... ({len(boxes) - limit} more patterns)" if len(boxes) > limit else ""
        out.append(F(p, f"{int((owner < 0).sum())} uncovered cells in {len(boxes)} patterns{body}{more}",
                     "add a [[row]] with one of these when-lines, or widen a neighbouring row"))
    return out


def chk_verdict(p, d, c, stem=None):
    req = {"columns": list, "ignores": list, "verdicts": list, "refuse": list, "row": list}
    out = header(p, d, "verdict") + shape(p, d, req, {"ignores_reason": str, "class_of": dict})
    if out:
        return out
    codes, bad = load(c.over.get("codes") or Path(c.root, p).parent / "codes.toml", c.root)
    if bad:
        return bad
    cols, dom = d["columns"], doms(codes, c.alpha["nulls"])
    text = Path(c.root, p).read_text()
    out += [F(f"{p}:columns", f"must equal the signature columns of codes.toml {list(dom)}", "fix the list") for _ in [0] if set(cols) != set(dom)]
    out += [F(f"{p}:ignores_reason", "required when ignores is not empty", "say why those columns are ignored") for _ in [0] if d["ignores"] and not d.get("ignores_reason")]
    out += [F(f"{p}:ignores", f"'{x}' is not a column", "fix the list") for x in d["ignores"] if x not in cols]
    classes, co, refuse = c.alpha["class_truth"], d.get("class_of", {}), set(d["refuse"])
    out += [F(f"{p}:refuse", f"'{x}' is not in verdicts", "list it in verdicts") for x in sorted(refuse - set(d["verdicts"]))]
    out += [F(f"{p}:class_of", f"'{x}' is both refusing and classed", "keep it in one") for x in sorted(refuse & set(co))]
    out += [F(f"{p}:class_of.{k}", f"'{v}' is not in {classes}", "use a class") for k, v in co.items() if v not in classes]
    out += [F(f"{p}:verdicts", f"verdict '{v}' is in none of refuse, class_of or the class names",
              "list it in refuse, add it to [class_of], or use a class name") for v in d["verdicts"] if v not in refuse and v not in co and v not in classes]
    if set(cols) != set(dom):
        return out
    read = set()
    for i, r in enumerate(d["row"]):
        e = shape(p, r, {"when": dict, "verdict": str, "why": str}, pre=f"row[{i}].")
        w = r.get("when", {})
        e += [F(f"{p}:row[{i}].when", f"unknown column '{k}'", "use a signature column") for k in w if k not in dom]
        e += [F(f"{p}:row[{i}].when.{k}", f"'{x}' is not in {dom[k]}", "use values of that column or the nulls") for k, v in w.items() if k in dom for x in v if x not in dom[k]]
        e += [F(f"{p}:row[{i}].verdict", f"'{r['verdict']}' is not in verdicts", "list it in verdicts") for _ in [0] if r.get("verdict") not in d["verdicts"]]
        e += [F(f"{p}:row[{i}].why", "empty", "say why this row gives this verdict") for _ in [0] if not r.get("why")]
        out += e
        read |= set(w)
    out += [F(f"{p}:columns", f"column '{x}' is neither read by a row nor in ignores", "read it in a row or add it to ignores") for x in cols if x not in read and x not in d["ignores"]]
    if out:
        return out
    return chk_partition(p, cols, [dom[x] for x in cols], [r["when"] for r in d["row"]], text)


KIND = {"case": chk_case, "points": chk_points, "input": chk_input, "instrument": chk_instrument,
        "codes": chk_codes, "verdict": chk_verdict, "data-manifest": chk_manifest, "cc": lambda p, d, c, stem=None: chk_cc(p, d, c)}


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
        return [F(p, f"unknown kind '{d.get('kind')}'", f"use one of: {' '.join(KIND)}")]
    return KIND[d["kind"]](p, d, c, stem)


def validate(root=ROOT, input_id=None, tables=None, soft_ok=False):
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
        d = load(f, root)[0] or {}
        n[d.get("kind", "?")] = n.get(d.get("kind", "?"), 0) + 1
        out += check_file(f, root)
    soft = [f for f in out if f.soft]
    return ([f for f in out if not f.soft] if soft_ok else out), soft, n
