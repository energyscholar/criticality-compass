"""intake_seal - stage S2 SEAL of the intake (plan 1136; advisory since plan 1139, amendment A3): `mint` stamps a declaration (bin/cc intake
seal), `verify` is the stage body (bin/cc intake run). Invariant: S2 never refuses; its PASS evidence is a SealState whose status is a lookup
over (SEAL.json present, a seal-log line holds the declaration's sha256 now); the seal records the source universe as names and sizes, never a
hash and never a data byte (amendment A2 Q7). Sealing is recommended and not enforced; the seal proves integrity and ordering, never ignorance
(intake/STAGES.toml [report] seal_claim)."""
import enum
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import intake_bytes   # plan 1160 A20: located, the universe from the declared root (intake_bytes imports this module too; both use the other at call time only)
from intake_blind import Absent, Pass, Refuse, detail, gate
import registry

FILES = ("intake.toml", "transducer.toml")   # the declaration: the two files its sha256 covers, in this order
AUTHOR_KIND = {"human": "HUMAN", "ai-draft": "AI_DRAFT"}   # the --as word -> the sealed author_kind; a word outside it is a usage refusal


class SealStatus(enum.Enum):
    """The seal status every report carries. ATOMS: SEALED | UNSEALED | SEALED_THEN_EDITED. Axiom: exactly one holds for a declaration that
    passed FORMAT (a seal holds its text now; it has no SEAL.json; it has a SEAL.json and no seal-log line holds its text now)."""
    SEALED = frozenset({"SEALED"})
    UNSEALED = frozenset({"UNSEALED"})
    SEALED_THEN_EDITED = frozenset({"SEALED_THEN_EDITED"})


class Ordering(enum.Enum):
    """The ordering note of a report: information, never a refusal. ATOMS: NOT_SEALED | NO_DATA_READ_LOGGED | READS_FOLLOW_SEAL |
    A_READ_PRECEDES_SEAL. Axiom: exactly one holds (no SEAL.json; else no logged loader read; else no logged read before the seal time; else one)."""
    NOT_SEALED = frozenset({"NOT_SEALED"})
    NO_DATA_READ_LOGGED = frozenset({"NO_DATA_READ_LOGGED"})
    READS_FOLLOW_SEAL = frozenset({"READS_FOLLOW_SEAL"})
    A_READ_PRECEDES_SEAL = frozenset({"A_READ_PRECEDES_SEAL"})


STATUS = {(False, False): SealStatus.UNSEALED, (False, True): SealStatus.UNSEALED,   # (SEAL.json present, a seal-log line holds the sha now)
          (True, True): SealStatus.SEALED, (True, False): SealStatus.SEALED_THEN_EDITED}


@dataclass(frozen=True)
class SealState:
    """S2 SEAL's PASS evidence (advisory): the status, its sentence, and the SEAL.json record ({} when there is none). Invariant: confirmed()
    holds exactly when the status is SEALED and the record's confirmed_by is not empty; no data stage takes it (plan 1139)."""
    status: SealStatus
    sentence: str
    record: dict

    def summary(self):
        return f"{self.status.name}. {self.sentence}" + (f" {_said(self.record)}" if self.record != {} else "")

    def confirmed(self):
        return self.status is SealStatus.SEALED and self.record["confirmed_by"] != ""


def declared(d):
    """S0's input: the text of declarations/<id>/intake.toml, or Absent when it is no file (S0 refuses DECLARATION_FILE_ABSENT)."""
    f = Path(d) / "intake.toml"
    return {True: lambda: f.read_text(), False: lambda: Absent(f"declarations/{Path(d).name}/intake.toml")}[f.is_file()]()


def _said(r):
    return (f"Sealed at {r['sealed_at_utc']} (seal-log t_ns {r['sealed_at_ns']}) by {r['author']} ({r['author_kind']}), confirmed_by "
            f"'{r['confirmed_by']}', mode {r['mode']}; declaration sha256 {r['declaration_sha256']}; universe '{r['universe']['root']}' "
            f"(located at a directory named '{r['universe']['location_name']}'): {len(r['universe']['listing'])} files, names and sizes in SEAL.json")


def declaration_sha(d):
    """sha256 over the sorted (name, sha256) lines of the declaration's two files."""
    lines = "".join(f"{n}\0{registry.sha256_of(Path(d) / n)}\n" for n in sorted(FILES))
    return hashlib.sha256(lines.encode()).hexdigest()


def lines(p):
    """The JSON lines of an append-only log; a log never written has none (Path.is_file is the key of a two-row table)."""
    return {True: lambda: [json.loads(x) for x in Path(p).read_text().splitlines()], False: lambda: []}[Path(p).is_file()]()


def _append(p, rec):
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)   # append-only by open mode (the toolset t23 log discipline)
    os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode())
    os.close(fd)


def record(d):
    """SEAL.json as a value: {} when the declaration has none (Path.is_file is the key of a two-row table)."""
    return {True: lambda: json.loads((Path(d) / "SEAL.json").read_text()), False: lambda: {}}[(Path(d) / "SEAL.json").is_file()]()


def verify(declaration, d, t):
    """S2 SEAL in a run: always a Pass(SealState), the status looked up in STATUS. Never mints and never refuses (amendment A3)."""
    held = any(s["sha256"] == declaration_sha(d) for s in lines(Path(d) / "seal.log"))
    status = STATUS[((Path(d) / "SEAL.json").is_file(), held)]
    return Pass(SealState(status, said(t, status), record(d)))


def said(t, status):
    """The sentence of a seal status: its row of the seal stage's `status` in intake/STAGES.toml."""
    return {r["code"]: r["sentence"] for s in t["stages"]["stage"] if s["id"] == t["stages"]["seal_stage"] for r in s["status"]}[status.name]


def ordering(d, t):
    """The ordering note (information): (Ordering, its sentence) from SEAL.json's seal time and the access log's loader reads, read after the run; the sentence adds
    CONVERSION_READ_BEFORE_SEAL (n files) when conversion-access.log holds raw-file reads from before the seal (plan 1160 A13), and PROFILE_READ_BEFORE_SEAL (n files)
    from profile-access.log (plan 1165): information, never a refusal (converting and profiling before declaring is the designed order; no seal, no read precedes one)."""
    rec, reads = record(d), [a["t_ns"] for a in lines(Path(d) / "access.log") if a["route"] == "loader"]
    before = lambda log, part: {a["path"] for a in lines(Path(d) / log) if a["partition"] == part and a["t_ns"] < rec["sealed_at_ns"]}
    o, conv = ((list(Ordering)[1 + (len(reads) > 0) + any(r < rec["sealed_at_ns"] for r in reads)],
                                                                         (before("conversion-access.log", "converted-from"), before("profile-access.log", "profiled"))) if rec != {}
               else (Ordering.NOT_SEALED, (set(), set())))
    said = "".join({True: f" {a} ({len(c)} file{'s' * (len(c) != 1)}). {t['stages']['report'][k]}", False: ""}[len(c) > 0]   # plan 1165: and PROFILE_READ_BEFORE_SEAL
                   for a, k, c in zip(("CONVERSION_READ_BEFORE_SEAL", "PROFILE_READ_BEFORE_SEAL"), ("conversion_read", "profile_read"), conv))
    return o, {r["code"]: r["sentence"] for r in t["stages"]["report"]["ordering"]}[o.name] + said


def _git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return {True: r.stdout.strip(), False: "none"}[r.returncode == 0]


def listing(universe, glob):
    """The source universe as sorted [relative path, size] pairs: names and sizes only, never a byte of a file."""
    return sorted([q.relative_to(universe).as_posix(), q.stat().st_size] for q in Path(universe).glob(glob) if q.is_file())


SELECTED = {   # [selection] layout -> the file names it selects, relative to the source root; total over FORMAT's layouts (plan 1145)
    "PER_FILE": lambda sel: list(sel["files"]),   # format v3 (plan 1160 P1): the declared list, as written (a duplicate stays a duplicate)
    "LONG_TABLE": lambda sel: [sel["file"]],
}


def selected(sel):
    """The selected file names of a declaration's [selection], in curve order (PER_FILE: its `files`; LONG_TABLE: its one file)."""
    return SELECTED[sel["layout"]](sel)


SEEN = {"PROSPECTIVE": False, "RETROSPECTIVE_PREDECLARED": True, "EXPLORATORY": True}   # [intake] mode -> may a selected file exist at the seal; total (test)


def parts(decl, names):
    """The three parts the universe must be (plan 1160 P1), each a LIST of names in declared or listing order (never a set, so a name given
    twice is counted twice): selected (the selection's files), excluded (its excluded entries' files), truth_side (the universe names with a
    path part in [source] truth_side)."""
    src, sel = decl.data["source"], decl.data["selection"]
    return {"selected": selected(sel), "excluded": [e["file"] for e in sel["excluded"]], "truth_side": [n for n in names if set(Path(n).parts) & set(src["truth_side"])]}


def _write(d, decl, universe, who, root, tables):
    """SELECTION_DUPLICATE (a name twice within one part) | MODE_CONTRADICTS_SOURCE (plan 1160 P4: PROSPECTIVE, and a selected name is in
    the listing) | SELECTION_OUTSIDE_UNIVERSE (a selected name not in the listing) |
    UNIVERSE_NOT_PARTITIONED (universe != selected + excluded + truth_side with each name in exactly one part, or an excluded entry with an
    empty why), else the stamp. Details carry names and counts, never a byte of a file."""
    import schema
    have = listing(universe, decl.data["source"]["universe"])
    names = [n for n, _ in have]
    part = parts(decl, names)
    every = [x for p in part.values() for x in p]
    twice = sorted({x for p in part.values() for x in p if p.count(x) > 1})
    outside = sorted(set(part["selected"]) - set(names))
    seen = sorted(set(part["selected"]) & set(names))
    split = sorted({x for x in every if every.count(x) > 1} - set(twice))   # in two parts
    loose = sorted(set(names) - set(every)) + sorted(set(every) - set(names) - set(outside))   # in no part | a part's name not in the universe
    whyless = [e["file"] for e in decl.data["selection"]["excluded"] if e["why"].strip() == ""]
    broken = lambda: {"names in no part": len(set(names) - set(every)), "names in two parts": len(split), "excluded names not in the universe": len(set(every) - set(names) - set(outside)),
                      "excluded entries with no why": len(whyless)}
    return gate([(lambda: not twice, "SELECTION_DUPLICATE", lambda: detail(words=twice[:3], counts={"names given more than once in one part": len(twice)})),
                 (lambda: SEEN[decl.mode] or not seen, "MODE_CONTRADICTS_SOURCE",
                  lambda: detail(words=[f"mode {decl.mode}"] + seen[:3], counts={"selected files already in the universe listing": len(seen)})),
                 (lambda: not outside, "SELECTION_OUTSIDE_UNIVERSE", lambda: detail(words=outside[:3], counts={"selected files not in the universe listing": len(outside)})),
                 (lambda: not (split or loose or whyless), "UNIVERSE_NOT_PARTITIONED", lambda: detail(words=(split + loose + whyless)[:3], counts=broken()))],
                lambda: _stamp(d, decl, universe, have, who, root, tables, schema, {k: len(v) for k, v in part.items()}))


def _stamp(d, decl, universe, have, who, root, tables, schema, counts):
    sha = declaration_sha(d)
    t = time.time_ns()
    _append(Path(d) / "seal.log", {"t_ns": t, "sha256": sha, "file": "SEAL.json"})   # the seal time IS the log time
    rec = {
        "schema": 1, "kind": "intake-seal", "id": decl.id, "sealed_at_ns": t, "sealed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t // 10**9)),
        **who, "mode": decl.mode, "declaration_sha256": sha, **dict(zip(("profile_sha256", "conversion_manifest_sha256"), intake_bytes.intake_profile.read(d, universe, Path.read_bytes)[1::2])),   # plan 1165, A1
        "files": {n: registry.sha256_of(Path(d) / n) for n in FILES},
        "code_identity": {"commit": schema.git_head(root), "code_hash": schema.code_hash(root),
                          "tree": "CLEAN" if _git(root, "status", "--porcelain", "--", "cc", "bin/cc") == "" else "UNCOMMITTED_CHANGES"},
        "protocol_identity": {n: {"sha256": registry.sha256_of(Path(root) / "intake" / n), "version": tables[k]["version"]}
                              for n, k in (("STAGES.toml", "stages"), ("POLICY.toml", "policy"), ("FORMAT.toml", "format"))},
        "universe": {"root": decl.data["source"]["root"], "location_name": Path(universe).resolve().name, "glob": decl.data["source"]["universe"], "listing": have,
                     "partition": counts},   # plan 1160 P1: the count of names in each part, counted as lists
        "claim": tables["stages"]["report"]["seal_claim"],
    }
    (Path(d) / "SEAL.json").write_text(json.dumps(rec, indent=1) + "\n")
    return Pass(SealState(SealStatus.SEALED, said(tables, SealStatus.SEALED), rec))


def mint(declaration, d, who, root, tables):
    """bin/cc intake seal, after S0 passed: ALREADY_SEALED | UNIVERSE_ROOT_ABSENT | _write's rows, or append the seal-log line and
    write SEAL.json. `who` = {author, author_kind, confirmed_by}. The universe is the directory the declared [source] root names through
    the tables' roots (plan 1160 A20: was a --universe flag), the very directory S3 lists, so a seal cannot list another one."""
    universe = intake_bytes.located(declaration.data["source"]["root"], tables["roots"])   # "" when the root names no declared root
    return {True: lambda: Refuse("ALREADY_SEALED", detail(words=["SEAL.json exists; a seal is never replaced"])),
            False: lambda: {False: lambda: Refuse("UNIVERSE_ROOT_ABSENT", detail(words=[f"root '{declaration.data['source']['root']}' names no directory on this machine"])),
                            True: lambda: _write(d, declaration, Path(universe), who, root, tables)}[universe != "" and Path(universe).is_dir()]()}[(Path(d) / "SEAL.json").is_file()]()
