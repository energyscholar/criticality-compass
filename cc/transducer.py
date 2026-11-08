"""transducer.py - inputs/<id>/transducer.toml (plan 0883, Q0): the transducer (or the record), the per-locus reduction, the interval's role.
Plumbing; outside the measurement closure. The schema is data (cc.toml [transducer], [alphabets] interval_method); nothing here reads a sentence."""
import hashlib
import re
import tomllib
from pathlib import Path
from schema import at, sha
from host import Held, probe, resource, git_bytes as _git

UPDATE = re.compile(r"((?:[a-z]+:)?)(\S+) sha256 ([0-9a-f]{64})")   # [route] path sha256 hex
CC = Path(__file__).resolve().parent.parent
ROUTES = {k: CC / v for k, v in tomllib.loads((CC / "cc.toml").read_text())["transducer"]["update_routes"].items()}   # declared routes; "" is the toolset


def routed(tools, m):
    """(the git tree a pin resolves in, its path there, its sha) for an UPDATE match: no route = the toolset root `tools`; a route = its
    directory of cc.toml [transducer] update_routes. An undeclared route resolves to None (update_findings reports it)."""
    routes = {**ROUTES, "": tools}
    return {True: lambda: routes[m[1]], False: lambda: None}[m[1] in routes](), m[2], m[3]
RECORD = ("apparatus", "preparation", "observation", "authors_projection", "source")


def chk_transducer(p, d, c, stem=None):
    import declare as D   # late: declare registers this function in KIND
    cfg = c.cfg.get("transducer")
    if cfg is None:
        return [at("cc.toml", "transducer", "missing: the transducer file's sentences are declared there", "add a [transducer] table to cc.toml")]
    kind = d.get("kind")
    out = D.header(p, d, kind) + D.inalpha(p, "kind", kind, cfg["kinds"])
    sec = {"transducer": {"transducer": dict}, "record": {"record": dict}}.get(kind, {})
    out += D.shape(p, d, {"id": str, "reduction": dict, "interval": dict, **sec}, {"provenance_note": dict})
    if out:
        return out
    out += D.id_check(p, "id", d["id"], stem, "its directory")
    if list(D.todos(p, d)):
        return out + list(D.todos(p, d))   # a template still full of TODOs: report them, nothing else
    full = {"name": str, "keeps": str, "discards": str}
    out += D.shape(p, d["reduction"], full, pre="reduction.") + D.shape(p, d["interval"], {"role": str, "keeps": str, "discards": str}, pre="interval.")
    out += D.shape(p, d.get("provenance_note", {}), {}, {"declared_after": list, "note": str}, pre="provenance_note.")
    if kind == "record":
        out += D.shape(p, d["record"], {k: str for k in RECORD}, pre="record.")
    else:
        t = d["transducer"]
        out += D.shape(p, t, {"model": str, "update": list, "inputs": str, "output": str}, pre="transducer.")
        outs = [cfg["phase1_output"], cfg["phase2_output"]]
        out += D.when(isinstance(t.get("output"), str) and t["output"] not in outs, p, "transducer.output", f"'{t['output']}' is not a declared output sentence",
                      "write exactly one of cc.toml [transducer] phase1_output / phase2_output: " + " | ".join(f'"{x}"' for x in outs))
        out += update_findings(p, t.get("update"), probe(c)[1]) if isinstance(t.get("update"), list) else []   # plan 1273: the toolset this host holds, or Absent
    for sec_name in ("reduction", "interval"):
        out += [at(p, f"{sec_name}.{k}", "is empty", f"write what the {sec_name} {k}") for k, v in d[sec_name].items() if isinstance(v, str) and not v.strip()]
    role = d["interval"].get("role")
    return out + D.when(isinstance(role, str) and role != cfg["interval_role"], p, "interval.role", f"'{role}' is not the declared role",
                        f'write role = "{cfg["interval_role"]}"')


def retrieve(tools, rel, want):
    """(commit, bytes) of the toolset file `rel` whose sha256 is `want`, or None. A pin is a CONTENT hash, so it is checked against the
    toolset's git HISTORY (any commit holding a blob of that path with that sha), never against a working tree that other projects change
    (plan 0929, ruling D-0929-5). The bytes come from that commit; only a toolset with no such commit falls back to the working-tree file,
    and then the commit is 'working-tree'. A sha found in no commit and not in the working tree gives None."""
    log = _git(tools, "log", "--all", "--format=%H", "--", rel)
    for c in (log or b"").decode().split():
        blob = _git(tools, "show", f"{c}:{rel}")
        if blob is not None and hashlib.sha256(blob).hexdigest() == want:
            return c, blob
    path = Path(tools) / rel
    if log is None and path.is_file() and sha(path) == want:   # not a git toolset: the working tree is the only source there is
        return "working-tree", path.read_bytes()
    return None


def supplied(update, tools):
    """{path: {"sha256": ..., "commit": ...}} for every well-formed update entry whose pinned content is retrievable (for the result record)."""
    out = {}
    for e in update:
        m = UPDATE.fullmatch(e) if isinstance(e, str) else None
        base, rel, want = routed(tools, m) if m else (None, "", "")
        got = retrieve(base, rel, want) if base else None
        if got:
            out[m[1] + rel] = {"sha256": want, "commit": got[0]}
    return out


def update_findings(p, update, tools):
    """Each entry '<toolset path> sha256 <hex>' names content some commit of the toolset holds for that path (retrieve; D-0929-5). Total: no entry is skipped.
    `tools`: the toolset's path, or the host's toolset resource (plan 1273): an Absent toolset makes each of its entries NotEvaluableHere; a Compass route is always held."""
    routes = {**{k: Held("compass", v) for k, v in ROUTES.items()}, "": resource(tools)}
    out = [at(p, "transducer.update", "must have at least one entry", 'write update = ["<toolset path> sha256 <64 hex>"]')] if not update else []
    for i, e in enumerate(update):
        m = UPDATE.fullmatch(e) if isinstance(e, str) else None
        if m is None:
            out.append(at(p, f"transducer.update[{i}]", f"'{e}' is not '<toolset-relative path> sha256 <64 hex>'", "write the path, the word sha256 and the 64 hex digits of sha256sum"))
            continue
        if m[1] not in routes:
            out.append(at(p, f"transducer.update[{i}]", f"route '{m[1]}' is not declared", f"use a route of cc.toml [transducer] update_routes {sorted(ROUTES)}, or none (the toolset)"))
            continue
        out += routes[m[1]].each(lambda base, rel=m[2], want=m[3], i=i: pin_findings(p, i, base, rel, want), p, f"transducer.update[{i}]")
    return out


def pin_findings(p, i, base, rel, want):
    """One update pin on a held toolset (or Compass route) `base`: retrievable from its history, else the finding naming what to write."""
    out = []
    if retrieve(base, rel, want) is None:
        head = _git(base, "show", f"HEAD:{rel}")
        if head is not None:   # the pinned content is in no commit; the newest committed content of that path is the pin to write
            got = hashlib.sha256(head).hexdigest()
            out.append(at(p, f"transducer.update[{i}]", f"{rel} sha256 {want} differs from the toolset file's {got}", f"write {rel} sha256 {got}"))
        else:
            out.append(at(p, f"transducer.update[{i}]", f"{rel} sha256 {want} is in no commit of the toolset's history, and {rel} is not committed there",
                          f"name a committed sampler file of the toolset (git -C <toolset> log --all -- {rel})"))
    return out
