"""intake_seal - stage S2 SEAL of the intake (plan 1136): `mint` stamps a declaration (bin/cc intake seal), `verify` is the stage body
(bin/cc intake run). Invariant: a Sealed is built in this module only, by `verify`, and only from a seal-log line whose sha256 equals the
declaration's sha256 now; the seal records the source universe as names and sizes, never a hash and never a data byte (amendment A2 Q7).
The seal proves integrity and ordering, never ignorance (intake/STAGES.toml [report] seal_claim)."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from intake_blind import Pass, Refuse

FILES = ("intake.toml", "transducer.toml")   # the declaration: the two files its sha256 covers, in this order
AUTHOR_KIND = {"human": "HUMAN", "ai-draft": "AI_DRAFT"}   # the --as word -> the sealed author_kind; a word outside it is a usage refusal


class Sealed:
    """S2 SEAL's PASS evidence: the Declaration and its SEAL.json record. Invariant: no public constructor (calling Sealed(...) is a
    TypeError) and frozen; `verify` builds it with object.__new__. Python cannot forbid object.__new__ elsewhere; a forged Sealed carries a sha
    with no seal-log line, which S6 ADMISSIBILITY (through the loader's t23.check) refuses once it is live."""
    __slots__ = ("declaration", "record")

    def __init__(self, *args, **kwargs):
        raise TypeError("Sealed has no public constructor; it is the evidence of a passed S2 SEAL (bin/cc intake run)")

    def __setattr__(self, key, value):
        raise TypeError("a Sealed is frozen")

    def summary(self):
        r = self.record
        return (f"Sealed at {r['sealed_at_utc']} (seal-log t_ns {r['sealed_at_ns']}) by {r['author']} ({r['author_kind']}), confirmed_by "
                f"'{r['confirmed_by']}', mode {r['mode']}; declaration sha256 {r['declaration_sha256']}; universe '{r['universe']['root']}' "
                f"(located at a directory named '{r['universe']['location_name']}'): {len(r['universe']['listing'])} files, names and sizes in SEAL.json")

    def confirmed(self):
        return self.record["confirmed_by"] != ""


def _built(declaration, record):
    s = object.__new__(Sealed)
    object.__setattr__(s, "declaration", declaration)
    object.__setattr__(s, "record", record)
    return s


def declaration_sha(d):
    """sha256 over the sorted (name, sha256) lines of the declaration's two files."""
    lines = "".join(f"{n}\0{hashlib.sha256((Path(d) / n).read_bytes()).hexdigest()}\n" for n in sorted(FILES))
    return hashlib.sha256(lines.encode()).hexdigest()


def lines(p):
    """The JSON lines of an append-only log; a log never written has none (Path.is_file is the key of a two-row table)."""
    return {True: lambda: [json.loads(x) for x in Path(p).read_text().splitlines()], False: lambda: []}[Path(p).is_file()]()


def _append(p, rec):
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)   # append-only by open mode (the toolset t23 log discipline)
    os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode())
    os.close(fd)


VERIFY = {   # (SEAL.json present, a seal-log line holds the declaration's sha now, a logged loader read precedes that line) -> the S2 result
    (False, False, False): lambda d, decl, sha, t: Refuse("SEAL_ABSENT", f"no SEAL.json in the declaration '{decl.id}'"),
    (False, False, True): lambda d, decl, sha, t: Refuse("SEAL_ABSENT", f"no SEAL.json in the declaration '{decl.id}'"),
    (False, True, False): lambda d, decl, sha, t: Refuse("SEAL_ABSENT", f"no SEAL.json in the declaration '{decl.id}' (its seal-log line is {sha[:12]})"),
    (False, True, True): lambda d, decl, sha, t: Refuse("SEAL_ABSENT", f"no SEAL.json in the declaration '{decl.id}' (its seal-log line is {sha[:12]})"),
    (True, False, False): lambda d, decl, sha, t: Refuse("SEAL_SHA_DIFFERS", f"the declaration hashes to {sha[:12]} now; no seal-log line holds it"),
    (True, False, True): lambda d, decl, sha, t: Refuse("SEAL_SHA_DIFFERS", f"the declaration hashes to {sha[:12]} now; no seal-log line holds it"),
    (True, True, True): lambda d, decl, sha, t: Refuse("DATA_READ_PRECEDES_SEAL", f"access.log holds a loader read before the seal at t_ns {t}"),
    (True, True, False): lambda d, decl, sha, t: Pass(_built(decl, json.loads((Path(d) / "SEAL.json").read_text()))),
}


def verify(declaration, d):
    """S2 SEAL in a run: the declaration's sha256 now, looked up in the seal log, against the access log. Never mints."""
    sha = declaration_sha(d)
    sealed = [s["t_ns"] for s in lines(Path(d) / "seal.log") if s["sha256"] == sha]
    reads = [a["t_ns"] for a in lines(Path(d) / "access.log") if a["route"] == "loader"]
    before = [t for t in sealed for r in reads if r < t]
    return VERIFY[((Path(d) / "SEAL.json").is_file(), len(sealed) > 0, len(before) > 0)](d, declaration, sha, (before + [""])[0])


def _git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return {True: r.stdout.strip(), False: "NO-GIT"}[r.returncode == 0]


def listing(universe, glob):
    """The source universe as sorted [relative path, size] pairs: names and sizes only, never a byte of a file."""
    return sorted([q.relative_to(universe).as_posix(), q.stat().st_size] for q in Path(universe).glob(glob) if q.is_file())


def _write(d, decl, universe, who, root, tables):
    import schema
    src, sel = decl.data["source"], decl.data["selection"]
    have = listing(universe, src["universe"])
    picked = [sel["pattern"].format(index=i) for i in range(sel["index"]["first"], sel["index"]["last"] + 1)]
    outside = sorted(set(picked) - {n for n, _ in have})
    return {False: lambda: Refuse("SELECTION_OUTSIDE_UNIVERSE", f"{len(outside)} selected files are not in the universe listing, first {outside[:3]}"),
            True: lambda: _stamp(d, decl, universe, have, who, root, tables, schema)}[not outside]()


def _stamp(d, decl, universe, have, who, root, tables, schema):
    sha = declaration_sha(d)
    t = time.time_ns()
    _append(Path(d) / "seal.log", {"t_ns": t, "sha256": sha, "file": "SEAL.json"})   # the seal time IS the log time
    rec = {
        "schema": 1, "kind": "intake-seal", "id": decl.id, "sealed_at_ns": t, "sealed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t // 10**9)),
        **who, "mode": decl.mode, "declaration_sha256": sha,
        "files": {n: hashlib.sha256((Path(d) / n).read_bytes()).hexdigest() for n in FILES},
        "code_identity": {"commit": _git(root, "rev-parse", "HEAD"), "code_hash": schema.code_hash(root),
                          "tree": {True: "CLEAN", False: "UNCOMMITTED_CHANGES"}[_git(root, "status", "--porcelain", "--", "cc", "bin/cc") == ""]},
        "protocol_identity": {n: {"sha256": hashlib.sha256((Path(root) / "intake" / n).read_bytes()).hexdigest(), "version": tables[k]["version"]}
                              for n, k in (("STAGES.toml", "stages"), ("POLICY.toml", "policy"), ("FORMAT.toml", "format"))},
        "universe": {"root": decl.data["source"]["root"], "location_name": Path(universe).resolve().name, "glob": decl.data["source"]["universe"], "listing": have},
        "claim": tables["stages"]["report"]["seal_claim"],
    }
    (Path(d) / "SEAL.json").write_text(json.dumps(rec, indent=1) + "\n")
    return Pass(_built(decl, rec))


def mint(declaration, d, universe, who, root, tables):
    """bin/cc intake seal, after S0 passed: ALREADY_SEALED | UNIVERSE_ROOT_ABSENT | SELECTION_OUTSIDE_UNIVERSE, or append the seal-log line and
    write SEAL.json. `who` = {author, author_kind, confirmed_by}; `universe` is the directory --universe names (a str; "" when not given)."""
    return {True: lambda: Refuse("ALREADY_SEALED", "SEAL.json exists; a seal is never replaced"),
            False: lambda: {False: lambda: Refuse("UNIVERSE_ROOT_ABSENT", f"'{universe}' is not a directory on this machine"),
                            True: lambda: _write(d, declaration, Path(universe), who, root, tables)}[universe != "" and Path(universe).is_dir()]()}[(Path(d) / "SEAL.json").is_file()]()
