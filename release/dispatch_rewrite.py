"""dispatch_rewrite - plan 1644 D5: the sweep of bool-keyed dict dispatch and the CHECKED rewrite of a two-way branch spelt as a table.
`{True: lambda: a, False: lambda: b}[k]()` and `{True: x, False: y}[k]` (effect-free arms) become `a if k else b` / `x if k else y` ONLY where `k` is provably bool.
`Rewrite` (an ast.NodeTransformer) is the oracle: tests/test_dispatch_rewrite.py asserts ast_digest(Rewrite(base)) == ast_digest(head). `rewrite_text` makes the text edit (comments kept);
a site with a comment inside it, or inside an f-string (positions are unreliable before Python 3.12), is left for a hand edit and reported.
Usage: dispatch_rewrite.py sweep [ROOT]  -> the rows as TOML on stdout;  dispatch_rewrite.py rewrite FILE...  -> edit in place, print what was left for hand."""
import ast
import collections
import hashlib
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ("cc", "manual", "navigator", "needlestream", "needleview", "environment")   # plus bin/cc


def ser(n):
    if isinstance(n, ast.AST):
        return n.__class__.__name__ + "(" + ",".join(f"{f}={ser(v)}" for f, v in ast.iter_fields(n) if v is not None and v != []) + ")"
    return "[" + ",".join(ser(x) for x in n) + "]" if isinstance(n, list) else repr(n)


def ast_digest(src):   # the digest of tests/test_dist.py T3
    t = ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    return hashlib.sha256(ser(t).encode()).hexdigest()


def provably_bool(k):
    """A key that is a bool by its own syntax: a comparison, `not`, a bool literal, bool/isinstance/callable/all/any/hasattr(...), or `and`/`or` of those."""
    return (isinstance(k, ast.Compare) or isinstance(k, ast.UnaryOp) and isinstance(k.op, ast.Not) or isinstance(k, ast.Constant) and isinstance(k.value, bool)
            or isinstance(k, ast.BoolOp) and all(provably_bool(v) for v in k.values)
            or isinstance(k, ast.Call) and isinstance(k.func, ast.Name) and k.func.id in ("bool", "isinstance", "callable", "all", "any", "hasattr"))


def pure(v):
    """An arm with no effect and no way to raise: a literal, a name (a dotted name too), an f-string of those, a tuple of those."""
    return (isinstance(v, (ast.Constant, ast.Name)) or isinstance(v, ast.Attribute) and pure(v.value) or isinstance(v, (ast.Tuple, ast.List)) and all(pure(e) for e in v.elts)
            or isinstance(v, ast.JoinedStr) and all(isinstance(p, ast.Constant) or isinstance(p, ast.FormattedValue) and pure(p.value) and p.format_spec is None for p in v.values))


def arms(d):
    """({True: arm, False: arm}) of a two-row bool dict, else None."""
    ks = [k.value if isinstance(k, ast.Constant) and isinstance(k.value, bool) else None for k in d.keys]
    return dict(zip(ks, d.values)) if None not in ks and sorted(ks) == [False, True] else None


def lazy(v):
    return isinstance(v, ast.Lambda) and not (v.args.args or v.args.posonlyargs or v.args.vararg or v.args.kwonlyargs or v.args.kwarg)


def eligible(n):
    """-> (key, true arm, false arm) when node `n` is a rewritable site: a called zero-parameter-lambda table, or an effect-free table; else None."""
    call = isinstance(n, ast.Call) and not n.args and not n.keywords and isinstance(n.func, ast.Subscript)
    sub = n.func if call else n
    if not (isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Dict) and provably_bool(sub.slice)):
        return None
    a = arms(sub.value)
    if a is None:
        return None
    if call and lazy(a[True]) and lazy(a[False]):
        return sub.slice, a[True].body, a[False].body
    if not call and pure(a[True]) and pure(a[False]):
        return sub.slice, a[True], a[False]
    return None


class Rewrite(ast.NodeTransformer):
    """The declared rewrite, and nothing else: every eligible site becomes the IfExp with the same key and arms."""
    def generic_visit(self, node):
        node = super().generic_visit(node)
        got = eligible(node)
        return ast.IfExp(test=got[0], body=got[1], orelse=got[2]) if got else node


def transformed_digest(src):
    """ast_digest of the tree `Rewrite` makes from `src` (the base): what the head must equal."""
    t = Rewrite().visit(ast.parse(src))
    ast.fix_missing_locations(t)
    return ast_digest(ast.unparse(t))


def _offsets(src):
    starts, o = [], 0
    for ln in src.splitlines(keepends=True):
        starts.append(o)
        o += len(ln.encode())
    return starts


def rewrite_text(src):
    """-> (new source, [(line, why) left for a hand edit]). The text edit of the Rewrite: outermost sites first, repeated until none remain."""
    left = []
    for _ in range(12):
        t = ast.parse(src)
        data, starts, edits = src.encode(), _offsets(src), []
        parent = {c: p for p in ast.walk(t) for c in ast.iter_child_nodes(p)}
        for n in ast.walk(t):
            got = eligible(n)
            if not got or any(isinstance(p, ast.JoinedStr) for p in _up(parent, n)):
                continue
            a, b = starts[n.lineno - 1] + n.col_offset, starts[n.end_lineno - 1] + n.end_col_offset
            if any(a <= s and e <= b for s, e, _ in edits) or any(s <= a and b <= e for s, e, _ in edits):
                continue   # an enclosing or enclosed site is edited this pass; this one is next pass
            if b"#" in data[a:b]:
                left.append((n.lineno, "a comment inside the site"))
                continue
            seg = lambda x: data[starts[x.lineno - 1] + x.col_offset:starts[x.end_lineno - 1] + x.end_col_offset].decode()   # noqa: E731
            wrap = lambda x, s: f"({s})" if isinstance(x, (ast.IfExp, ast.Lambda, ast.NamedExpr, ast.Yield, ast.YieldFrom)) else s   # noqa: E731
            parts = (wrap(got[1], seg(got[1])), wrap(got[0], seg(got[0])), wrap(got[2], seg(got[2])))
            flat = f"{parts[0]} if {parts[1]} else {parts[2]}"
            text = flat if "\n" not in flat and len(flat) < 140 else f"{parts[0]}\n{' ' * (n.col_offset + 1)}if {parts[1]}\n{' ' * (n.col_offset + 1)}else {parts[2]}"
            p = parent.get(n)
            if "\n" in text or not (isinstance(p, (ast.Assign, ast.AnnAssign, ast.Return, ast.keyword, ast.Lambda, ast.Dict, ast.Tuple, ast.List)) or isinstance(p, ast.Call) and n in p.args):
                text = f"({text})"
            edits.append((a, b, text))
        if not edits:
            break
        for a, b, text in sorted(edits, reverse=True):
            data = data[:a] + text.encode() + data[b:]
        src = data.decode()
    return src, sorted(set(left))


def _up(parent, n):
    while n in parent:
        n = parent[n]
        yield n


def files(root=ROOT):
    out = [p for d in SCAN for p in sorted((root / d).rglob("*.py")) if "__pycache__" not in p.parts] + [root / "bin" / "cc"]
    return [p for p in out if p.is_file()]


def maths(root=ROOT):
    return set(tomllib.loads((root / "checks.toml").read_text())["roles"]["maths"])


def scope(parent, n):
    names = [p.name for p in _up(parent, n) if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return ".".join(reversed(names)) or "<module>"


def classify(n, parent, rel, is_maths):
    """-> (category, ruling, reason) of the bool-keyed dict literal `n` (one row of the sweep)."""
    d = n
    keys = d.keys
    arity = 1 if isinstance(keys[0], ast.Constant) else len(keys[0].elts)
    p = parent.get(d)
    if isinstance(p, (ast.Assign, ast.AnnAssign)) and isinstance(parent.get(p), ast.Module):
        return "K-named-table", "KEEP", "a named table over a discrete signature: the class is a lookup in a total table"
    if arity > 1:
        return ("K-inline-signature", "KEEP", "total over the product of its bools") if len(keys) == 2 ** arity else ("X-inline-partial-signature", "KEEP", "a missing combination is a crash on purpose (an upstream refusal makes it unreachable)")
    sub = p if isinstance(p, ast.Subscript) and p.value is d else None
    call = sub is not None and isinstance(parent.get(sub), ast.Call) and parent[sub].func is sub
    if sub is None:
        return "X-other", "KEEP", "the dict is bound to a name and indexed elsewhere: not a literal dispatch, outside the transformer's form"
    a = arms(d)
    if a is None:
        return "X-other", "KEEP", "not a two-row True/False table"
    lam = all(isinstance(v, ast.Lambda) for v in d.values)
    cat = ("R-lazy-if" if lam and call else "X-eager-arms" if not lam and not all(pure(v) for v in d.values) else "R-pure-ternary" if not lam else "X-other")
    node = parent[sub] if call else sub
    if is_maths:
        return cat, "KEEP", "a maths-role file: a style edit there is out of scope (C1 reports and tags its comparisons)"
    if cat == "X-eager-arms":
        return cat, "KEEP", "both arms run today; a rewrite stops evaluating one (plan 1644 O2 names the lazy and pure sites only); reported per site"
    if not provably_bool(sub.slice):
        return cat, "KEEP", "the key is not provably bool by its syntax: a ternary would accept a truthy non-bool where the table raises KeyError"
    if cat == "X-other" or eligible(node) is None:
        return cat, "KEEP", "outside the transformer's form (a lambda with parameters, or an arm that is not effect-free)"
    return cat, "REWRITE", "a two-way branch spelt as a table, provably bool key, lazy or effect-free arms"


def boolkey(k):
    """True for a bool literal, or a non-empty tuple of bool literals."""
    isb = lambda e: isinstance(e, ast.Constant) and isinstance(e.value, bool)   # noqa: E731
    return isb(k) or isinstance(k, ast.Tuple) and bool(k.elts) and all(isb(e) for e in k.elts)


def sweep(root=ROOT):
    """The rows of every bool or bool-tuple keyed dict literal under the scanned roots: id (file, scope, category, ruling, ordinal), plus the text for a reader."""
    rows, mm = [], maths(root)
    for f in files(root):
        rel, src = f.relative_to(root).as_posix(), f.read_text()
        t = ast.parse(src)
        parent = {c: p for p in ast.walk(t) for c in ast.iter_child_nodes(p)}
        seen = collections.Counter()
        for n in sorted((x for x in ast.walk(t) if isinstance(x, ast.Dict) and x.keys and None not in x.keys), key=lambda x: (x.lineno, x.col_offset)):
            if not all(boolkey(k) for k in n.keys):
                continue
            cat, ruling, why = classify(n, parent, rel, rel in mm)
            key = (rel, scope(parent, n), cat, ruling)
            seen[key] += 1
            rows.append({"file": rel, "scope": key[1], "category": cat, "ruling": ruling, "n": seen[key], "line": n.lineno, "reason": why, "text": ast.unparse(n)[:100]})
    return rows


def toml_text(rows):
    q = lambda s: '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'   # noqa: E731
    return "# release/dispatch-sweep.toml: every bool or bool-tuple keyed dict literal of cc/, bin/cc, manual/ (plan 1644 D5). `line` is where the row was at the base; identity is (file, scope, category, ruling, n).\n" + "".join(
        f"\n[[row]]\nfile = {q(r['file'])}\nscope = {q(r['scope'])}\ncategory = {q(r['category'])}\nruling = {q(r['ruling'])}\nn = {r['n']}\nline = {r['line']}\nreason = {q(r['reason'])}\ntext = {q(r['text'])}\n" for r in rows)


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        sys.stdout.write(toml_text(sweep(Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT)))
    else:
        for f in sys.argv[2:]:
            new, left = rewrite_text(Path(f).read_text())
            Path(f).write_text(new)
            print(f, "left for hand:", left)
