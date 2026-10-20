"""intake_against - the cross-check (plan 1165 section 5; role intake_against, its own cap tests/test_budget.py AGAINST_CAP, split from
cc/intake_profile.py by plan 1165 D5): a declaration against the PROFILE of the files it names, by `bin/cc intake profile <id> --check`
and by S3. Invariants: it reads no data byte (PROFILE.json, the declaration, the bank's conversion manifest are plain values); a contradiction is a row
of Contradiction; every live S4 / S4 reader / S5 reason is in PREDICTS or NOT_PREDICTABLE (tests/test_intake_profile.py)."""
import enum
from dataclasses import replace

import intake_read
import intake_seal
from intake_blind import Refuse
from intake_names import masked, split_unit

R = Contradiction = enum.Enum("Contradiction", "FILE_NOT_PROFILED ENCODING_CONTRADICTS_PROFILE DELIMITER_CONTRADICTS_PROFILE HEADER_CONTRADICTS_PROFILE "
                                 "COLUMN_CONTRADICTS_PROFILE CELLS_CONTRADICT_PROFILE WIDTH_CONTRADICTS_PROFILE ORDER_CONTRADICTS_PROFILE REPEATS_CONTRADICT_PROFILE SHEET_CONTRADICTS_PROFILE FILES_CONTRADICT_PROFILE")
PREDICTS = {   # plan 1165 section 5: a live S4 / S4 reader / S5 reason a byte-level fact can raise -> the Contradiction that precedes it (test)
    "NOT_UTF8": R.ENCODING_CONTRADICTS_PROFILE, "ROW_WIDTH_DIFFERS": R.WIDTH_CONTRADICTS_PROFILE, "COLUMN_NAME_ABSENT": R.COLUMN_CONTRADICTS_PROFILE,
    "COLUMN_NAME_AMBIGUOUS": R.COLUMN_CONTRADICTS_PROFILE, "COLUMN_POSITION_OUT_OF_RANGE": R.COLUMN_CONTRADICTS_PROFILE,
    "CELL_NOT_A_NUMBER": R.CELLS_CONTRADICT_PROFILE, "HEADER_LINE_ABSENT": R.HEADER_CONTRADICTS_PROFILE, "NO_DATA_ROW": R.HEADER_CONTRADICTS_PROFILE,
    "SHEET_ABSENT": R.SHEET_CONTRADICTS_PROFILE, "COLUMNS_DIFFER": R.FILES_CONTRADICT_PROFILE, "ROW_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
    "FILE_DIFFERS_FROM_FIRST": R.FILES_CONTRADICT_PROFILE, "FAST_VALUE_REPEATED": R.REPEATS_CONTRADICT_PROFILE, "ACQUISITION_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
}
NOT_PREDICTABLE = {   # plan 1165 section 5: the live reasons no profile can precede, each with why (test: PREDICTS + this = every live S4, S5 reason)
    "CURVE_REPEATED": "a slow value's recurrence is a value fact, and the profile holds no value", "SLOW_KEY_UNRESOLVED": "a FILE_KEY slow value is a header cell's value, which the profile masks",
    "REPLICATE_KEY_UNRESOLVED": "a replicate key is a value of a file name field or a column, which the profile does not hold", "UNIT_DIFFERS": "a unit is compared as declared text; the profile masks every numeral in it",
    "NOT_AN_XLSX": "openpyxl's parse of the cells, not a structure the profile states", "XLSX_READER_ABSENT": "a fact of the machine that runs the reader, not of the files",
    "READER_NOT_LIVE": "a fact of the declaration's reader name, not of the files", "READER_REFUSED": "the wrapper of a reader reason; each reader reason has its own row",
}
NUMERIC, PREDICTED = ("NUMERIC", "NUMERIC_WITH_EMPTY"), "the profile did not predict this"
SPEC = {"csv-curve-v1": lambda d: intake_read.CSV_CURVE, "table-curve-v1": lambda d: d["reader"]}   # a live [reader] name -> the spec its reader reads by
NAMES = {"NAMES_UNITS_IN_NAMES": lambda h, cs: [split_unit(c, h["unit_syntax"])[0] for c in cs]}   # [reader.header] kind -> its names from the line's cells
OPPOSITE = {"ASCENDING": "DESCENDING", "DESCENDING": "ASCENDING", "UNORDERED": "(none)"}   # a direction -> the first_direction that contradicts it
NONE = {"rows": [], "header_lines": [], "columns": [], "widths": [], "delimiter": "NONE"}   # no table the declared reader reads (no sheet; no text table)
COLUMN = {"text": 0, "empty": 0, "monotone_runs": 1, "first_direction": "FLAT", "equal_runs": [0], "revisited": 0}   # a declared column the names do not resolve


def _facts(fp, spec, d, ops):
    """What the declared reader meets in one profiled file, from its profile alone (intake_read's steps): the table (an XLSX's declared sheet, by
    position or masked name), the live runs (no BLANK, no declared comment prefix), the lines before the first NUMERIC run, the masked names
    (None when the names line lies beyond the 12 header lines profiled: then no column is checked), the width, each declared column's profile."""
    want = {True: lambda: spec["format"]["sheet"], False: lambda: 0}[spec["format"]["kind"] == "XLSX"]()
    tabs = [(0, "", t) for t in fp["tables"]] + [(s["position"], s["name"], s["table"]) for s in {True: fp["sheets"], False: []}[isinstance(fp["sheets"], list)]]
    t = next((t for k, n, t in tabs if k == want or n == masked(str(want))), NONE)
    live = [r for r in t["rows"] if r["kind"] != "BLANK" and not any(r["prefix"].startswith(p) for p in spec["comment"])]
    i, h = next((i for i, r in enumerate(live) if r["kind"] in NUMERIC), len(live)), spec["header"]
    head, at = [n for r in live[:i] for n in range(r["first"], r["last"] + 1)], {"names": 0, **intake_read.HEADER[h["kind"]](h)}["names"]
    cells = next((x["cells"] for x in t["header_lines"] if x["line"] == ([0] + head)[at * (at <= len(head))]), {True: [], False: None}[at * (at <= len(head)) == 0])
    names = {True: lambda: NAMES.get(h["kind"], lambda h, cs: list(cs))(h, cells), False: lambda: None}[cells is not None]()
    k = {str: lambda r: ([j for j, n in enumerate(names or [], 1) if n == masked(r)] + [0])[0], int: lambda r: r}
    return dict(fp=fp, t=t, live=live, body=live[i:], i=i, head=head, names=names, width={True: len(cells or ()), False: ([r["width"] for r in live[i:]] + [0])[0]}[bool(cells)],
                col=lambda r: next((c for c in t["columns"] if c["position"] == k[type(r)](r)), COLUMN), spec=spec, d=d, ops=ops,
                score={w: max([n for x, n in h if x >= 2], default=0) for w, h in t["widths"]}, refs=[r for _, r in intake_read.role_columns(d)])


ACQ = lambda d: {"ACQUISITION": d["acquisition"]["direction"]}.get(d["acquisition"]["row_order"], d["acquisition"]["row_order"])   # the direction a curve holds
ONE = lambda c: c["d"]["selection"]["layout"] == "PER_FILE"   # ORDER, REPEATS, FILES: a PER_FILE file is one curve (a LONG_TABLE's blocks are no profile fact)
FAST = lambda c: c["col"]((c["refs"] + [0])[0])   # the fast column's profile (role_columns: the fast column first; no column: COLUMN)
HOLDS = {   # Contradiction -> (holds over one file's facts, where it is: positions, counts, masked names); every row but FILE_NOT_PROFILED, FILES (in against)
    R.ENCODING_CONTRADICTS_PROFILE: (lambda c: c["fp"]["encoding"] in ("UTF16", "LATIN1_ONLY") and "DECODE" not in c["ops"], lambda c: f"encoding {c['fp']['encoding']}, no DECODE"),
    R.DELIMITER_CONTRADICTS_PROFILE: (lambda c: "DELIMITER" not in c["ops"] and (c["fp"]["kind"] != {True: "XLSX", False: "TEXT_TABLE"}[c["spec"]["format"]["kind"] == "XLSX"] or c["score"].get(
        c["spec"]["format"]["kind"], 0) < c["score"].get(c["t"]["delimiter"], 0)), lambda c: f"{c['fp']['kind']}, delimiter {c['t']['delimiter']}; declared {c['spec']['format']['kind']}"),
    R.SHEET_CONTRADICTS_PROFILE: (lambda c: c["fp"]["kind"] == "XLSX" == c["spec"]["format"]["kind"] and isinstance(c["fp"]["sheets"], list) and c["t"] is NONE,
                                  lambda c: f"sheet {masked(str(c['spec']['format'].get('sheet', '')))} declared, {len(c['fp']['sheets'])} sheets"),
    R.HEADER_CONTRADICTS_PROFILE: (lambda c: c["t"] is not NONE and (c["i"] == len(c["live"]) or len(c["head"]) != c["spec"]["header"]["rows"]),
                                   lambda c: f"header rows {c['spec']['header']['rows']} declared, {len(c['head'])} lines before the first numeric line"),
    R.COLUMN_CONTRADICTS_PROFILE: (lambda c: c["t"] is not NONE and c["names"] is not None and any({str: lambda r: c["names"].count(masked(r)) != 1 and (masked(r) == r or masked(r) not in c["names"]),
                                   int: lambda r: not 1 <= r <= c["width"]}[type(r)](r) for r in c["refs"]), lambda c: f"columns {[masked(str(r)) for r in c['refs']]} declared; names {c['names']}, width {c['width']}"),
    R.WIDTH_CONTRADICTS_PROFILE: (lambda c: any(r["width"] != c["width"] for r in c["body"]), lambda c: f"line {([r['first'] for r in c['body'] if r['width'] != c['width']] + [0])[0]}: width not {c['width']}"),
    R.CELLS_CONTRADICT_PROFILE: (lambda c: "TEXT_RUN" in c["ops"] or "DROP_ROWS_NOT_NUMERIC" not in c["ops"] and (any(c["col"](r)["text"] + c["col"](r)["empty"] > 0 for r in c["refs"]) or any(
        r["kind"] == "TEXT" and r["numbers"] == 0 for r in c["body"])), lambda c: "a declared column holds text or empty cells, or a text run lies in the body or was dropped as rows (D2: BLOCKS)"),
    R.ORDER_CONTRADICTS_PROFILE: (lambda c: ONE(c) and ACQ(c["d"]) != "UNORDERED" and (FAST(c)["monotone_runs"] > 1 or FAST(c)["first_direction"] == OPPOSITE[ACQ(c["d"])]),
                                  lambda c: f"fast column: {FAST(c)['monotone_runs']} monotone runs, first {FAST(c)['first_direction']}; declared {ACQ(c['d'])}"),
    R.REPEATS_CONTRADICT_PROFILE: (lambda c: ONE(c) and c["d"]["knobs"]["fast"]["control"] == "SET" and FAST(c)["revisited"] + sum(FAST(c)["equal_runs"]) * (
        c["d"]["replicate"]["identity"] != "SAME_FAST_VALUE") > 0, lambda c: f"fast column: equal runs {FAST(c)['equal_runs']}, {FAST(c)['revisited']} revisited; control SET"),
}


def against(p, m, d):
    """Plan 1165 section 5: the contradictions (code, file, where) of an S0-admitted declaration's data d against a profile p (PROFILE.json's
    values) and a conversion manifest m ({} for none); reads no byte. A reader that is not live has none (READER_NOT_LIVE is not predictable)."""
    ops, have, names = {x[k]: [s["op"] for s in x["steps"]] + ["TEXT_RUN"] * any(e == "TEXT" and n == 0 for u in m["units"] if u["file"] == i for e, n in zip(u["cell_kind"], u["numbers"])) for i, x in enumerate(m.get("files", [])) for k in ("from", "to")}, {f["name"]: f for f in p["files"]}, intake_seal.selected(d["selection"])   # P5: a dropped TEXT run
    facts = [(n, _facts(have[n], SPEC[d["reader"]["name"]](d), d, ops.get(n, []))) for n in names if n in have and d["reader"]["name"] in SPEC]
    lines = {tuple(c["names"] or ()) for _, c in facts} | {tuple(masked(str(r)) for r in c["refs"]) for _, c in facts if d["reader"]["name"] == "csv-curve-v1"}
    return (tuple((R.FILE_NOT_PROFILED, n, "not in the profile") for n in names if n not in have) + tuple((code, n, said(c)) for n, c in facts for code, (holds, said) in HOLDS.items() if holds(c))
            + tuple((R.FILES_CONTRADICT_PROFILE, n, f"{len(lines)} names lines across {len(facts)} files") for n, c in facts[:1] if ONE(c) and len(lines) > 1))


def unpredicted(pinned, got):
    """S4 / S5's result, its Detail ending "the profile did not predict this" when it refuses a PREDICTS reason on a profiled run (a hole in section 5)."""
    hole = isinstance(got, Refuse) and pinned.profile != {} and bool({got.reason, *got.evidence.words[:1]} & set(PREDICTS))
    return {True: lambda: Refuse(got.reason, replace(got.evidence, words=got.evidence.words + (PREDICTED,))), False: lambda: got}[hole]()
