"""author.py - the commands that write plugin files: new case/input, data add, tables fork/drop/split (plumbing)."""
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


def scal(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Was):
        return f'"TODO"   # was {v.old}'
    if isinstance(v, str):
        if len(v) <= 80:
            return json.dumps(v)
        words, lines, cur = json.dumps(v)[1:-1].split(" "), [], ""
        for w in words:
            lines, cur = (lines + [cur], w) if cur and len(cur) + len(w) > 88 else (lines, f"{cur} {w}" if cur else w)
        return '"""' + " \\\n".join(lines + [cur]) + '"""'
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{key(k)} = {scal(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        items = [scal(x) for x in v]
        if len(", ".join(items)) < 85:
            return "[" + ", ".join(items) + "]"
        rows, cur = [], "  "
        for it in items:
            rows, cur = (rows + [cur.rstrip()], "  " + it + ",") if len(cur) + len(it) > 96 else (rows, cur + (" " if cur != "  " else "") + it + ",")
        return "[\n" + "\n".join(rows + [cur]) + "\n]"
    return repr(v)


def small(v):
    return isinstance(v, dict) and len(v) <= 3 and not any(isinstance(x, (dict, list)) for x in v.values())


def aot(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v)


def dump(d, path=""):
    """TOML lines for a nested dict in vertical form (scalars, small inline tables, sub-tables, [[blocks]])."""
    inline = lambda v: not aot(v) and (not isinstance(v, dict) or (small(v) and path))  # noqa: E731
    out = [f"{key(k)} = {scal(v)}" for k, v in d.items() if inline(v)]
    for k, v in d.items():
        name = f"{path}.{key(k)}" if path else key(k)
        if aot(v):
            for item in v:
                out += ["", f"[[{name}]]"]
                for k2, x in item.items():
                    out += [f"{key(k2)}.{key(k3)} = {scal(y)}" for k3, y in x.items()] if isinstance(x, dict) else [f"{key(k2)} = {scal(x)}"]
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
    use = [reg[i] for i in keep]
    m["instruments"] = keep
    for k in declare.SIDECARS:
        if k in m and not any(k in i["sidecar"] for i in use):
            del m[k]
    rels = {k: v for k, v in m.pop("relations", {}).items() if any(k in i["relations"] for i in use)}
    m.update({"relations": rels} if rels else {})
    m["eps"] = {k: v for k, v in m["eps"].items() if k in {e for i in use for e in i["columns"].values()}}


def new_input(root, iid, like=None, points=None, pattern=None, instruments=None):
    root = Path(root)
    d = root / "inputs" / iid
    if d.exists():
        return refuse(f"inputs/{iid} already exists.", "pick another id")
    ins = root / "inputs"
    d.mkdir()
    if like is None:
        (d / "m.toml").write_text((ins / "TEMPLATE.m.toml.in").read_text().replace("<ID>", iid))
        (d / "points.toml").write_text((ins / "TEMPLATE.points.toml.in").read_text().replace("<ID>", iid))
        print(f"wrote inputs/{iid}/m.toml and points.toml\n  Next: replace every TODO, add the [[data.files]] blocks, "
              f"then bin/cc data add {iid} and bin/cc validate")
        return 0
    src = ins / like / "m.toml"
    if not src.is_file():
        d.rmdir()
        return refuse(f"no input '{like}'.", f"bin/cc new input {iid} --like <one of: {' '.join(sorted(p.parent.name for p in ins.glob('*/m.toml')))}>")
    text = src.read_text()
    m = tomllib.loads(text)
    m["id"] = iid
    if points:
        repoint(m, points.split(","), pattern or m["axes"]["point"][-1])
    if instruments:
        restrict(m, instruments.split(","), declare.Ctx(root).reg)
    head = "\n".join(text.splitlines()[:2]) + f"\n# inputs/{iid}/m.toml - like {like}\n"
    body = text_of(head, m) if points or instruments else re.sub(r'^id = ".*"$', f'id = "{iid}"', text, flags=re.M)
    (d / "m.toml").write_text(body)
    pts = "\n".join(f'"{p}" = "TODO"' for p in m["axes"]["point"])
    (d / "points.toml").write_text(f'# inputs/{iid}/points.toml - the point -> case JOIN (taxonomy; never frozen)\n'
                                   f'schema = 1\nkind = "points"\ninput = "{iid}"\n\n[points]\n{pts}\n')
    print(f"wrote inputs/{iid}/m.toml and points.toml (like {like})\n  Next: fix every TODO, then bin/cc data add {iid} and bin/cc validate")
    return 0


def data_add(root, iid):
    root = Path(root)
    p, c = root / "fixtures" / "data" / f"{iid}.toml", declare.Ctx(root)
    m, bad = declare.load(root / "inputs" / iid / "m.toml", root)
    if bad:
        return refuse(declare.fmt(bad[0]).split("\n  Next: ")[0], f"bin/cc new input {iid}")
    if p.exists():
        return refuse(f"fixtures/data/{iid}.toml already exists.", "delete it first if it is unfrozen and you mean to re-pin")
    paths = list(dict.fromkeys(b["path"] for b in m["data"]["files"]))
    gone = [x for x in paths if not (c.data_root / x).is_file()]
    if gone:
        return refuse(f"inputs/{iid}/m.toml: {len(gone)} data files do not exist under the data root, first: {gone[0]}",
                      "fix the paths in [[data.files]], then bin/cc data add " + iid)
    head = f"# fixtures/data/{iid}.toml - written by bin/cc data add: sha256 of every data file\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text_of(head, {"schema": 1, "kind": "data-manifest", "input": iid, "files": {x: declare.sha(c.data_root / x) for x in paths}}))
    print(f"pinned {len(paths)} files in fixtures/data/{iid}.toml\n  Next: bin/cc validate")
    return 0


def frozen(root):
    f = Path(root) / "FROZEN.json"
    fz = json.loads(f.read_text()) if f.is_file() else {"files": {}, "dirs": {}}
    return set(fz["files"]), set(fz["dirs"])


def sets_of(root):
    return sorted(t.name for t in (Path(root) / "tables").glob("*") if t.is_dir())


def fork(root, src, dst):
    root = Path(root)
    if src not in sets_of(root):
        return refuse(f"no table set '{src}'. Sets: {' '.join(sets_of(root))}", "bin/cc tables fork <one of these> <new-name>")
    if (root / "tables" / dst).exists():
        return refuse(f"tables/{dst} already exists.", f"pick another name, or bin/cc tables drop {dst} first")
    shutil.copytree(root / "tables" / src, root / "tables" / dst)
    for p in [root / "tables" / dst, *(root / "tables" / dst).rglob("*")]:
        p.chmod(0o755 if p.is_dir() else 0o644)
    print(f"forked tables/{src} to tables/{dst}\n  Next: edit tables/{dst}/verdict.toml, then bin/cc validate, then bin/cc run --all --tables {dst}")
    return 0


def drop(root, name, with_results):
    root = Path(root)
    if name not in sets_of(root):
        return refuse(f"no table set '{name}'. Sets: {' '.join(sets_of(root))}", "bin/cc tables drop <one of these>")
    if declare.Ctx(root).cfg["defaults"]["tables"] == name:
        return refuse(f"REFUSED: tables/{name} is the default rulebook (cc.toml [defaults] tables).",
                      "change [defaults] tables in cc.toml first, or drop another set")
    files, dirs = frozen(root)
    res = sorted((root / "results").glob(f"*@{name}.*")) if (root / "results").is_dir() else []
    if f"tables/{name}" in dirs:
        return refuse(f"REFUSED: tables/{name} is frozen (results depend on it).", "nothing to do; a frozen rulebook stays. Fork it to change it.")
    if res and not with_results:
        return refuse(f"tables/{name} has results: {' '.join(str(r.relative_to(root)) for r in res)}", f"bin/cc tables drop {name} --with-results")
    hit = [str(r.relative_to(root)) for r in res if str(r.relative_to(root)) in files]
    if hit:
        return refuse(f"REFUSED: {hit[0]} is frozen.", "nothing to do; a frozen result stays")
    shutil.rmtree(root / "tables" / name)
    for r in res:
        r.unlink()
    print(f"dropped tables/{name}" + (f" and {len(res)} result files" if res else ""))
    return 0


def split(root, name, col, val, verdict):
    root = Path(root)
    p = root / "tables" / name / "verdict.toml"
    if not p.is_file():
        return refuse(f"no table set '{name}'. Sets: {' '.join(sets_of(root))}", "bin/cc tables split <one of these> ...")
    if f"tables/{name}" in frozen(root)[1]:
        return refuse(f"REFUSED: tables/{name} is frozen (results depend on it).", "fork it first: bin/cc tables fork " + name + " <new-name>")
    c = declare.Ctx(root)
    text = p.read_text()
    d, codes = tomllib.loads(text), tomllib.loads((p.parent / "codes.toml").read_text())
    dom = declare.doms(codes, c.alpha["nulls"]).get(col)
    if dom is None or val not in dom:
        return refuse(f"'{col}' = '{val}' is not a column value of {name}.", f"use a column of {' '.join(declare.doms(codes, []))} and one of its values")
    rows, touched = [], 0
    for r in d["row"]:
        w = r["when"]
        if col in w and val not in w[col]:
            rows.append(r)
            continue
        touched += 1
        left = [x for x in w.get(col, dom) if x != val]
        rows += [{**r, "when": {**w, col: left}}] if left else []
    why = f"split: {col} = {val} decides the verdict (bin/cc tables split, {date.today().isoformat()})"
    d["row"] = rows + [{"when": {col: [val]}, "verdict": verdict, "why": why}]
    if verdict not in d["verdicts"]:
        d["verdicts"].append(verdict)
        d["refuse"] += [verdict] if verdict.startswith("REFUSE") else []
    head = "".join(ln + "\n" for ln in text.splitlines()[: next(i for i, ln in enumerate(text.splitlines()) if not ln.startswith("#"))])
    p.write_text(text_of(head, d))
    found = declare.check_file(p, root)
    print(f"split touched {touched} rows ({len(d['row'])} rows now)")
    print("\n".join(declare.fmt(f) for f in found) or f"tables/{name}/verdict.toml: clean")
    return 1 if found else 0
