"""author.py - the commands that write plugin files: new case/input, data add, tables fork/drop/split."""
import json
import re
import shutil
import tomllib
from datetime import date
from pathlib import Path
import declare


class Was(str):
    """A path this tool refused to guess: written as "TODO" with a comment naming the old value."""
    old = ""


def key(k):
    return k if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", k) else json.dumps(k)


def wrap(items, width, first="", sep=" "):
    """Greedy fill: join items with `sep` into lines of at most `width` characters."""
    lines, cur = [], first
    for it in items:
        if cur.strip() and len(cur) + len(sep) + len(it) > width:
            lines, cur = lines + [cur], first + it
        else:
            cur = (cur + sep + it) if cur.strip() else first + it
    return lines + [cur]


def scal(v):
    """One TOML value; long strings become wrapped multi-line strings, long lists one group per line."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Was):
        return f'"TODO"   # was {v.old}'
    if isinstance(v, str):
        if len(v) <= 80:
            return json.dumps(v)
        return '"""' + " \\\n".join(wrap(json.dumps(v)[1:-1].split(" "), 76)) + '"""'
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{key(k)} = {scal(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        items = [scal(x) for x in v]
        if len(", ".join(items)) < 85:
            return "[" + ", ".join(items) + "]"
        return "[\n" + "\n".join(wrap([it + "," for it in items], 96, "  ")) + "\n]"
    return repr(v)


def small(v):
    return isinstance(v, dict) and len(v) <= 3 and not any(isinstance(x, (dict, list)) for x in v.values())


def aot(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v)


def block(item):
    """The lines of one [[array-of-tables]] entry: nested maps become dotted keys."""
    out = []
    for k, x in item.items():
        if isinstance(x, dict):
            out += [f"{key(k)}.{key(k2)} = {scal(y)}" for k2, y in x.items()]
        else:
            out.append(f"{key(k)} = {scal(x)}")
    return out


def dump(d, path=""):
    """TOML lines for a nested dict in vertical form (scalars, small inline tables, sub-tables, [[blocks]])."""
    inline = lambda v: not aot(v) and (not isinstance(v, dict) or (small(v) and path))  # noqa: E731
    out = [f"{key(k)} = {scal(v)}" for k, v in d.items() if inline(v)]
    for k, v in d.items():
        name = f"{path}.{key(k)}" if path else key(k)
        if aot(v):
            for item in v:
                out += ["", f"[[{name}]]"] + block(item)
        elif isinstance(v, dict) and not inline(v):
            direct = [x for x in v.values() if not aot(x) and (not isinstance(x, dict) or small(x))]
            out += ([""] + [f"[{name}]"] if direct else []) + dump(v, name)
    return out


def text_of(header, d):
    return header + "\n".join(dump(d)).lstrip("\n") + "\n"


def refuse(msg, nxt):
    print(f"{msg}\n  Next: {nxt}")
    return 1


def new_case(root, cid):
    p = Path(root) / "cases" / f"{cid}.toml"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid):
        return refuse(f"'{cid}' is not a case id (lower-case letters, digits, hyphens).", "bin/cc new case potts-q4")
    if p.exists():
        return refuse(f"cases/{cid}.toml already exists.", "edit it, or pick another id")
    p.write_text((Path(root) / "cases" / "TEMPLATE.toml.in").read_text().replace("<ID>", cid))
    print(f"wrote cases/{cid}.toml\n  Next: fill every TODO in cases/{cid}.toml, map points to it in "
          "inputs/<input>/points.toml, then bin/cc validate")
    return 0


def repoint(m, labels, pat):
    """Give the blocks of the pattern point to every new label; a file name is renamed only when unambiguous."""
    new = []
    for lab in labels:
        for b in [b for b in m["data"]["files"] if b["point"] == pat]:
            head, _, name = b["path"].rpartition("/")
            path = head + "/" + name.replace(pat, lab) if name.count(pat) == 1 else Was("TODO")
            if isinstance(path, Was):
                path.old = b["path"]
            new.append({**b, "point": lab, "path": path})
    m["data"]["files"], m["axes"]["point"] = new, labels
    m["obtained"] = {x: "TODO" for x in labels}


def restrict(m, keep, reg):
    """Keep only the instruments `keep`, and drop the tables, relations and eps keys nothing else needs."""
    use = [reg[i] for i in keep]
    m["instruments"] = keep
    for k in declare.SIDECARS:
        if k in m and not any(k in i["sidecar"] for i in use):
            del m[k]
    rels = {k: v for k, v in m.pop("relations", {}).items() if any(k in i["relations"] for i in use)}
    m.update({"relations": rels} if rels else {})
    m["eps"] = {k: v for k, v in m["eps"].items() if k in {e for i in use for e in i["columns"].values()}}


def retarget(m, data_dir, fmt):
    """Point every data block at --data-dir and/or name its file by --label-format; a TODO stays TODO unless fmt names it."""
    for b in m["data"]["files"]:
        old = b["path"].old if isinstance(b["path"], Was) else b["path"]
        head, _, name = old.rpartition("/")
        if isinstance(b["path"], Was) and not fmt:
            continue
        name = fmt.format(label=b["point"], size=b["size"], start=b["start"]) if fmt else name
        b["path"] = f"{data_dir or head}/{name}"


def blank(t):
    """The TODO form of a schema type: a list, a table or a scalar."""
    return ["TODO"] if t is list else {"TODO": "TODO"} if t is dict else "TODO"


def add_instruments(m, ids, reg):
    """Declare more instruments: write the sidecar tables, relations, eps keys and arrays they need as TODOs."""
    for i in ids:
        inst = reg[i]
        m["instruments"] = m["instruments"] + [i] * (i not in m["instruments"])
        for k in inst["sidecar"]:
            m.setdefault(k, {f: blank(t) for f, t in declare.SIDECAR_SHAPE[k].items()})
        for r in inst["relations"]:
            m.setdefault("relations", {}).setdefault(
                r, {"template": "TODO", "axis": "TODO", "provenance": "TODO", "direction_from": "TODO"})
        for e in inst["columns"].values():
            m["eps"].setdefault(e, "TODO")
        m["kernel"]["uses"] = sorted(set(m["kernel"]["uses"]) | set(inst["operators"]))
        for b in m["data"]["files"]:
            for a in inst["arrays"]:
                b["arrays"].setdefault(a, {"key": "TODO"})


def new_input(root, iid, like=None, points=None, pattern=None, instruments=None, data_dir=None, fmt=None, add=None):
    root = Path(root)
    d, ins = root / "inputs" / iid, root / "inputs"
    if d.exists():
        return refuse(f"inputs/{iid} already exists.", "pick another id")
    if like is None:
        d.mkdir()
        (d / "m.toml").write_text((ins / "TEMPLATE.m.toml.in").read_text().replace("<ID>", iid))
        (d / "points.toml").write_text((ins / "TEMPLATE.points.toml.in").read_text().replace("<ID>", iid))
        (d / "transducer.toml").write_text((ins / "TEMPLATE.transducer.toml.in").read_text().replace("<ID>", iid))
        print(f"wrote inputs/{iid}/m.toml, points.toml and transducer.toml\n  Next: replace every TODO, add the [[data.files]] "
              f"blocks, then bin/cc data add {iid} and bin/cc validate")
        return 0
    src, reg = ins / like / "m.toml", declare.Ctx(root).reg
    if not src.is_file():
        names = " ".join(sorted(p.parent.name for p in ins.glob("*/m.toml")))
        return refuse(f"no input '{like}'.", f"bin/cc new input {iid} --like <one of: {names}>")
    unknown = [i for i in (instruments or "").split(",") + (add or "").split(",") if i and i not in reg]
    if unknown:
        return refuse(f"'{unknown[0]}' is not in the instrument registry.",
                      f"use --instruments / --add-instrument <some of: {' '.join(reg)}>")
    try:
        fmt and fmt.format(label="", size=0, start="")
    except (KeyError, IndexError, ValueError):
        return refuse(f"--label-format '{fmt}' may use only {{label}}, {{size}} and {{start}}.",
                      "bin/cc new input x --like y --label-format 'd{label}-L{size}.npz'")
    text = src.read_text()
    m = tomllib.loads(text)
    m["id"] = iid
    if points:
        repoint(m, points.split(","), pattern or m["axes"]["point"][-1])
    if instruments:
        restrict(m, instruments.split(","), reg)
    if data_dir or fmt:
        retarget(m, data_dir, fmt)
    if add:
        add_instruments(m, [i for i in add.split(",") if i], reg)
    head = "\n".join(text.splitlines()[:2]) + f"\n# inputs/{iid}/m.toml - like {like}\n"
    changed = bool(points or instruments or data_dir or fmt or add)
    body = text_of(head, m) if changed else re.sub(r'^id = ".*"$', f'id = "{iid}"', text, flags=re.M)
    d.mkdir()
    (d / "m.toml").write_text(body)
    pts = "\n".join(f'"{p}" = "TODO"' for p in m["axes"]["point"])
    (d / "points.toml").write_text(
        f"# inputs/{iid}/points.toml - the point -> case JOIN (taxonomy; never frozen)\n"
        f'schema = 1\nkind = "points"\ninput = "{iid}"\n\n[points]\n{pts}\n')
    (d / "transducer.toml").write_text((ins / "TEMPLATE.transducer.toml.in").read_text().replace("<ID>", iid))   # provenance is not inherited: --like never copies the like-input's file
    print(f"wrote inputs/{iid}/m.toml, points.toml and transducer.toml (like {like})\n"
          f"  Next: fix every TODO, then bin/cc data add {iid} and bin/cc validate")
    return 0


def new_instrument(root, iid):
    """instruments/<id>.toml from the template and the stub cc/instruments/<id>.py; both refuse to validate until finished."""
    root = Path(root)
    taken = {f.stem for f in (root / "cc").glob("*.py")} | set(declare.Ctx(root).checks["allow"]["modules"]) | declare.RESERVED
    if not re.fullmatch(r"[a-z][a-z0-9_]*", iid):
        return refuse(f"'{iid}' is not an instrument id (lower-case letters, digits, underscores: it names a module).",
                      "bin/cc new instrument eta")
    if iid in taken:
        return refuse(f"'{iid}' would shadow a plumbing or allow-listed module (a bare import would find it).",
                      "pick another id")
    toml, stub = root / "instruments" / f"{iid}.toml", root / "cc" / "instruments" / f"{iid}.py"
    if toml.exists() or stub.exists():
        return refuse(f"instruments/{iid}.toml or cc/instruments/{iid}.py already exists.", "pick another id")
    toml.write_text((root / "instruments" / "TEMPLATE.toml.in").read_text().replace("<ID>", iid))
    stub.write_text((root / "instruments" / "TEMPLATE.py.in").read_text().replace("<ID>", iid))
    print(f"wrote instruments/{iid}.toml and cc/instruments/{iid}.py\n"
          f'  add this line to checks.toml [roles].maths: "cc/instruments/{iid}.py"\n'
          f"  Next: replace every TODO in instruments/{iid}.toml, write the stages and delete the TODO-STAGE "
          f"marker, then bin/cc validate (bin/cc run refuses until it is clean)")
    return 0


def new_family(root, fid):
    """families/<id>.toml from the template; validate refuses it until every TODO is replaced."""
    root, p = Path(root), Path(root) / "families" / f"{fid}.toml"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", fid):
        return refuse(f"'{fid}' is not a family id (lower-case letters, digits, hyphens).", "bin/cc new family b7-at-line-2")
    if p.exists():
        return refuse(f"families/{fid}.toml already exists.", "edit it, or pick another id")
    p.write_text((root / "families" / "TEMPLATE.toml.in").read_text().replace("<ID>", fid))
    print(f"wrote families/{fid}.toml\n  Next: replace every TODO (an input and its interior points), then bin/cc validate "
          f"and bin/cc family {fid}")
    return 0


def data_add(root, iid):
    root = Path(root)
    p, c = root / "fixtures" / "data" / f"{iid}.toml", declare.Ctx(root)
    m, bad = declare.load(root / "inputs" / iid / "m.toml", root)
    if bad:
        return refuse(bad[0].msg, f"bin/cc new input {iid}")
    if p.exists():
        return refuse(f"fixtures/data/{iid}.toml already exists.",
                      "delete it first if it is unfrozen and you mean to re-pin")
    paths = list(dict.fromkeys(b["path"] for b in m["data"]["files"]))
    gone = [x for x in paths if not c.file(x).is_file()]
    if gone:
        return refuse(f"inputs/{iid}/m.toml: {len(gone)} data files do not exist under the data root, "
                      f"first: {gone[0]}", f"fix the paths in [[data.files]], then bin/cc data add {iid}")
    head = f"# fixtures/data/{iid}.toml - written by bin/cc data add: sha256 of every data file\n"
    pins = {x: declare.sha(c.file(x)) for x in paths}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text_of(head, {"schema": 1, "kind": "data-manifest", "input": iid, "files": pins}))
    print(f"pinned {len(paths)} files in fixtures/data/{iid}.toml\n  Next: bin/cc validate")
    return 0


def frozen(root):
    f = Path(root) / "FROZEN.json"
    fz = json.loads(f.read_text()) if f.is_file() else {"files": {}, "dirs": {}}
    return set(fz["files"]), set(fz["dirs"])


def sets_of(root):
    return sorted(t.name for t in (Path(root) / "tables").glob("*") if t.is_dir())


def unknown_set(root, name, nxt):
    return refuse(f"no table set '{name}'. Sets: {' '.join(sets_of(root))}", nxt)


def fork(root, src, dst):
    root = Path(root)
    if src not in sets_of(root):
        return unknown_set(root, src, "bin/cc tables fork <one of these> <new-name>")
    if (root / "tables" / dst).exists():
        return refuse(f"tables/{dst} already exists.", f"pick another name, or bin/cc tables drop {dst} first")
    shutil.copytree(root / "tables" / src, root / "tables" / dst)
    for p in [root / "tables" / dst, *(root / "tables" / dst).rglob("*")]:
        p.chmod(0o755 if p.is_dir() else 0o644)
    print(f"forked tables/{src} to tables/{dst}\n  Next: edit tables/{dst}/verdict.toml, then bin/cc validate, "
          f"then bin/cc run --all --tables {dst}")
    return 0


def drop(root, name, with_results):
    root = Path(root)
    if name not in sets_of(root):
        return unknown_set(root, name, "bin/cc tables drop <one of these>")
    if declare.Ctx(root).cfg["defaults"]["tables"] == name:
        return refuse(f"REFUSED: tables/{name} is the default rulebook (cc.toml [defaults] tables).",
                      "change [defaults] tables in cc.toml first, or drop another set")
    files, dirs = frozen(root)
    res = sorted((root / "results").glob(f"*@{name}.*")) if (root / "results").is_dir() else []
    names = [str(r.relative_to(root)) for r in res]
    if f"tables/{name}" in dirs:
        return refuse(f"REFUSED: tables/{name} is frozen (results depend on it).",
                      "nothing to do; a frozen rulebook stays. Fork it to change it.")
    if res and not with_results:
        return refuse(f"tables/{name} has results: {' '.join(names)}", f"bin/cc tables drop {name} --with-results")
    hit = [n for n in names if n in files]
    if hit:
        return refuse(f"REFUSED: {hit[0]} is frozen.", "nothing to do; a frozen result stays")
    shutil.rmtree(root / "tables" / name)
    for r in res:
        r.unlink()
    print(f"dropped tables/{name}" + (f" and {len(res)} result files" if res else ""))
    return 0


def split(root, name, col, val, verdict):
    """Whenever `col` reads `val` the verdict is `verdict`, applied so the rows stay a partition."""
    root = Path(root)
    p = root / "tables" / name / "verdict.toml"
    if not p.is_file():
        return unknown_set(root, name, "bin/cc tables split <one of these> ...")
    if f"tables/{name}" in frozen(root)[1]:
        return refuse(f"REFUSED: tables/{name} is frozen (results depend on it).",
                      f"fork it first: bin/cc tables fork {name} <new-name>")
    text = p.read_text()
    d, codes = tomllib.loads(text), tomllib.loads((p.parent / "codes.toml").read_text())
    alpha = declare.doms(codes, declare.Ctx(root).alpha["nulls"])
    if val not in alpha.get(col, []):
        return refuse(f"'{col}' = '{val}' is not a column value of {name}.",
                      f"use a column of {' '.join(alpha)} and one of its values")
    rows, touched = [], 0
    for r in d["row"]:
        w = r["when"]
        if col in w and val not in w[col]:
            rows.append(r)
            continue
        touched += 1
        left = [x for x in w.get(col, alpha[col]) if x != val]
        rows += [{**r, "when": {**w, col: left}}] if left else []
    why = f"split: {col} = {val} decides the verdict (bin/cc tables split, {date.today().isoformat()})"
    d["row"] = rows + [{"when": {col: [val]}, "verdict": verdict, "why": why}]
    if verdict not in d["verdicts"]:
        d["verdicts"].append(verdict)
        d["refuse"] += [verdict] if verdict.startswith("REFUSE") else []
    lines = text.splitlines()
    head = "".join(ln + "\n" for ln in lines[: next(i for i, ln in enumerate(lines) if not ln.startswith("#"))])
    p.write_text(text_of(head, d))
    found = declare.check_file(p, root)
    print(f"split touched {touched} rows ({len(d['row'])} rows now)")
    print("\n".join(declare.fmt(f) for f in found) or f"tables/{name}/verdict.toml: clean")
    return 1 if found else 0
