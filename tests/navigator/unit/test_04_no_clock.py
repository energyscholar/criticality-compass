"""Test 4, AST half (plan 1511 §3): no clock, no timeout, no side channel anywhere in the navigator package."""
import ast

from conftest import ROOT

BANNED_IMPORTS = {"time", "datetime", "select", "selectors", "signal", "sched", "asyncio", "threading", "multiprocessing",
                  "timeit"}
BANNED_ATTRS = {"settimeout", "setblocking", "setdefaulttimeout", "perf_counter", "monotonic", "time_ns", "sleep", "Timer",
                "alarm", "setitimer", "perf_counter_ns", "monotonic_ns", "process_time"}


def violations(src):
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in BANNED_IMPORTS]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BANNED_IMPORTS:
                out.append(f"from {node.module} import ...")
            out += [f"from {node.module} import {a.name}" for a in node.names if a.name in BANNED_ATTRS]
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            out.append(f".{node.attr}")
        elif isinstance(node, ast.Call):
            out += [f"timeout={ast.unparse(k.value)}" for k in node.keywords if k.arg == "timeout"]
            if isinstance(node.func, ast.Attribute) and node.func.attr == "wait" and node.args:
                out.append(".wait(<timeout>)")
        elif isinstance(node, ast.Name) and node.id in BANNED_ATTRS:
            out.append(node.id)
    return out


def test_checker_catches_every_banned_form():
    bad = {
        "import time": "import time", "from time import sleep": "from time import ...",
        "import datetime": "import datetime", "import select": "import select", "import selectors": "import selectors",
        "import signal": "import signal", "import asyncio": "import asyncio",
        "import threading\nthreading.Timer(1, f)": "import threading", "s.settimeout(3)": ".settimeout",
        "s.setblocking(False)": ".setblocking", "socket.create_connection(a, timeout=3)": "timeout=3",
        "q.get(timeout=1)": "timeout=1", "ev.wait(5)": ".wait(<timeout>)", "t.perf_counter()": ".perf_counter",
        "x.monotonic()": ".monotonic", "signal.alarm(1)": ".alarm", "signal.setitimer(0, 1)": ".setitimer",
    }
    for src, want in bad.items():
        assert want in violations(src), src


def test_checker_passes_clean_code():
    assert violations("import json\nimport socket\ns = socket.socket()\ns.connect(a)\nx = f.readline()") == []


# environment/run.py runs the needle IN-PROCESS, so a process-wide socket timeout there would reach the needle's socket (R4-A).
# The orchestrator legitimately owns time/signal (wait_ready, SIGTERM reaping), so only the socket-timeout surface is banned there.
RUN_BANNED_ATTRS = {"setdefaulttimeout", "settimeout", "setblocking"}
RUN_BANNED_IMPORTS = {"select", "selectors", "asyncio", "threading", "multiprocessing", "sched"}


def run_violations(src):
    out = [v for v in violations(src) if v.lstrip(".") in RUN_BANNED_ATTRS or v.startswith("timeout=")]
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            out += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in RUN_BANNED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in RUN_BANNED_IMPORTS:
            out.append(f"from {node.module} import ...")
    return out


def test_run_checker_catches_the_socket_timeout_forms_but_allows_the_orchestrators_clock():
    for src, want in {"socket.setdefaulttimeout(3)": ".setdefaulttimeout", "s.settimeout(1)": ".settimeout",
                      "socket.create_connection(a, timeout=3)": "timeout=3", "import select": "import select"}.items():
        assert want in run_violations(src), src
    assert run_violations("import time, signal\ntime.sleep(1)\nproc.wait(15)") == []


def test_orchestrator_run_py_cannot_give_the_in_process_needle_a_socket_timeout():
    assert run_violations((ROOT / "environment" / "run.py").read_text()) == []


def test_navigator_package_has_no_clock_or_timeout():
    found = {}
    for p in sorted((ROOT / "navigator").glob("*.py")):
        v = violations(p.read_text())
        if v:
            found[p.name] = v
    assert found == {}
