"""Test 1 (plan 1511 §3): the navigator package's import closure contains no environment.* module."""
import ast
import subprocess
import sys

from conftest import ROOT


def _local_closure():
    """static: every module reachable by import from navigator/*.py (local modules only)."""
    seen, todo, imports = set(), [p for p in (ROOT / "navigator").glob("*.py")], set()
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        for node in ast.walk(ast.parse(p.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "")] + [f"{node.module}.{a.name}" for a in node.names]
                if node.level:  # relative import inside navigator
                    names = [f"navigator.{node.module}" if node.module else "navigator"]
            imports.update(names)
            for n in names:
                f = ROOT / (n.replace(".", "/") + ".py")
                if n.split(".")[0] in ("navigator", "environment") and f.exists():
                    todo.append(f)
    return imports


def test_static_closure_has_no_environment_module():
    bad = sorted(n for n in _local_closure() if n.split(".")[0] == "environment")
    assert bad == []


def test_runtime_closure_has_no_environment_module():
    code = ("import sys, navigator.needle, navigator.reader;"
            "print(sorted(m for m in sys.modules if m.split('.')[0]=='environment'))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"
