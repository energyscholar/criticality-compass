"""test_docs_match - plan 1634 T9-T11: the documents describe the tool as it is today.
T9 the man page is well formed (mandoc lint, no output). T10 the options of `compass hold --help` equal the options of the man page's OPTIONS section, both ways,
and its EXIT STATUS codes equal the wrapper's. T11 every `$ compass ...` and `$ bin/cc ...` line of README.md, HOWTO.md, TUTORIAL.md and the man page examples is in exactly
one of two declared tables: READONLY (run; where the document shows output under the command, the shown lines equal the actual output, trailing whitespace stripped,
a `...` line standing for lines left out) or NOT_RUN (it measures, writes or needs state from an earlier step; each with its reason). Needs mandoc on PATH."""
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAN = ROOT / "docs" / "man" / "compass.1"
DOCS = ("README.md", "HOWTO.md", "TUTORIAL.md", "docs/FIRST-HOUR.md", "docs/READING-THE-CODE.md", "docs/try-to-break-it.md", "AGENTS.md")   # plan 1639 T11 (declared edit): docs/FIRST-HOUR.md, docs/READING-THE-CODE.md, docs/try-to-break-it.md and AGENTS.md join the documents run here (plan 1639 5b)
ELIDE = ("…", "...")

# READONLY: (document, command, n-th occurrence of that command in the document) -> None (run as written) or "verify" (the record argument is replaced by a record the test made).
READONLY = {
    ("README.md", "compass help", 0): None, ("README.md", "bin/cc help", 0): None, ("README.md", "bin/cc show b7-at-line", 0): None,
    ("README.md", "bin/cc explain w2-potts 5", 0): None, ("README.md", "bin/cc validate", 0): None,
    ("README.md", "compass hold --list", 0): None,
    ("HOWTO.md", "bin/cc help --advanced", 0): None, ("HOWTO.md", "bin/cc explain b7-at-line-2 0.14->0.21", 0): None, ("HOWTO.md", "bin/cc explain x7a-bc 1.0->1.5", 0): None,
    ("HOWTO.md", "bin/cc explain x5n-bilayer-2 0.0 --tables v04-rules", 0): None, ("HOWTO.md", "bin/cc show x2-xy-line-3 --tables v04-rules", 0): None,
    ("TUTORIAL.md", "bin/cc show w2-potts", 0): None, ("TUTORIAL.md", "bin/cc explain w2-potts 5", 0): None,
    ("man", "compass hold --list", 0): None, ("man", "compass hold --dry ising production --needle settled", 0): None,
    ("man", "compass hold --verify compass-runs/<record>", 0): "verify",   # run on a record the test makes first
}
NOT_RUN = {  # every other command line of the documents, one by one: (document, command, n-th occurrence) -> why it is not run. A command in neither table FAILS the test.
    ('README.md', 'compass hold ising production --needle settled', 0): 'runs a hold: minutes of compute',
    ('README.md', 'bin/cc tables fork v01-rules my-rules', 0): 'writes a rulebook',
    ('README.md', 'bin/cc run w2-potts --tables my-rules --dry', 0): 'measures; needs the data root',
    ('README.md', 'bin/cc tables drop my-rules', 0): 'writes a rulebook',
    ('README.md', 'bin/cc new case potts-q4', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc new case potts-q4', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc new input w2b --like w2-potts --points 6,7', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc new input b7c --like b7-at-line --add-instrument along', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc data add w2-potts', 0): 'pins data files',
    ('HOWTO.md', 'bin/cc tables split mine --column two_start --value UNRES --verdict REFUSE-EQUIL', 0): 'writes a rulebook',
    ('HOWTO.md', 'bin/cc tables drop v01-rules', 0): 'writes a rulebook',
    ('HOWTO.md', 'bin/cc reverdict w2-potts --tables rv', 0): 'needs a stored result and a rulebook of an earlier step',
    ('HOWTO.md', 'bin/cc reverdict b7-at-line-2 --tables rv', 0): 'needs a stored result and a rulebook of an earlier step',
    ('HOWTO.md', 'bin/cc validate --input b7-at-line-2 --tables nomem', 0): 'needs a rulebook or file an earlier step of the document made',
    ('HOWTO.md', 'bin/cc new family b7-demo', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc family x7a-bc-lambda', 0): 'measures; needs the data root',
    ('HOWTO.md', 'bin/cc family x2b-xy --tables v05-rules', 0): 'measures; needs the data root',
    ('HOWTO.md', 'bin/cc new instrument foo', 0): 'writes a file',
    ('HOWTO.md', 'bin/cc tabulate --diff verdict-x-rules v01-rules', 0): 'writes SIGNATURE-TABLE.md',
    ('HOWTO.md', 'bin/cc run w2-potts --tables verdict-x-rules', 0): 'measures; needs the data root',
    ('HOWTO.md', 'bin/cc freeze w2-potts@verdict-x-rules', 0): 'writes read-only files; needs the structure checker',
    ('HOWTO.md', 'bin/cc tabulate', 0): 'writes SIGNATURE-TABLE.md',
    ('HOWTO.md', 'bin/cc tabulate --diff v01-rules scratch', 0): 'writes SIGNATURE-TABLE.md',
    ('HOWTO.md', 'bin/cc validate --mvt', 0): 'runs minutes; a test of its own covers it',
    ('HOWTO.md', 'bin/cc family x5n-g --tables v04-rules', 0): 'measures; needs the data root',
    ('TUTORIAL.md', 'bin/cc tables fork v01-rules scratch', 0): 'writes a rulebook',
    ('TUTORIAL.md', 'bin/cc run --all --tables scratch', 0): 'measures; needs the data root',
    ('TUTORIAL.md', 'bin/cc tables drop scratch --with-results', 0): 'writes a rulebook',
    ('TUTORIAL.md', 'bin/cc family b7-at-line-2', 0): 'measures; needs the data root',
    ('man', 'compass hold ising production --needle settled', 0): 'runs a hold: minutes of compute',
    ('HOWTO.md', 'bin/cc validate', 0): 'needs a rulebook or file an earlier step of the document made',
    ('TUTORIAL.md', 'bin/cc validate', 0): 'needs a rulebook or file an earlier step of the document made',
    ('TUTORIAL.md', 'bin/cc validate', 1): 'needs a rulebook or file an earlier step of the document made',
}


def cmd_args(cmd):
    return cmd.split()[1:]


def run_cc(args, cwd=ROOT):
    r = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), *args], capture_output=True, text=True, cwd=cwd, timeout=900)
    out = [x.rstrip() for x in (r.stdout + r.stderr).split("\n")]
    while out and not out[-1]:
        out.pop()
    return r.returncode, out


def man_text():
    r = subprocess.run(f"mandoc -T utf8 {MAN} | col -b", shell=True, capture_output=True, text=True)
    return r.stdout


def extract(lines, fenced):
    """-> [(command, shown lines)] for each `$ compass ` / `$ bin/cc ` line; shown = the lines under it up to the next `$ ` line, the closing fence or a blank line (man)."""
    out, fence = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
        s = ln.strip()
        if (fence or not fenced) and re.match(r"^\$ (compass|bin/cc) ", s):
            shown = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("```") or nxt.strip().startswith("$ ") or (not fenced and not nxt.strip()):
                    break
                shown.append(nxt.strip() if not fenced else nxt.rstrip())
            while shown and not shown[-1]:
                shown.pop()
            out.append((s[2:].split("  #")[0].strip(), shown))
    return out


def differs(shown, actual):
    """-> None when the shown lines match the actual output (a `...` line stands for lines left out), else the first difference."""
    shown = [x for x in shown]
    if not any(x.strip() in ELIDE for x in shown):
        return None if shown == actual[:len(shown)] and len(shown) == len(actual) else next((f"shown `{a[:60]}` vs actual `{b[:60]}`" for a, b in zip(shown + ["<end>"], actual + ["<end>"]) if a != b), "length")
    pos = 0
    for x in shown:
        if x.strip() in ELIDE:
            continue
        if x not in actual[pos:]:
            return f"shown line not found in order: `{x[:70]}`"
        pos = actual.index(x, pos) + 1
    return None


def t9():
    r = subprocess.run(["mandoc", "-T", "lint", "-W", "warning", str(MAN)], capture_output=True, text=True)
    check("T9 the man page is well formed (mandoc lint: exit 0, no output)", MAN.is_file() and r.returncode == 0 and not (r.stdout + r.stderr).strip(), (r.stdout + r.stderr)[:300] or "no docs/man/compass.1")


def section(text, name):
    m = re.search(r"(?ms)^" + name + r"\n(.*?)(?=^[A-Z][A-Z ]+$|\Z)", text)
    return m.group(1) if m else ""


def t10():
    text = man_text()
    helped = {o for o in re.findall(r"--[a-z][a-z-]*", "\n".join(run_cc(["hold", "--help"])[1]))} - {"--help"}
    doc = {o for o in re.findall(r"--[a-z][a-z-]*", section(text, "OPTIONS"))} - {"--help"}
    check("T10 options: `compass hold --help` and the man page OPTIONS name the same options", bool(doc) and helped == doc, f"only in --help: {sorted(helped - doc)}; only in the man page: {sorted(doc - helped)}")
    sys.path.insert(0, str(ROOT))
    try:
        from manual import record
        codes = {str(c) for c in record.EXIT.values()}
        names = set(record.EXIT)
    except ImportError:
        codes, names = set(), set()
    ex = section(text, "EXIT STATUS")
    doc_codes = set(re.findall(r"(?m)^\s+(\d+)\s", ex))
    check("T10 exit codes: the man page EXIT STATUS lists exactly the wrapper's codes", bool(codes) and doc_codes == codes, f"man {sorted(doc_codes)} vs wrapper {sorted(codes)}")
    check("T10 exit codes: every status word is named in EXIT STATUS", bool(names) and all(n in ex for n in names), str(sorted(n for n in names if n not in ex)))


def t11():
    items = []
    check("T11 docs/FIRST-HOUR.md exists (plan 1639)", (ROOT / "docs" / "FIRST-HOUR.md").is_file(), "no such file")
    for d in DOCS:
        if not (ROOT / d).is_file():
            continue
        seen = Counter()
        for cmd, shown in extract((ROOT / d).read_text().split("\n"), True):
            items.append((d, cmd, seen[cmd], shown))
            seen[cmd] += 1
    seen = Counter()
    for cmd, shown in extract(man_text().split("\n"), False):
        items.append(("man", cmd, seen[cmd], shown))
        seen[cmd] += 1
    check("T11 the documents hold commands to check", len(items) > 20, str(len(items)))
    both = [k for k in READONLY if k in NOT_RUN]
    check("T11 no command is in both tables", not both, str(both))
    recdir = tempfile.mkdtemp(prefix="t-docs-rec-")
    rec = None
    for d, cmd, n, shown in items:
        key = (d, cmd, n)
        if key in READONLY:
            args = cmd_args(cmd)
            if args[:2] == ["hold", "--verify"]:
                if rec is None:
                    world = Path(recdir) / "w.toml"
                    world.write_text(re.sub(r"(?m)^horizon\s*=.*$", "horizon = 1", (ROOT / "system-instantiated/plugins/ising/ising-apparatus-static.toml").read_text()))
                    run_cc(["hold", "ising", str(world), "--needle", "settled", "--out", recdir])[0]
                    rec = next(p for p in Path(recdir).iterdir() if p.is_dir())
                args = args[:2] + [str(rec)]
            rc, actual = run_cc(args)
            check(f"T11 {d}: `{cmd}` exits 0", rc == 0, f"rc={rc} {' / '.join(actual[-3:])[:200]}")
            norm = (lambda xs: [re.sub(r"\s+", " ", x).strip() for x in xs]) if d == "man" else (lambda xs: xs)   # the man renderer turns runs of spaces into tabs and indents literal blocks
            why = differs(norm(shown), norm(actual)) if shown else None
            check(f"T11 {d}: `{cmd}` runs and its shown output matches", why is None, why or "")
        else:
            check(f"T11 {d}: `{cmd}` (occurrence {n}) is in a declared table, READONLY or NOT_RUN", key in NOT_RUN, "in neither table: add it with a reason, or fix the document")
    stale = [k for k in list(READONLY) + list(NOT_RUN) if k not in {(d, c, n) for d, c, n, _ in items}]
    check("T11 no table row names a command the documents no longer hold", not stale, str(stale))


for name, fn in (("T9", t9), ("T10", t10), ("T11", t11)):
    guarded(name, fn)
print("test_docs_match: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
