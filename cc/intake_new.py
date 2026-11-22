"""intake_new - `bin/cc new intake <id> [--from-synth <sid>]`. Invariant: it never overwrites; it writes only declarations/<id>/, from the
two committed templates (and, with --from-synth, the synth MANIFEST's metadata); it prints nothing: `new` returns (exit code, text) and
bin/cc prints it; a refusal is a usage line with a Next."""
import json
import re
import tomllib
from pathlib import Path


def fill(text, values, dropped=frozenset()):
    """The template text with each `key = "TODO"` line of a [section] whose "section.key" is a key of `values` set to that TOML value, and
    without each line whose "section.key" is in `dropped`, or whose section is (its [section] line, its "# [section]:" comment line and every
    line under it): the fields of a VARIANT row that was not chosen."""
    out, sec = [], ""
    for ln in text.splitlines():
        sec, m, head = {True: ln.strip("[] "), False: sec}[ln.startswith("[")], re.match(r'(\w+) = "TODO"(.*)', ln), re.match(r"# \[([\w.]+)\]:", ln)
        about = [head[1]] if head is not None else [sec] + [f"{sec}.{x[1]}" for x in [m] if x is not None]
        kept = {True: lambda: [], False: lambda: [f"{m[1]} = {values[sec + '.' + m[1]]}{m[2]}" if m is not None and f"{sec}.{m[1]}" in values else ln]}
        out += kept[any(n in dropped for n in about)]()
    return "\n".join(out) + "\n"


def _write_new(root, d, ident, values, dropped, trans):
    d.mkdir(parents=True)
    (d / "intake.toml").write_text(fill((Path(root) / "intake" / "TEMPLATE.intake.toml.in").read_text().replace("<ID>", ident), values, dropped))
    (d / "transducer.toml").write_text(trans)
    todo = [f"  declarations/{ident}/{n}:{i}: {ln}" for n in ("intake.toml", "transducer.toml") for i, ln in enumerate((d / n).read_text().splitlines(), 1) if '"TODO"' in ln]
    return 0, (f"wrote declarations/{ident}/intake.toml and transducer.toml; {len(todo)} TODO lines remain (yours to choose):\n" + "\n".join(todo)
               + f"\n  Next: replace each TODO (docs/INTAKE-QUICKSTART.md shows a filled example), then bin/cc intake lint {ident}")


def _from_synth(root, d, ident, sid, synth):
    """The declaration filled from the synth MANIFEST, then the bank it declares profiled (plan 1165: <intake-synth>/<sid>), so the quickstart
    path does not change: S3 finds the PROFILE the user never asked for by name."""
    import intake, intake_profile, intake_synth   # intake_synth is test infrastructure: it knows the MANIFEST it wrote
    code, said = _write_new(root, d, ident, *intake_synth.declare(json.loads(synth.read_text()), ident, sid))
    p = intake_profile.profile(root, ident, f"<intake-synth>/{sid}", intake.tables(root))
    return code, said + f"\n  profiled <intake-synth>/{sid}: {len(p.files)} files, {len(p.findings)} findings (declarations/{ident}/PROFILE.md)"


def new(root, ident, sid):
    """bin/cc new intake <id> [--from-synth <sid>]: declarations/<id>/ from the committed templates; with --from-synth, the synth MANIFEST's
    metadata filled in (intake_synth.declare) and every choice left TODO. (exit code, the text bin/cc prints)."""
    d, synth = Path(root) / "declarations" / ident, Path(root) / tomllib.loads((Path(root) / "intake" / "ROOTS.toml").read_text())["root"]["<intake-synth>"] / sid / "MANIFEST.json"
    blank = lambda: _write_new(root, d, ident, {}, frozenset(), (Path(root) / "inputs" / "TEMPLATE.transducer.toml.in").read_text().replace("<ID>", ident))
    filled = lambda: _from_synth(root, d, ident, sid, synth)
    usage = [u for ok, u in ((re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", ident) is not None, f"an id (letters, digits, _ . -), not '{ident}'"),
                             (not d.exists(), f"declarations/{ident} exists; a declaration is never overwritten (choose another id)"),
                             (sid == "" or synth.is_file(), f"no synthetic bank '{sid}' (run bin/cc intake synth {sid} --seed N first)")) if not ok]
    return {True: lambda: (1, f"bin/cc new intake: refused, {'; '.join(usage)}\n  Next: bin/cc new intake <id> [--from-synth <synth-id>]"),
            False: blank if sid == "" else filled}[len(usage) > 0]()
