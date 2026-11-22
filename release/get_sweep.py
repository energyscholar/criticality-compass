"""get_sweep - plan 1644 D6: every `.get(` call of cc/ is a row of release/get-sweep.toml with a class and a ruling; tests/test_get_sweep.py asserts the table is total.
Classes: V validator probing a declaration (cc/declare.py, cc/author.py) · T module-level code table (the only class the rule bans) · E os.environ / CLI options ·
R stored record (a field added after the record was written) · O declared-optional field of an input (the row names the schema line that declares it; none = F4 finding).
Identity of a row: (file, scope, receiver, ordinal). Usage: get_sweep.py [ROOT]  -> TOML on stdout."""
import ast
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = {"st", "res", "rec", "stored", "row", "other", "out", "got", "code", "codes", "notes", "direct", "pinned", "hits", "truth", "tr", "reads", "rank", "s"}
SCHEMA_DIRS = ("inputs", "intake", "instruments", "families", "tables", "registry.toml", "cc.toml")
# plan 1644 D6 rulings for class T, one by one: (file, receiver) -> (ruling, why)
T_RULING = {
    ("cc/intake_against.py", "NAMES"): ("FIX", "G-FIX-1: row for every header kind of the alphabet, then index"),
    ("cc/intake_profile.py", "CUT"): ("FIX", "G-FIX-2: explicit no-delimiter row(s), then index"),
    ("cc/intake_profile.py", "BIN"): ("FIX", "G-FIX-3: every key 0..10 present, then index"),
    ("cc/intake_differs.py", "HEADER[spec['header']['kind']](spec['header'])"): ("FIX", "G-FIX-4: every header row returns names, then index"),
    ("cc/oracle_measured.py", "{(True, True, False): 'BRACKET'}"): ("FIX", "G-FIX-6: a total 8-row table over the three bools, then index"),
    ("cc/declare.py", "TEMPLATES"): ("KEEP", "G-FIX-5: the validator's membership test; the None becomes a finding"),
    ("cc/declare.py", "SECTION_HINT"): ("KEEP", "G-KEEP-1: advisory message text, partial by design"),
    ("cc/declare.py", "HINT"): ("KEEP", "G-KEEP-2: advisory message text, partial by design"),
    ("cc/declare.py", "SIDECAR_OPT"): ("KEEP", "G-KEEP-3: advisory, partial by design"),
    ("cc/resources.py", "PLATFORMS"): ("KEEP", "G-KEEP-4: the None becomes a typed refusal at once (_no_row)"),
    ("cc/score.py", "T.axes"): ("KEEP", "G-KEEP-5 (Auditor A3): reads a FROZEN rule set; making it total edits sealed tables (F5)"),
    ("cc/score.py", "T.verdict"): ("KEEP", "G-KEEP-6 (Auditor A3): reads a FROZEN rule set (F5)"),
    ("cc/score.py", "T.verdict.get('class_of', {})"): ("KEEP", "G-KEEP-6 (Auditor A3): reads a FROZEN rule set (F5)"),
    ("cc/view.py", "T.membership"): ("KEEP", "G-KEEP-7 (Auditor A3): reads a FROZEN rule set (F5)"),
}


def _up(parent, n):
    while n in parent:
        n = parent[n]
        yield n


def scope(parent, n):
    names = [p.name for p in _up(parent, n) if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return ".".join(reversed(names)) or "<module>"


def schema_line(root, key):
    """First `file:line` of a schema/config text naming `key`, else '' (an F4 finding for the report)."""
    if not key:
        return ""
    pat = re.compile(r"(^|[^\w])" + re.escape(key) + r"([^\w]|$)")
    for d in SCHEMA_DIRS:
        p = root / d
        for f in ([p] if p.is_file() else sorted(p.rglob("*.toml")) if p.is_dir() else []):
            for i, ln in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if pat.search(ln):
                    return f"{f.relative_to(root).as_posix()}:{i}"
    return ""


def classify(rel, recv, root_name, tables, key):
    if (rel, recv) in T_RULING:
        return "T", *T_RULING[(rel, recv)]
    if rel in ("cc/declare.py", "cc/author.py"):
        return "V", "KEEP", "(a) the validator probes a declaration for a missing key in order to refuse it"
    if recv.startswith("os.environ") or recv == "env":
        return "E", "KEEP", "(d) environment / option: absence is a declared state"
    if (rel, recv) in T_RULING or root_name in tables or recv in tables or re.fullmatch(r"[A-Z_]+", root_name):
        r = T_RULING.get((rel, recv))
        return "T", r[0] if r else "UNRULED", r[1] if r else "a module-level code table: unruled"
    if root_name in RECORD or recv.split("[")[0] in RECORD:
        return "R", "KEEP", "(c) a stored record: a field added after the record was written"
    return "O", "KEEP", "(b) a field the input declares optional: absence is a declared state"


def sweep(root=ROOT):
    rows = []
    for f in sorted((root / "cc").rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel, src = f.relative_to(root).as_posix(), f.read_text()
        t = ast.parse(src)
        parent = {c: p for p in ast.walk(t) for c in ast.iter_child_nodes(p)}
        tables = {tg.id for n in t.body if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Dict, ast.DictComp)) for tg in n.targets if isinstance(tg, ast.Name)}
        seen = collections.Counter()
        for n in sorted((x for x in ast.walk(t) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "get" and 1 <= len(x.args) <= 2), key=lambda x: (x.lineno, x.col_offset)):
            recv = ast.unparse(n.func.value)
            root_name = re.split(r"[.\[(]", recv)[0]
            key = n.args[0].value if isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str) else ""
            cls, ruling, why = classify(rel, recv, root_name, tables, key)
            sc = scope(parent, n)
            seen[(rel, sc, recv)] += 1
            rows.append({"file": rel, "scope": sc, "recv": recv, "n": seen[(rel, sc, recv)], "line": n.lineno, "key": key, "default": ast.unparse(n.args[1])[:60] if len(n.args) == 2 else "", "class": cls, "ruling": ruling, "why": why,
                         "schema": schema_line(root, key) if cls == "O" else ""})
    return rows


def toml_text(rows):
    q = lambda s: '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'   # noqa: E731
    return "# release/get-sweep.toml: every `.get(` call of cc/ (plan 1644 D6). `line` is where the row was at the base; identity is (file, scope, recv, n). class O with schema = \"\" is an F4 finding (reported, not fixed here).\n" + "".join(
        f"\n[[row]]\nfile = {q(r['file'])}\nscope = {q(r['scope'])}\nrecv = {q(r['recv'])}\nn = {r['n']}\nline = {r['line']}\nkey = {q(r['key'])}\ndefault = {q(r['default'])}\nclass = {q(r['class'])}\nruling = {q(r['ruling'])}\nwhy = {q(r['why'])}\nschema = {q(r['schema'])}\n" for r in rows)


if __name__ == "__main__":
    sys.stdout.write(toml_text(sweep(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)))
