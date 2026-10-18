"""intake.py — the shared intake record of the real-data adapters (plan 0923 §1; design: plan 0902 §2). Role kernel (plan 0907).

Declarations: m.toml [ADAPT-SERIES-v1], [ADAPT-FRAMES-v1], [INTAKE-REAL-FORMAT] (Argus) — NONE WRITTEN when this module was built. This module
therefore fixes NO set grammar, NO axis-role vocabulary, NO unit, NO file list and NO pinned sha: all of them are fields of a `Declaration` argument,
and in a scored or real run the only source of a Declaration is those m.toml sections. The unit tests use labelled FIXTURES, never a declaration.

STRUCTURE
S1 Every byte an adapter sees is read by the frozen T23 Loader (studies/TAX-B1b/t23.py, route "loader"): its access-log line, with the sha256 of the
   bytes, is appended BEFORE the bytes are returned. The format reader (studies/TWINS/formats.py, unchanged) then parses a private COPY of exactly
   those bytes in a fresh temporary directory (an undeclared partition), so the reader never re-opens the source: the parsed bytes ARE the logged
   bytes, by construction.
S2 Hash pin (T21): each file is given with its pinned sha256; intake refuses unless the sha of the logged bytes equals the pin.
S3 The intake `Record` holds FORMAT FIELDS ONLY: path, raw sha, size, shape, dtype, the declared columns (name, role, unit), the declared control
   (its value is parsed from the PATH by the declared pattern, never from data), the declared header keys of the reader's metadata, the reduction
   label and the read route. No field of it is built from a data value.
S4 Data values live only in a `Raw` (read-only array; a write raises). The ONLY reduction type is `ConstantShift` (one constant per declared column:
   T(x) = x + c, the one pre-A admissible transform) and `kernel_input(raw, shift)` is the only route from a Raw to kernel input. Every other reduction
   is a separate labelled analysis outside this module (T21): there is no type for it here.
S6 ADMISSION BEFORE READ (plan 0923 P3, m.toml [TAX-T14-v1] intake_finding): whether a path is read at all is a TOTAL lookup over three booleans of the
   PATH and the pin list alone (truth-side component present, declared control matched exactly once, pin present) — `admission`. Only the one
   admitted cell reaches `read_logged`; every refused cell returns before it, so a refused path has NO loader line (for a theory file the read
   itself is the leak).
S5 Outcomes are values: Admitted(record, raw) | Refused(path, reason). A reader refusal passes through with the reader's own reason.
"""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "studies/TAX-B1b"), str(ROOT / "studies/TWINS")]
import t23  # noqa: E402  (frozen T23 loader)
import formats  # noqa: E402  (the 0914 real-format readers, unchanged)

ROUTE = "t23-loader"


class Column(NamedTuple):
    name: str
    role: str                     # a word of the declared role vocabulary (T17/T22: control / geometry / replicate / ...)
    unit: str                     # as declared (SEAL-CHECKLIST item 6)


class Control(NamedTuple):
    name: str
    role: str
    unit: str
    pattern: str                  # regex with ONE group, matched against the full path string; it must match exactly once


class ConstantShift(NamedTuple):
    label: str
    offsets: tuple                # one constant per declared column


class Declaration(NamedTuple):
    set_id: str
    reader: Callable              # path -> formats.Admitted | formats.Refused
    extract: Callable             # (formats.Admitted, columns) -> ndarray | str (a str is the reason the file does not fit the declaration)
    column_axis: int              # the axis of the extracted array that runs over the declared columns
    columns: tuple
    control: Control
    header_keys: tuple            # reader-metadata keys copied into the record (format metadata only)
    shift: ConstantShift
    truth_side: tuple = ()        # path components that mark theory / truth-side files of the deposit (m.toml [TAX-T14-v1]: 'iPEPS'); () = none


class Record(NamedTuple):
    set_id: str
    path: str
    sha256: str
    size: int
    shape: tuple
    dtype: str
    columns: tuple
    control: Control
    control_value: float
    header: tuple
    reduction: str
    route: str


class Raw(NamedTuple):
    values: np.ndarray
    sha256: str
    column_axis: int


class Admitted(NamedTuple):
    record: Record
    raw: Raw


class Refused(NamedTuple):
    path: str
    reason: str


class Session:
    """One T23 Loader over the declared partitions ({path prefix: partition name}) and one append-only access log."""

    def __init__(self, partitions, access_log):
        self.loader = t23.Loader(partitions, access_log, hook=True)
        self.log = Path(access_log)


def read_logged(session, path):
    return session.loader.read(path)                              # S1: T23 R2 — logged before the bytes are returned


def sha(data):
    return hashlib.sha256(data).hexdigest()


def frozen(a):
    out = np.array(a)
    out.setflags(write=False)
    return out


def pin_ok(got, pin):
    return got == pin                                             # form: S2 — T21 hash pin, the logged bytes against the declared sha


def control_value(control, path):
    """The declared control parsed from the path: exactly one match -> float; zero or several -> None (honest null, refused by `intake`)."""
    hits = re.findall(control.pattern, str(path))
    return (None, *(float(h.replace("p", ".")) for h in hits[:1]), None)[min(len(hits), 2)]   # form: 'p' = decimal point (F1 names: 16p5 = 16.5); index = min(#matches, 2): none | the one | ambiguous


def parse_copy(data, name, reader):
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / name
        copy.write_bytes(data)
        return reader(copy)                                       # S1: the reader parses exactly the logged bytes


ADMIT = None                                                      # the one admitted cell of ADMISSION
ADMISSION = {                                                     # S6: (truth-side path, control matched exactly once, pinned) -> None | refusal
    (False, True, True): ADMIT,
    (False, True, False): "REFUSED_NOT_PINNED: no pin for this path",
    (False, False, True): "control {name}: pattern {pattern!r} does not match the path exactly once",
    (False, False, False): "REFUSED_NOT_PINNED_NOT_ADMITTED_PATH: no pin, and control {name}: pattern {pattern!r} does not match the path exactly once",
    (True, True, True): "REFUSED_THEORY_PATH: the path lies on the truth side of the deposit {truth_side}",
    (True, False, True): "REFUSED_THEORY_PATH: the path lies on the truth side of the deposit {truth_side}",
    (True, True, False): "REFUSED_NOT_PINNED_NOT_ADMITTED_PATH: no pin, and the path lies on the truth side of the deposit {truth_side}",
    (True, False, False): "REFUSED_NOT_PINNED_NOT_ADMITTED_PATH: no pin, and the path lies on the truth side of the deposit {truth_side}",
}


def admission(decl, path, pin):
    """S6: None (admit: the path may be read) or the refusal reason. Looks at the PATH and the pin only — never at bytes."""
    parts = Path(str(path)).parts
    key = (any(part in decl.truth_side for part in parts), control_value(decl.control, path) is not None, pin is not None)   # form: S6 — the 3 booleans
    cell = ADMISSION[key]
    return cell and cell.format(name=decl.control.name, pattern=decl.control.pattern, truth_side=decl.truth_side)   # form: S6 — None passes through


def intake(session, decl, path, pin):
    refusal = admission(decl, path, pin)                          # S6: BEFORE read_logged
    if refusal is not None:                                       # form: S5 — a refused path returns here, unread and unlogged
        return Refused(str(path), refusal)
    data = read_logged(session, path)
    got = sha(data)
    value = control_value(decl.control, path)
    if not pin_ok(got, pin):                                      # form: S2 — refused on a pin mismatch
        return Refused(str(path), f"sha256 {got} != pinned {pin}")
    parsed = parse_copy(data, Path(path).name, decl.reader)
    if isinstance(parsed, formats.Refused):                       # form: S5 — the reader's refusal passes through with its reason
        return Refused(str(path), "reader: " + parsed.reason)
    values = decl.extract(parsed, decl.columns)
    if isinstance(values, str):                                   # form: S5 — a file that does not fit the declaration is refused, not coerced
        return Refused(str(path), "declaration: " + values)
    raw = Raw(frozen(values), got, decl.column_axis)
    record = Record(decl.set_id, str(Path(path).resolve()), got, len(data), tuple(raw.values.shape), str(raw.values.dtype), decl.columns,
                    decl.control, value, tuple((k, parsed.meta[k]) for k in decl.header_keys), decl.shift.label, ROUTE)
    return Admitted(record, raw)


def kernel_input(raw, shift):
    """S4: raw + one constant per declared column, broadcast along the declared column axis. A wrong number of offsets is unrepresentable as
    output: the offsets are placed on a shape that has the raw column count on that axis, so a mismatch is a numpy reshape error."""
    shape = [1] * raw.values.ndim
    shape[raw.column_axis] = raw.values.shape[raw.column_axis]
    return frozen(raw.values + np.reshape(np.asarray(shift.offsets, dtype=float), shape))


def log_audit(session, records):
    """A4 evidence: (records whose (path, sha) has no loader line in the access log, number of in-process-bypass lines in it)."""
    lines = [json.loads(x) for x in session.log.read_text().splitlines()]
    logged = {(ln["path"], ln["sha256"]) for ln in lines if ln["route"] == "loader"}   # plumbing: select the loader lines
    missing = [r.path for r in records if (r.path, r.sha256) not in logged]           # plumbing: records without their logged read
    return missing, sum(ln["route"] == "in-process-bypass" for ln in lines)            # plumbing: count bypass lines


def record_lines(records):
    """The printed intake table: format fields only (S3)."""
    return [f"{r.set_id} {Path(r.path).name}: sha {r.sha256[:16]} size {r.size} shape {r.shape} dtype {r.dtype} "
            f"{r.control.name}={r.control_value:g} {r.control.unit} [{r.control.role}] reduction={r.reduction} route={r.route}; columns "
            + ", ".join(f"{c.name}[{c.role}, {c.unit}]" for c in r.columns) for r in records]
