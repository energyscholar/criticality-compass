"""transducer.py - inputs/<id>/transducer.toml (plan 0883, Q0): the transducer (or the record), the per-locus reduction, the interval's role.
Plumbing; outside the measurement closure. The schema is data (cc.toml [transducer], [alphabets] interval_method); nothing here reads a sentence."""
import hashlib
import os
import re
import subprocess
from pathlib import Path
from schema import at, sha

UPDATE = re.compile(r"(\S+) sha256 ([0-9a-f]{64})")
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
        out += update_findings(p, t.get("update"), c.data_root.parent) if isinstance(t.get("update"), list) else []
    for sec_name in ("reduction", "interval"):
        out += [at(p, f"{sec_name}.{k}", "is empty", f"write what the {sec_name} {k}") for k, v in d[sec_name].items() if isinstance(v, str) and not v.strip()]
    role = d["interval"].get("role")
    return out + D.when(isinstance(role, str) and role != cfg["interval_role"], p, "interval.role", f"'{role}' is not the declared role",
                        f'write role = "{cfg["interval_role"]}"')


def _git(tools, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}   # a git hook exports GIT_DIR/GIT_INDEX_FILE: they would point -C at the hook's repo
    r = subprocess.run(["git", "-C", str(tools), *args], capture_output=True, env=env)
    return r.stdout if r.returncode == 0 else None


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
        got = retrieve(tools, m[1], m[2]) if m else None
        if got:
            out[m[1]] = {"sha256": m[2], "commit": got[0]}
    return out


def update_findings(p, update, tools):
    """Each entry '<toolset path> sha256 <hex>' names content some commit of the toolset holds for that path (retrieve; D-0929-5). Total: no entry is skipped."""
    out = [at(p, "transducer.update", "must have at least one entry", 'write update = ["<toolset path> sha256 <64 hex>"]')] if not update else []
    for i, e in enumerate(update):
        m = UPDATE.fullmatch(e) if isinstance(e, str) else None
        if m is None:
            out.append(at(p, f"transducer.update[{i}]", f"'{e}' is not '<toolset-relative path> sha256 <64 hex>'", "write the path, the word sha256 and the 64 hex digits of sha256sum"))
            continue
        rel, want = m[1], m[2]
        if retrieve(tools, rel, want) is None:
            head = _git(tools, "show", f"HEAD:{rel}")
            if head is not None:   # the pinned content is in no commit; the newest committed content of that path is the pin to write
                got = hashlib.sha256(head).hexdigest()
                out.append(at(p, f"transducer.update[{i}]", f"{rel} sha256 {want} differs from the toolset file's {got}", f"write {rel} sha256 {got}"))
            else:
                out.append(at(p, f"transducer.update[{i}]", f"{rel} sha256 {want} is in no commit of the toolset's history, and {rel} is not committed there",
                              f"name a committed sampler file of the toolset (git -C <toolset> log --all -- {rel})"))
    return out
