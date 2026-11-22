"""test_dispatch_rewrite - plan 1644 D5, T7 / T7b / T7c. T7: every file of the sweep is, definition for definition, the declared rewrite of its BASE (the AST of `Rewrite(base)` equals head's),
except the definitions another phase of this plan edited on purpose (EDITED, each named with its phase). T7b: the transformer is behaviourally right (and a swapped-arms transformer is found).
T7c: at head no REWRITE site is left. Base sources are read with `git show`; a clone without the base commit FAILS with a Next line (it never skips)."""
import ast
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "release"))
from lib import bad, check, guarded  # noqa: E402

import dispatch_rewrite as D  # noqa: E402

BASE = "c9954ba"   # the plan-1639-dist tip this plan branched from (D0)
EDITED = {   # file -> top-level names another phase of plan 1644 edited on purpose (declared in that phase's commit); compared nowhere else
    "cc/chain.py": {"=REFUSAL", "_edges", "_edge_feature"},   # phase 4 (D4): the value door and SAMPLE_NOT_FINITE
    "cc/intake_blind.py": {"Typed"},   # phase 3 (D3): the code is an Enum member
    "cc/intake_feature.py": {"#0", "Unprojected", "=Unprojected.Reason"},   # phase 3 (D3)
}


def git_show(path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"the base commit {BASE} is not in this clone: {r.stderr.strip()[:120]}\n  Next: fetch the plan-1639-dist history (git fetch), then rerun")
    return r.stdout


def units(tree):
    """{name: digest} of each top-level statement (a def/class by its name, an assignment by its targets, anything else by position), docstrings removed."""
    out = {}
    for i, n in enumerate(tree.body):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            key = n.name
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets if isinstance(n, ast.Assign) else [n.target]
            key = "=" + ",".join(ast.unparse(t) for t in tg)
        else:
            key = f"#{i}"
        while key in out:
            key += "'"
        for x in ast.walk(n):
            if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and x.body and isinstance(x.body[0], ast.Expr) and isinstance(getattr(x.body[0], "value", None), ast.Constant) and isinstance(x.body[0].value.value, str):
                x.body = x.body[1:] or [ast.Pass()]
        out[key] = D.ser(n)
    return out


def differing(rel, head_src):
    """Top-level units of `rel` at head that are not the rewrite of base's, minus the declared EDITED ones."""
    t = ast.parse(git_show(rel)) if rel in D.maths(ROOT) else D.Rewrite().visit(ast.parse(git_show(rel)))   # a maths-role file is never rewritten (D5): it must equal its base
    want, got = units(ast.fix_missing_locations(t)), units(ast.parse(head_src))
    skip = EDITED.get(rel, set())
    return sorted(k for k in set(want) | set(got) if k not in skip and want.get(k) != got.get(k))


def t7():
    sweep_files = sorted({r["file"] for r in D.sweep(ROOT)} | {p.relative_to(ROOT).as_posix() for p in D.files(ROOT) if (b"True:" in p.read_bytes())})
    found = {}
    for rel in sweep_files:
        d = differing(rel, (ROOT / rel).read_text())
        if d:
            found[rel] = d
    check("T7 every file is, unit for unit, the declared rewrite of its base", found == {}, "; ".join(f"{k}: {v[:4]}" for k, v in list(found.items())[:6]) + f" ({len(found)} files)")
    # breaker 1: one arm of one rewritten ternary changed in a scratch copy
    src = "def f(x):\n    return 'a' if x > 1 else 'b'\n"
    base = "def f(x):\n    return {True: 'a', False: 'b'}[x > 1]\n"
    t = D.Rewrite().visit(ast.parse(base))
    check("T7 breaker: the rewrite of a site equals the hand ternary", units(ast.fix_missing_locations(t)) == units(ast.parse(src)), "")
    check("T7 breaker: a changed arm is found", units(ast.fix_missing_locations(t)) != units(ast.parse(src.replace("'b'", "'c'"))), "")
    # breaker 2: a site whose key is not provably bool is not a rewrite
    nb = "def f(x):\n    return {True: 'a', False: 'b'}[x]\n"
    check("T7 breaker: a rewrite of a non-provably-bool key is not what the transformer does", units(ast.fix_missing_locations(D.Rewrite().visit(ast.parse(nb)))) == units(ast.parse(nb)), "")


SHAPES = [   # (dict form, ternary-free names): each evaluates over k in {True, False}
    ("{True: lambda: a, False: lambda: b}[x > 1]()", "x > 1"),
    ("{True: lambda: f'n={a}', False: lambda: f'm={b}'}[not x]()", "not x"),
    ("{True: lambda: a + 1, False: lambda: b - 1}[a < b]()", "a < b"),
    ("{True: lambda: a, False: lambda: b}[isinstance(x, int)]()", "isinstance(x, int)"),
    ("{True: 'yes', False: 'no'}[x == 3]", "x == 3"),
    ("{True: a, False: b}[x > 1 and a < b]", "x > 1 and a < b"),
    ("{True: lambda: (a, b), False: lambda: None}[bool(x)]()", "bool(x)"),
    ("{True: lambda: [a], False: lambda: []}[callable(x)]()", "callable(x)"),
    ("{True: lambda: a if b else 0, False: lambda: 7}[x is None]()", "x is None"),
]


def run(code, env):
    try:
        return eval(code, dict(env))   # noqa: S307
    except Exception as e:  # noqa: BLE001
        return ("raised", type(e).__name__)


def agree(transform):
    bad_ = []
    for dform, key in SHAPES:
        t = ast.fix_missing_locations(transform().visit(ast.parse(dform, mode="eval")))
        code = compile(t, "<t>", "eval")
        for x in (0, 3, None, 5):
            for a, b in ((1, 2), (5, 0)):
                env = {"x": x, "a": a, "b": b}
                if run(dform, env) != run(code, env):
                    bad_.append((dform, x, a, b))
    return bad_


def t7b():
    check("T7b the transformer agrees with the dict form on 9 shapes x 8 inputs", agree(D.Rewrite) == [], str(agree(D.Rewrite)[:3]))
    check("T7b the arms are lazy: the unselected arm's effect does not run", lazy_ok(), "")

    class SwappedRewrite(D.Rewrite):
        def generic_visit(self, node):
            out = super().generic_visit(node)
            if isinstance(out, ast.IfExp) and out is not node:
                out.body, out.orelse = out.orelse, out.body
            return out
    check("T7b breaker: a transformer with the arms swapped is found", agree(SwappedRewrite) != [], "")


def lazy_ok():
    hits = []
    t = ast.fix_missing_locations(D.Rewrite().visit(ast.parse("{True: lambda: hits.append('t'), False: lambda: hits.append('f')}[x > 1]()", mode="eval")))
    eval(compile(t, "<t>", "eval"), {"hits": hits, "x": 3})   # noqa: S307
    return hits == ["t"]


def t7c():
    left = [r for r in D.sweep(ROOT) if r["ruling"] == "REWRITE"]
    check("T7c no REWRITE site is left at head", left == [], "; ".join(f"{r['file']}:{r['line']}" for r in left[:6]) + f" ({len(left)} left)")
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "cc").mkdir()
        (Path(d) / "cc" / "p.py").write_text("x = 3\ny = {True: 1, False: 2}[x > 1]\n")
        (Path(d) / "checks.toml").write_text("[roles]\nmaths = []\n")
        check("T7c breaker: a reverted site (the dict form) is found", [r["line"] for r in D.sweep(Path(d)) if r["ruling"] == "REWRITE"] == [2], "")


for name, fn in (("T7", t7), ("T7b", t7b), ("T7c", t7c)):
    guarded(name, fn)
print("test_dispatch_rewrite: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
