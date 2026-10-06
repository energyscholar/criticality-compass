"""transducer.py - inputs/<id>/transducer.toml (plan 0883, Q0): the transducer (or the record), the per-locus reduction, the interval's role.
Plumbing; outside the measurement closure. The schema is data (cc.toml [transducer], [alphabets] interval_method); nothing here reads a sentence."""
import re
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


def update_findings(p, update, tools):
    """Each entry '<toolset path> sha256 <hex>' names a file that exists under the toolset root with exactly that sha256 (total: no entry is skipped)."""
    out = [at(p, "transducer.update", "must have at least one entry", 'write update = ["<toolset path> sha256 <64 hex>"]')] if not update else []
    for i, e in enumerate(update):
        m = UPDATE.fullmatch(e) if isinstance(e, str) else None
        if m is None:
            out.append(at(p, f"transducer.update[{i}]", f"'{e}' is not '<toolset-relative path> sha256 <64 hex>'", "write the path, the word sha256 and the 64 hex digits of sha256sum"))
            continue
        path, want = Path(tools) / m[1], m[2]
        if not path.is_file():
            out.append(at(p, f"transducer.update[{i}]", f"{m[1]} does not exist under the toolset root", "name a frozen sampler file of the toolset"))
        elif (got := sha(path)) != want:
            out.append(at(p, f"transducer.update[{i}]", f"{m[1]} sha256 {want} differs from the toolset file's {got}", f"write {m[1]} sha256 {got}"))
    return out
