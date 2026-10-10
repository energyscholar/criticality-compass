"""bench.py - the frozen benchmark suite as a manifest (plan 0932 P1).

benchmark/ROWS.toml  (Argus's declared row list: single files + sets listed by a producer's own manifest; the role alphabet)
        --gen-->   benchmark/MANIFEST.toml  (one entry per file: id, role, root, path, sha256, bytes, source; + one identity per set)
        --verify-> one line per absence / mismatch; exit != 0 on any.

Roots: "cc" = the CC checkout; "data" = the declared data root (cc.toml [data] root, moved by --data-root / CC_DATA_ROOT).
Rows are never found by globbing a root: every row is named in ROWS.toml, or named by a producer manifest ROWS.toml points at.
A set's identity = sha256 of its sorted per-file lines "<path>\\t<sha256>\\t<bytes>\\n" (RECIPE below)."""
import hashlib
import json
import sys
import tomllib
from pathlib import Path

SCHEMA = 1
RECIPE = 'set identity = sha256 of the sorted lines "<path>\\t<sha256>\\t<bytes>\\n" of its entries (path as in the manifest)'
FIELDS = ("id", "role", "root", "path", "sha256", "bytes", "source")
ROOTS = ("cc", "data")


class Refused(Exception):
    pass


def sha_of(p):
    h, n = hashlib.sha256(), 0
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
            n += len(blk)
    return h.hexdigest(), n


def _toml_str(s):
    return json.dumps(s)   # a JSON string is a valid TOML basic string


def load_rows(path):
    """Parse ROWS.toml. The role alphabet is DATA in the header; a row whose role is outside it is refused here, at load."""
    d = tomllib.loads(Path(path).read_text())
    roles = d.get("roles")
    if d.get("schema") != SCHEMA or not isinstance(roles, list) or not roles:
        raise Refused(f"{path}: header needs schema = {SCHEMA} and a non-empty roles = [...]")
    for r in list(d.get("row", [])) + list(d.get("set", [])):
        if r.get("role") not in roles:
            raise Refused(f"{path}: row '{r.get('id', r.get('path'))}' has role {r.get('role')!r}, outside the declared alphabet {roles}")
        if r.get("root") not in ROOTS:
            raise Refused(f"{path}: row '{r.get('id', r.get('path'))}' has root {r.get('root')!r}, outside {list(ROOTS)}")
    return d


def _listed(root_dir, s):
    """File names (relative to the set's dir) that the producer's own manifest names."""
    if "files" in s:   # the set names its files itself (inputs with no producer manifest); still explicit, never a glob
        return list(s.get("extra", [])) + list(s["files"])
    lst = root_dir / s["path"] / s["listed_by"]
    if not lst.is_file():
        raise Refused(f"set '{s['id']}': the producer list {lst} is absent, so the rows cannot be named")
    if s["listed_by"].endswith(".tsv"):
        lines = lst.read_text().splitlines()
        col = lines[0].split("\t").index("file")
        names = [ln.split("\t")[col] for ln in lines[1:] if ln.strip()]
    else:
        names = [f["file"] for f in json.loads(lst.read_text())["files"]]
    return [s["listed_by"]] + list(s.get("extra", [])) + names


def expand(rows, roots):
    """-> list of (set_id|None, id, role, root, path, source). Order = declaration order, sets expanded in listed order."""
    out = [(None, r["id"], r["role"], r["root"], r["path"], r["source"]) for r in rows.get("row", [])]
    for s in rows.get("set", []):
        for nm in _listed(roots[s["root"]], s):
            p = f"{s['path']}/{nm}"
            out.append((s["id"], p, s["role"], s["root"], p, s["source"]))
    ids = [o[1] for o in out]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise Refused(f"duplicate row ids: {dup[:5]}")
    return out


def set_identity(entries):
    lines = sorted(f"{e['path']}\t{e['sha256']}\t{e['bytes']}\n" for e in entries)
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def generate(rows_path, out_path, roots, extend=False):
    """extend=True: the entries already in out_path are carried VERBATIM (not re-hashed: their bytes may live on another host); only rows whose id
    is not yet in it are hashed. A carried entry must still be a declared row, so a row removed from ROWS.toml is refused, never silently dropped."""
    rows = load_rows(rows_path)
    planned = expand(rows, roots)
    old = load_manifest(out_path) if extend else {"entry": [], "set": []}
    have = {e["id"]: e for e in old["entry"]}
    gone = sorted(set(have) - {p[1] for p in planned})
    if gone:
        raise Refused(f"--extend: {len(gone)} manifest entries are no longer declared rows (first: {gone[0]}). Nothing written.")
    absent = [p for p in planned if p[1] not in have and not (roots[p[3]] / p[4]).is_file()]
    if absent:
        raise Refused(f"{len(absent)} declared rows have no bytes under their root; first: " + ", ".join(f"{a[3]}:{a[4]}" for a in absent[:5]) + ". Nothing written.")
    entries, bysets = [], {}
    for sid, i, role, root, path, source in planned:
        if i in have:
            e = have[i]
            if (e["role"], e["root"], e["path"], e["source"]) != (role, root, path, source):
                raise Refused(f"--extend: declared row '{i}' differs from the carried entry in role/root/path/source. Nothing written.")
        else:
            h, n = sha_of(roots[root] / path)
            e = dict(id=i, role=role, root=root, path=path, sha256=h, bytes=n, source=source)
        entries.append(e)
        if sid:
            bysets.setdefault(sid, []).append(e)
    sets = [dict(id=s["id"], role=s["role"], root=s["root"], path=s["path"], n=len(bysets[s["id"]]), sha256=set_identity(bysets[s["id"]]), source=s["source"])
            for s in rows.get("set", [])]
    head = ["# benchmark/MANIFEST.toml (plan 0932 P1) - GENERATED by `bin/cc bench gen` from benchmark/ROWS.toml; do not edit by hand.",
            "# DATA NEVER IN GIT: paths are relative to the root named in each entry; the bytes stay where they are.",
            f"schema = {SCHEMA}", f"roles = {json.dumps(rows['roles'])}", f"fields = {json.dumps(list(FIELDS))}",
            f"recipe = {_toml_str(RECIPE)}", f"rows_sha256 = {_toml_str(sha_of(rows_path)[0])}", ""]
    body = []
    for s in sets:
        body += ["[[set]]"] + [f"{k} = {_toml_str(v) if isinstance(v, str) else v}" for k, v in s.items()] + [""]
    for e in entries:
        body += ["[[entry]]"] + [f"{k} = {_toml_str(v) if isinstance(v, str) else v}" for k, v in e.items()] + [""]
    Path(out_path).write_text("\n".join(head + body))
    return len(entries), len(sets)


def load_manifest(path):
    m = tomllib.loads(Path(path).read_text())
    roles = m.get("roles")
    if m.get("schema") != SCHEMA or not isinstance(roles, list):
        raise Refused(f"{path}: header needs schema = {SCHEMA} and roles = [...]")
    for e in m.get("entry", []):
        miss = [k for k in FIELDS if k not in e]
        if miss:
            raise Refused(f"{path}: entry '{e.get('id')}' lacks {miss}")
        if e["role"] not in roles:
            raise Refused(f"{path}: entry '{e['id']}' has role {e['role']!r}, outside the declared alphabet {roles}")
        if e["root"] not in ROOTS:
            raise Refused(f"{path}: entry '{e['id']}' has root {e['root']!r}")
    return m


def verify(manifest_path, roots):
    """-> list of one-line findings. Absence and mismatch are distinct messages; a set whose recomputed identity differs is one more."""
    m = load_manifest(manifest_path)
    out, seen = [], {}
    for e in m.get("entry", []):
        p = roots[e["root"]] / e["path"]
        if not p.is_file():
            out.append(f"ABSENT   {e['id']}: no file at {e['root']}:{e['path']} (role {e['role']})")
            continue
        h, n = sha_of(p)
        if (h, n) != (e["sha256"], e["bytes"]):
            out.append(f"MISMATCH {e['id']}: sha256 {h} bytes {n}; manifest says sha256 {e['sha256']} bytes {e['bytes']}")
        else:
            seen[e["id"]] = e
    for s in m.get("set", []):
        mine = [e for e in m["entry"] if e["path"].startswith(s["path"] + "/") and e["root"] == s["root"] and e["role"] == s["role"]]
        if len(mine) != s["n"] or set_identity(mine) != s["sha256"]:
            out.append(f"SET      {s['id']}: the manifest's own entries do not reproduce the set identity (n {len(mine)} vs {s['n']})")
    return out


def main(args, roots, repo):
    if not args or args[0] not in ("gen", "verify"):
        print("usage: bin/cc [--data-root DIR] bench gen [--extend] | verify\n  Next: bench gen builds benchmark/MANIFEST.toml from benchmark/ROWS.toml; bench verify re-hashes every entry")
        return 1
    try:
        if args[0] == "gen":
            n, s = generate(repo / "benchmark/ROWS.toml", repo / "benchmark/MANIFEST.toml", roots, extend="--extend" in args[1:])
            print(f"wrote benchmark/MANIFEST.toml: {n} entries, {s} sets")
            return 0
        bad = verify(repo / "benchmark/MANIFEST.toml", roots)
    except Refused as r:
        print(f"refused: {r}")
        return 2
    for ln in bad:
        print(ln)
    n = len(load_manifest(repo / "benchmark/MANIFEST.toml").get("entry", []))
    print(f"bench verify: {n} entries, {len(bad)} findings" + (" - FAIL" if bad else " - ok"))
    return 1 if bad else 0
