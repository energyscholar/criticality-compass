"""intake_plant - planted inputs shared by the plan-1145 intake tests (test_intake_read, test_intake_long, test_intake_reach): a minimal xlsx
writer, the synthetic bank's declaration as PER_FILE and as LONG_TABLE, and an in-process run of every stage. It reads no real data."""
import io
import re
import zipfile
from pathlib import Path

import intake
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


CHOICES = {"intake.mode": '"PROSPECTIVE"', "source.admissibility": '"RAW"', "acquisition.mode": '"INDEPENDENT"', "acquisition.direction": '"UNORDERED"', "acquisition.row_order": '"ASCENDING"',
           "interval.method": '"iid"', "bracket.required": '"CANDIDATE_BRACKET"', "projection.lane": '"PRIMARY"', "projection.from": '"C"', "projection.to": '"C_max"',
           "projection.bias": '"MAX_MEASURED"', "projection.keeps": '"the largest C on each curve"', "projection.discards": '"every other point"',
           "bridge.lane": '"PRIMARY"', "bridge.on": '"C_max"', "bridge.template": '"CHAIN_SLOW"', "bridge.bias": '"CHAIN_SLOW"', "shift.c": "0.0"}
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
    text = intake.fill((ROOT / "intake" / "TEMPLATE.intake.toml.in").read_text().replace("<ID>", ident), {**values, **CHOICES}, dropped)
    return text.replace('method = "iid"', 'method = "iid"\nresamples = 1000\nlevel = 0.95\nseed = 1145\ntau_declared = 1').replace("<intake-synth>/", "<long-test>/")


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
    return intake.fold(T["stages"]["stage"], intake.bodies(rooted(T, tmp), d, text, list(findings)))


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


