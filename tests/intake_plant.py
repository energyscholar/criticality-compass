"""intake_plant - planted inputs shared by the plan-1145 intake tests (test_intake_read, test_intake_long, test_intake_reach): a minimal xlsx
writer, the synthetic bank's declaration as PER_FILE and as LONG_TABLE, and an in-process run of every stage. It reads no real data."""
import io
import re
import zipfile
from pathlib import Path

import intake
import intake_fold
import intake_new
import intake_synth

ROOT = Path(__file__).resolve().parent.parent


def xlsx(rows, sheet="data"):
    """A minimal xlsx workbook of one sheet (workbook, below)."""
    return workbook({sheet: rows})


def workbook(sheets):
    """A minimal xlsx workbook (inline strings, numbers as numbers), written with zipfile only: the planted xlsx file, one worksheet per
    {name: rows} entry in order (plan 1160 P3: a two-sheet workbook). A bytes value is written as a number cell's raw text (a workbook whose
    number cell does not parse); None is an empty cell."""
    def cell(i, j, v):
        ref = f"{'ABCDEFGH'[j]}{i}"
        return {str: lambda: f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>', bytes: lambda: f'<c r="{ref}"><v>{v.decode()}</v></c>',
                int: lambda: f'<c r="{ref}"><v>{v!r}</v></c>', float: lambda: f'<c r="{ref}"><v>{v!r}</v></c>'}[type(v)]()
    data = lambda rows: "".join(f'<row r="{i}">' + "".join(cell(i, j, v) for j, v in enumerate(r) if v is not None) + "</row>" for i, r in enumerate(rows, 1))   # None: an empty cell
    ks = range(1, len(sheets) + 1)
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                               '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                               + "".join(f'<Override PartName="/xl/worksheets/sheet{k}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for k in ks) + '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                           + "".join(f'<sheet name="{n}" sheetId="{k}" r:id="rId{k}"/>' for k, n in zip(ks, sheets)) + '</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      + "".join(f'<Relationship Id="rId{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{k}.xml"/>' for k in ks)
                                      + '</Relationships>',
        **{f"xl/worksheets/sheet{k}.xml": '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                                          f'<sheetData>{data(rows)}</sheetData></worksheet>' for k, rows in zip(ks, sheets.values())},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, s in parts.items():
            z.writestr(n, s)
    return buf.getvalue()


CHOICES = {"intake.mode": '"RETROSPECTIVE_PREDECLARED"',   # plan 1160 P4: PROSPECTIVE with the files present is S2 MODE_CONTRADICTS_SOURCE
           "source.admissibility": '"RAW"', "acquisition.mode": '"INDEPENDENT"', "acquisition.direction": '"UNORDERED"', "acquisition.row_order": '"ASCENDING"',
           "interval.method": '"STATED"', "bracket.required": '"CANDIDATE_BRACKET"', "projection.lane": '"PRIMARY"', "projection.from": '"C"', "projection.to": '"C_max"',
           "projection.bias": '"MAX_MEASURED"', "projection.keeps": '"the largest C on each curve"', "projection.discards": '"every other point"',
           "bridge.lane": '"PRIMARY"', "bridge.on": '"C_max"', "bridge.template": '"CHAIN_SLOW"', "bridge.bias": '"CHAIN_SLOW"', "shift.c": "0.0"}
IV = 'method = "STATED"'   # per_file's interval block. Plan 1160 P5: was iid, which S7 now refuses on a bank of one reading per point (ONE_READING_PER_POINT); the banks carry sigma
ALT = '\n[[projection]]\nlane = "ALTERNATIVE"\nfrom = "C"\nto = "{to}"\nbias = "{bias}"\nkeeps = "planted"\ndiscards = "planted"\n'
ALT_BRIDGE = '\n[[bridge]]\nlane = "ALTERNATIVE"\non = "{on}"\ntemplate = "CHAIN_SLOW"\nbias = "CHAIN_SLOW"\n'
NO_SIGMA = lambda t: re.sub(r'kind = "COLUMN"([^\n]*)\nkey = "sigma"[^\n]*\n', r'kind = "NONE"\1\n', t, count=1)   # [measured.uncertainty] kind NONE
CHOICE_PLANTS = [   # (1160 P4) one plant per live S1 CHOICES row, and the PASS controls: (code, what, an edit of a per_file declaration text).
    # tests/test_intake_reach.py runs each in process, tests/test_intake_leak.py through bin/cc intake lint | seal | run on its sentinel bank
    ("KNOBS_SAME_QUANTITY", "[knobs.slow] name T, the fast knob's", lambda t: t.replace('name = "h"', 'name = "T"', 1)),
    ("MEASURED_IS_A_KNOB", "[measured] key T, the fast knob's column", lambda t: t.replace('key = "C"', 'key = "T"', 1)),
    ("PROJECTION_REQUIRED", "shape PICTURE, and the bridge on the raw C", lambda t: t.replace('shape = "SCALAR_PER_LOCUS"', 'shape = "PICTURE"', 1).replace('on = "C_max"', 'on = "C"', 1)),
    ("PROJECTION_ESTIMAND_MIXED", "a second projection to C_max by ARGMAX_FAST (a location; MAX_MEASURED's is a height)", lambda t: t + ALT.format(to="C_max", bias="ARGMAX_FAST")),
    ("SECOND_LANE_MISSING", "origin EXPERIMENT with one lane", lambda t: t.replace('origin = "PLANTED"', 'origin = "EXPERIMENT"', 1)),
    ("LANES_IDENTICAL", "an ALTERNATIVE lane with the PRIMARY's projection and bridge", lambda t: t + ALT.format(to="C_max", bias="MAX_MEASURED") + ALT_BRIDGE.format(on="C_max")),
    ("REPLICATE_IS_SWEEP_NEIGHBOUR", "identity SEED keyed by T, the fast knob (1160 A33: the key a COLUMN T; was key = \"T\")",
     lambda t: t.replace('identity = "NONE"', 'identity = "SEED"', 1).replace('[replicate.key]\nkind = "NONE"', '[replicate.key]\nkind = "COLUMN"\ncolumn = "T"', 1)),
    ("OPERATION_NOT_PERMITTED", "the bridge PAIR_NEAREST_FAST on C_max (a derived observable; it pairs raw locus values)",
     lambda t: t.replace('template = "CHAIN_SLOW"', 'template = "PAIR_NEAREST_FAST"', 1).replace('bias = "CHAIN_SLOW"', 'bias = "PAIR_NEAREST_FAST"', 1)),
    ("OPERATION_NOT_PERMITTED", "a bridge on C_maxx, a name the chain does not hold", lambda t: t.replace('on = "C_max"', 'on = "C_maxx"', 1)),
    ("PROVENANCE_HAS_NO_KERNEL_ROUTE", "admissibility FIGURE_LEVEL", lambda t: t.replace('admissibility = "RAW"', 'admissibility = "FIGURE_LEVEL"', 1)),
    ("METHOD_NEEDS_UNCERTAINTY_COLUMN", "interval STATED, and [measured.uncertainty] kind NONE", lambda t: NO_SIGMA(t)),
    ("MEASURED_KNOB_HAS_NO_POINTS", "(1160 A17, T17.2) control MEASURED with identity SAME_FAST_VALUE", lambda t: MEASURED(SAME_FAST(t))),
    ("MEASURED_KNOB_HAS_NO_POINTS", "(1160 A17, T17.2) control MEASURED with interval iid", lambda t: MEASURED(IID(t))),
    ("SLOW_KNOB_HAS_NO_METRIC", "(1160 A35) [knobs.slow] kind ORDINAL: the slow knob an index, not a quantity", lambda t: ORDINAL(t)),
    ("PASS", "interval STATED with the sigma column (per_file's default since 1160 P5)", lambda t: t.replace(IV, 'method = "STATED"', 1)),
    ("PASS", "interval NONE (no interval; the file's sigma column is still declared, S4 reads every column)", lambda t: t.replace(IV, 'method = "NONE"', 1)),
    ("PASS", "origin EXPERIMENT with two lanes that differ (ALTERNATIVE: C to T_star by ARGMAX_FAST, chained)",
     lambda t: t.replace('origin = "PLANTED"', 'origin = "EXPERIMENT"', 1) + ALT.format(to="T_star", bias="ARGMAX_FAST") + ALT_BRIDGE.format(on="T_star")),
    ("PASS", "(1160 A17) control MEASURED with identity NONE and interval STATED", lambda t: MEASURED(t)),
]
# (1160 P5) the S7, S8, S9 edits of a per_file or long_table declaration text, shared by tests/test_intake_reach.py and tests/test_intake_leak.py
BLOCK = lambda mb: lambda t: t.replace(IV, f'method = "block"\nresamples = 1000\nlevel = 0.95\nseed = 1160\nb = 1\nmin_blocks = {mb}', 1)   # n // 1 >= mb per point
BLOCK_NO_FLOOR = lambda t: BLOCK(2)(t).replace("\nmin_blocks = 2", "", 1)   # (1160 A4) a block interval without min_blocks: S0 FIELD_MISSING
ORDINAL = lambda t: re.sub(r'(\[knobs\.slow\][^\[]*?\nkind = )"QUANTITY"', r'\1"ORDINAL"', t, count=1)   # (1160 A35) the slow knob declared ORDINAL
IID = lambda t: t.replace(IV, 'method = "iid"\nresamples = 1000\nlevel = 0.95\nseed = 1160\ntau_declared = 1', 1)
SAME_FAST = lambda t: t.replace('identity = "NONE"', 'identity = "SAME_FAST_VALUE"', 1)
MEASURED = lambda t: t.replace('control = "SET"', 'control = "MEASURED"', 1)   # (1160 A17) [knobs.fast] control MEASURED: every row a point
VALIDATED = lambda t: t.replace('required = "CANDIDATE_BRACKET"', 'required = "VALIDATED_BRACKET"', 1)
ARGMAX_LANE = lambda t: t.replace('origin = "PLANTED"', 'origin = "EXPERIMENT"', 1) + ALT.format(to="T_star", bias="ARGMAX_FAST") + ALT_BRIDGE.format(on="T_star")
PAIR_LANE = lambda t: (t.replace('origin = "PLANTED"', 'origin = "EXPERIMENT"', 1)
                       + '\n[[bridge]]\nlane = "ALTERNATIVE"\non = "C"\ntemplate = "PAIR_NEAREST_FAST"\nbias = "PAIR_NEAREST_FAST"\n')
PRIMARY_PAIR = lambda t: re.sub(r'(\[\[bridge\]\]\nlane = "PRIMARY"[^\n]*\non = )"[^"]*"([^\n]*\ntemplate = )"CHAIN_SLOW"([^\n]*\nbias = )"CHAIN_SLOW"',
                                r'\1"C"\2"PAIR_NEAREST_FAST"\3"PAIR_NEAREST_FAST"', t, count=1)   # (1160 P6) the PRIMARY bridge PAIR_NEAREST_FAST on raw C: S10 NO_KERNEL_ROUTE
ALL_ALTERNATIVE = lambda t: t.replace('lane = "PRIMARY"', 'lane = "ALTERNATIVE"')   # (1160 P6) the projection and the bridge both ALTERNATIVE: no PRIMARY bridge, S10 NO_KERNEL_ROUTE
SHIFT = lambda c: lambda t: re.sub(r"(\[shift\][^\[]*?\nc = )[^\n#]*", lambda m: m.group(1) + c + " ", t, count=1)   # (1160 P6) [shift] c restated (nan, inf: S10 DOOR_REFUSED)
LONG = '''# [reader]: VARIANT on name
[reader]
name = "table-curve-v1"
comment = ["#"]
[reader.format]
kind = "COMMA"
[reader.header]
{header}

[selection]
layout = "LONG_TABLE"
file = "bank.csv"
block = {block}
excluded = []
[selection.slow]
source = "COLUMN"
key = {slow}

'''


def per_file(m, ident):
    """The PER_FILE declaration text of a synth bank: the template filled by --from-synth's values and the choices above."""
    values, dropped, _ = intake_synth.declare(m, ident, "pf")   # the root names bank pf; a test re-points it
    text = intake_new.fill((ROOT / "intake" / "TEMPLATE.intake.toml.in").read_text().replace("<ID>", ident), {**values, **CHOICES}, dropped)
    return text.replace("<intake-synth>/", "<long-test>/")


def long_table(m, ident, header='kind = "NAMES"\nrows = 1\nnames = 1', slow='"h"', block='"EXACT"'):
    """The same declaration as a LONG_TABLE of bank.csv: [reader] table-curve-v1 and [selection] LONG_TABLE replace their PER_FILE blocks
    (plan 1160 P2: with its block rule, EXACT unless stated)."""
    text = per_file(m, ident)
    return re.sub(r"(?s)# \[reader\]:.*?(?=\[knobs\.slow\])", lambda _: LONG.format(header=header, slow=slow, block=block), text)


KEYED = '''# [reader]: VARIANT on name
[reader]
name = "table-curve-v1"
comment = ["#"]
[reader.format]
kind = "COMMA"
[reader.header]
kind = "NAMES"
rows = 2
names = 2
'''


def slow_source(text, source):
    """A PER_FILE declaration with [selection.slow] restated: FILE_KEY (key "h"; the reader table-curve-v1 with a key line above the names
    line, see key_lines) or NONE (no slow knob), in place of LISTED values (plan 1160 P1)."""
    body = {"FILE_KEY": 'source = "FILE_KEY"\nkey = "h"\n', "NONE": 'source = "NONE"\n'}[source]
    text = re.sub(r"(?s)source = \"LISTED\".*?\nvalues = \[.*?\].*?\n", lambda _: body, text, count=1)
    reader = {"FILE_KEY": lambda t: re.sub(r"(?s)# \[reader\]:.*?(?=# \[selection\]:)", lambda _: KEYED, t), "NONE": lambda t: t}[source]
    return reader(text)


def key_lines(bank, m, line=lambda h: f"h,{h}\n"):
    """Each curve file of a copied PER_FILE bank with a key line above its names line: `line(h)` (FILE_KEY's header line, plan 1160 P1)."""
    for f in m["files"]:
        (bank / f["name"]).write_text(line(f["h"]) + (bank / f["name"]).read_text())


def write_long(bank, blocks, head="T,C,sigma,h\n"):
    """One long file: each (h, rows) block's rows with h appended, in the given order."""
    (bank / "bank.csv").write_text("# the synthetic bank as one long table (plan 1145 test)\n" + head + "".join(f"{r},{h}\n" for h, rows in blocks for r in rows))


def run(T, tmp, ident, text, findings=()):
    """Every stage of one planted declaration folded in-process, the root name <long-test> naming <tmp>/banks; `findings` are planted CC
    transducer findings (S0 TRANSDUCER_FILE_REFUSED). A second run of one ident reuses its directory (its access.log and SEAL.json)."""
    d = Path(tmp) / "declarations" / ident
    d.mkdir(parents=True, exist_ok=True)
    (d / "intake.toml").write_text(text)
    return intake_fold.fold(T["stages"]["stage"], intake.bodies(rooted(T, tmp), d, text, list(findings)))


def rooted(T, tmp):
    """The tables with the root name <long-test> naming <tmp>/banks (plan 1160 P3: and <cc-datasets>, <cc-banks> naming <tmp>/cc-datasets,
    <tmp>/cc-banks, so a CONVERTED plant never reaches the machine's data roots)."""
    return {**T, "roots": {**T["roots"], "<long-test>": str(Path(tmp) / "banks"), "<cc-datasets>": str(Path(tmp) / "cc-datasets"), "<cc-banks>": str(Path(tmp) / "cc-banks")}}


def conversion(source, out, files):
    """(plan 1160 P3) A declarations/<id>/CONVERSION.toml: files is [(from, to, steps as TOML inline-table text)]."""
    return f'schema = 1\nkind = "conversion"\nsource = "{source}"\nout = "{out}"\n' + "".join(f'\n[[file]]\nfrom = "{a}"\nto = "{b}"\nsteps = [{st}]\n' for a, b, st in files)


def converted(T, tmp, name, files, raws):
    """(plan 1160 P3) Plant <tmp>/cc-datasets/<name>/raw (raws: {file: bytes}) and declarations/c-<name>/CONVERSION.toml, and convert it to
    <cc-banks>/<name>/bank: the converter's result."""
    import intake_convert
    raw = Path(tmp) / "cc-datasets" / name / "raw"
    raw.mkdir(parents=True)
    [(raw / f).write_bytes(b) for f, b in raws.items()]
    d = Path(tmp) / "declarations" / f"c-{name}"
    d.mkdir(parents=True)
    (d / "CONVERSION.toml").write_text(conversion(f"<cc-datasets>/{name}/raw", f"<cc-banks>/{name}/bank", files))
    return intake_convert.convert(tmp, f"c-{name}", rooted(T, tmp), intake_convert.ctables())


def outcome(out, sid):
    """("PASS", the evidence) when stage `sid` passed; else (the reason of the first refused stage, its result as text)."""
    first = [e.result for e in out.values() if e.mark is intake.Mark.REFUSED] + [None]
    return {True: lambda: ("PASS", out[sid].result.evidence), False: lambda: (getattr(first[0], "reason", out[sid].mark.name), str(first[0])[:300])}[out[sid].mark is intake.Mark.PASSED]()


