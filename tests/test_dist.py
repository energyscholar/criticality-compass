"""test_dist - plan 1639 T3-T10 and T12: the distribution is what the plan says it is, and every check here has been seen to fail.
T3 the docstring-only edits of the plan change no code (AST identity against a pin). T4 the wheel carries what a run needs (registry.toml, DATA-LICENSE) and three commands
run from it as in the clone. T5 no sealed record is in any distribution. T6 sizes. T7 every stored result is in exactly one place and the documented commands run (code wheel
alone; code + data wheels) as in the clone, while a command naming a data-wheel result refuses with a line. T8 a record made from the installed wheel names no host and no
process word (green only after plan 1639 phase 4). T9 the metadata. T10 the hand-off check can fail. T12 NOTICE, README and CITATION.cff name the kernel port.
Needs a Python with `build` and `twine` (CC_RELEASE_TOOLS=<python>; else this interpreter), network for pip (numpy, scipy), and the data root for the three commands of T4."""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402
import test_wheel  # noqa: E402  (the one scan: tests/test_wheel.py scan_text / scan_members)

ROOT = Path(__file__).resolve().parent.parent
W = "criticality_compass/workspace/"
CODE_WHEEL_MAX = 15 * 1024 * 1024   # T6: "15 MB" read as MiB (PyPI counts its own 100 MB the same way); compressed bytes of the code wheel; the data wheel is bounded below the 100 MB PyPI file limit
DATA_WHEEL_MAX = 60 * 1024 * 1024
TOOLS = os.environ.get("CC_RELEASE_TOOLS") or sys.executable
EMAIL = "energyscholar+criticality-compass@gmail.com"
# T3: the AST digest (docstrings removed) of every .py file this plan edits, at the contract base 16a21fb. A pin follows an edit only by the Auditor's re-pin.
AST_BASE = {
    "cc/registry.py": "96548206ffd82395b4bb009b2ef99729a177def4d7c84df44aa0df9873b19dad",
    "cc/oracle_reweight.py": "47cc58df26189c49f325fb0cdcefb1be77a4e74cb3447995a0048c5936973fb2",
    "cc/chain.py": "72b4786cb673826f65ac16868aa0e017b3db95d77787d212831e540ab876b7cd",
    "cc/scorewords.py": "d35bd35eba05ac15a8985b8a64c47367faf956749f007bdc6f786d32cab134d5",
    "cc/linenav.py": "fa623461a5e35af5bbdba9644ccad9c895b030cc9042933d58e00bb2dfa67a95",
    "cc/sampler.py": "cb1771994db96829f9d976d22ab77fa86e4e64920ba4de30ba3afc8bed0abb99",
    "cc/kernel.py": "80a8d5a4943d9f30aa21d9ff853c178ad004c43dafbb26aadb1337d98bb7fdf6",
    "cc/admit.py": "657a9e5e1a00583dd3f039168c25d0c1f24ac77421f1976771236f6e46bbe7a8",
    "cc/instruments/along.py": "f9abf4b568614307ca4752e172c0bbdc8ef5a5b663e4dfdf29447d879440bc67",
    "cc/instruments/across_delta.py": "cbbe05d363ee619962967f683cccc415f6dd82e065e76d11e88f182ea9634f8f",
    "cc/instruments/stability_delta.py": "e7811256b0f894e00f979fa1506701ed4865ff5f36bc84f35317b2a626e8a43e",
}


def ser(n):
    """A version-independent serialisation of an AST: node names and fields, no positions, None and [] left out."""
    if isinstance(n, ast.AST):
        return n.__class__.__name__ + "(" + ",".join(f"{f}={ser(v)}" for f, v in ast.iter_fields(n) if v is not None and v != []) + ")"
    return "[" + ",".join(ser(x) for x in n) + "]" if isinstance(n, list) else repr(n)


def ast_digest(src):
    t = ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    return hashlib.sha256(ser(t).encode()).hexdigest()


def sh(cmd, cwd=None, env=None, timeout=1200):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def notice_findings(notice, readme, cff, kernel_py_exists):
    """T12 as a pure function of the texts, so it can be run on the real files and on planted ones. -> the list of what is missing."""
    miss = [w for w in ("cc/kernel.py", "operators.rs", "5c7941e0", "Metatron Dynamics, Inc.", "Apache", "translated to Python", "vectorised", "kernel_rs (rust/)") if w not in notice]
    miss += [] if kernel_py_exists else ["cc/kernel.py is not in the distribution"]
    ack = re.search(r"(?ms)^#+ +Acknowledgements.*?(?=^#+ |\Z)", readme)
    miss += [w for w in ("Robin Macomber", "Metatron Dynamics", "Relational Relativity Corp") if not ack or w not in ack.group(0)]
    miss += [] if re.search(r"(?m)^references:\s*$", cff) and "5c7941e0ce644dba844d3732fc25f9063db40f33" in cff and "abr-kernel" in cff and re.search(r"(?m)^cff-version: 1\.2\.0", cff) else ["CITATION.cff: references/abr-kernel commit"]
    return miss


def t3():
    for f, want in AST_BASE.items():
        check(f"T3 {f}: the code is identical to the base (docstrings and comments excluded)", ast_digest((ROOT / f).read_text()) == want, "the AST differs from the pin")
    a = "def f(x):\n    '''doc'''\n    return x + 1\n"
    check("T3 breaker: a docstring or comment edit leaves the digest", ast_digest(a) == ast_digest(a.replace("doc", "other") + "# c\n"))
    check("T3 breaker: a planted code change moves the digest", ast_digest(a) != ast_digest(a.replace("x + 1", "x + 2")) and ast_digest(a) != ast_digest(a.replace("return x + 1", "return min(x + 1, 3)")))


def build(T):
    """Stage the working tree (tracked and untracked, not ignored), build the code wheel, the sdist, the wheel from the sdist, and the data wheel. -> dict of paths."""
    src = T / "src"
    names = [n for n in subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, check=True).stdout.decode().split("\0") if n]
    for n in names:
        if (ROOT / n).is_file():
            (src / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / n, src / n)
    out = {"src": src}
    rc, o = sh([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", T / "d1", src], T)
    out["wheel"] = next(iter(sorted((T / "d1").glob("*.whl"))), None)
    check("T6 the code wheel builds", rc == 0 and out["wheel"] is not None, o[-300:])
    rc, o = sh([TOOLS, "-m", "build", "--sdist", "--no-isolation", "-o", T / "d2", src], T)
    out["sdist"] = next(iter(sorted((T / "d2").glob("*.tar.gz"))), None)
    check("T6 the sdist builds", rc == 0 and out["sdist"] is not None, o[-300:])
    if out["sdist"]:
        x = T / "fromsdist"
        tarfile.open(out["sdist"]).extractall(x)
        rc, o = sh([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", T / "d4", next(x.iterdir())], T)
        out["wheel2"] = next(iter(sorted((T / "d4").glob("*.whl"))), None)
        check("T6 a wheel builds from the sdist", rc == 0 and out["wheel2"] is not None, o[-300:])
    rc, o = sh([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", T / "d3", src / "release" / "data"], T)
    out["data"] = next(iter(sorted((T / "d3").glob("*.whl"))), None)
    check("T6 the data wheel builds", rc == 0 and out["data"] is not None, o[-300:])
    return out


def paths(archive, prefix=""):
    return {n for n, _ in test_wheel.members(archive) if n.startswith(prefix)}


def result_names(archive):
    return {n.rsplit("/", 1)[1] for n in paths(archive, W + "results/")}


def sealed_names():
    stems = {Path(r["path"]).stem for r in tomllib.loads((ROOT / "tests" / "sealed-records.toml").read_text())["record"]}
    return {p.name for p in (ROOT / "results").iterdir() if p.stem in stems}


def readonly_commands():
    """READONLY of tests/test_docs_match.py, read with ast.literal_eval (one table, never copied): the argument lists of README/HOWTO/TUTORIAL."""
    tree = ast.parse((ROOT / "tests" / "test_docs_match.py").read_text())
    tab = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "READONLY")
    return [(d, c, c.split()[1:]) for (d, c, _), v in tab.items() if d != "man" and v is None]


def norm(s, *roots):
    for r in roots:
        s = s.replace(str(r), "<R>")
    return re.sub(r"[ \t]+\n", "\n", s)


def t4_to_t8(T, a):
    venv = T / "venv"
    sh([sys.executable, "-m", "venv", venv], T)
    py, compass = venv / "bin" / "python", venv / "bin" / "compass"
    rc, o = sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", a["wheel"]], T)
    check("T4 the code wheel installs into a fresh venv", rc == 0, o[-300:])
    if rc:
        return
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "COMPASS_RUNS")}
    cwd = T / "empty"
    cwd.mkdir()
    clone = lambda args: sh([sys.executable, ROOT / "bin" / "cc", *args], ROOT, env)   # noqa: E731
    inst = lambda args: sh([compass, *args], cwd, env)   # noqa: E731
    for args in (["validate"], ["family", "b7-at-line-2"], ["explain", "w2-potts", "5"]):
        (rc1, o1), (rc2, o2) = clone(args), inst(args)
        check(f"T4 `compass {' '.join(args)}` from the installed wheel exits 0 with the clone's output", rc1 == 0 and rc2 == 0 and "Traceback" not in o2 and norm(o1, ROOT) == norm(o2, venv), f"clone rc={rc1} wheel rc={rc2}: {o2[-300:]}")
    cmds = readonly_commands()
    code_only_bad = []
    for d, c, args in cmds:
        (rc1, o1), (rc2, o2) = clone(args), inst(args)
        if not (rc1 == rc2 and "Traceback" not in o2 and norm(o1, ROOT) == norm(o2, venv)):
            code_only_bad.append(c)
    check("T7 the code wheel alone runs every documented READONLY command of README, HOWTO and TUTORIAL with the clone's exit code and output", not code_only_bad, str(code_only_bad))
    data_res = sorted(n for n in result_names(a["data"]) if n.endswith(".json"))
    probes = [(n.split("@")[0], n[:-5].split("@")[1]) for n in data_res[:3]]
    check("T7 the data wheel carries results to probe", len(probes) == 3, str(len(data_res)))
    for inp, tset in probes:
        rc, o = inst(["show", inp, "--tables", tset])
        check(f"T7 without the data wheel `show {inp} --tables {tset}` exits 1 with a `no result for` line and no traceback", rc == 1 and f"no result for {inp} under {tset}" in o and "Traceback" not in o, f"rc={rc} {o[-300:]}")
    rc, o = sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", "--no-deps", a["data"]], T)
    check("T7 the data wheel installs beside the code wheel", rc == 0, o[-300:])
    for inp, tset in probes:
        (rc1, o1), (rc2, o2) = clone(["show", inp, "--tables", tset]), inst(["show", inp, "--tables", tset])
        check(f"T7 with both wheels `show {inp} --tables {tset}` equals the clone", rc1 == rc2 == 0 and norm(o1, ROOT) == norm(o2, venv), f"{rc1} {rc2} {o2[-200:]}")
    bad_both = [c for d, c, args in cmds if (lambda x, y: not (x[0] == y[0] and norm(x[1], ROOT) == norm(y[1], venv)))(clone(args), inst(args))]
    check("T7 with both wheels the README/HOWTO/TUTORIAL command matrix equals the clone's", not bad_both, str(bad_both))
    # T8: a record made from the installed wheel (code wheel only was enough: the hold path reads no stored result)
    for system, world in (("ising", "ising-apparatus-static.toml"), ("at", "at-apparatus-static.toml")):
        wf = T / f"{system}-h1.toml"
        wf.write_text(re.sub(r"(?m)^horizon\s*=.*$", "horizon = 1", (ROOT / "system-instantiated" / "plugins" / system / world).read_text()))
        out = T / f"rec-{system}"
        rc, o = inst(["hold", system, wf, "--needle", "settled", "--wall", "300", "--out", out])
        recs = [p for p in out.iterdir() if p.is_dir()] if out.is_dir() else []
        check(f"T8 a horizon-1 {system} record is made from the installed wheel", rc == 0 and len(recs) == 1, f"rc={rc} {o[-300:]}")
        if recs:
            hit = {str(p.relative_to(recs[0])): test_wheel.scan_text(p.read_text("utf-8", "replace")) for p in sorted(recs[0].rglob("*")) if p.is_file() and b"\0" not in p.read_bytes()}
            hit = {k: v for k, v in hit.items() if v}
            check(f"T8 the {system} record names no host, no address and no process word, in any file", not hit, "; ".join(f"{k}:{','.join(sorted({p for _, p in v}))}" for k, v in hit.items()))


def t9(a):
    meta = lambda z, suffix: next(x for x in z.namelist() if x.endswith(suffix))   # noqa: E731
    z = zipfile.ZipFile(a["wheel"])
    m = z.read(meta(z, ".dist-info/METADATA")).decode()
    reqs = re.findall(r"(?m)^Requires-Dist: (.*)$", m)
    ok = lambda name: any(re.match(name + r">=[\d.]+,<[\d.]+", r) or re.match(name + r"<[\d.]+,>=[\d.]+", r) for r in reqs)   # noqa: E731
    want = {
        "License-Expression: Apache-2.0": "License-Expression: Apache-2.0" in m, "License-File LICENSE, NOTICE, DATA-LICENSE": all(f"License-File: {f}" in m for f in ("LICENSE", "NOTICE", "DATA-LICENSE")),
        "Requires-Python >=3.11": "Requires-Python: >=3.11" in m, "numpy and scipy have lower and upper bounds": ok("numpy") and ok("scipy"),
        "classifiers": all(c in m for c in ("Classifier: Programming Language :: Python :: 3 :: Only", "Classifier: Operating System :: OS Independent")),
        "no criticality-compass-kernel, no Provides-Extra: kernel": "criticality-compass-kernel" not in m and "Provides-Extra: kernel" not in m,
        "Author-email is the one public address": f"Author-email: Bruce Stephenson <{EMAIL}>" in m, "no Project-URL, no Home-page": "Project-URL" not in m and "Home-page" not in m, "version 0.1.0": "\nVersion: 0.1.0\n" in m}
    for k, v in want.items():
        check(f"T9 METADATA: {k}", v, "see METADATA of the built wheel")
    check("T9 the only address in the whole wheel text is the allowed one, found by exact match", EMAIL in m and not [r for n, r in test_wheel.scan_members(a["wheel"]).items() if any(p.startswith("address:") for _, p in r)])
    check("T9 breaker: another address is found, the allowed one is not", test_wheel.scan_text("mail me at someone@example.com") != [] and test_wheel.scan_text(EMAIL) == [])
    d = zipfile.ZipFile(a["data"])
    dm = d.read(meta(d, ".dist-info/METADATA")).decode()
    check("T9 the data wheel: licence CC-BY-4.0, DATA-LICENSE, the same version, DATA-LICENSE byte-equal to the root's", "License-Expression: CC-BY-4.0" in dm and "License-File: DATA-LICENSE" in dm and "\nVersion: 0.1.0\n" in dm
          and (ROOT / "release" / "data" / "DATA-LICENSE").read_bytes() == (ROOT / "DATA-LICENSE").read_bytes() and tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == "0.1.0")
    rc, o = sh([TOOLS, "-m", "twine", "check", a["wheel"], a["sdist"], a["data"]], ROOT)
    check("T9 twine check passes the wheel, the sdist and the data wheel", rc == 0 and "PASSED" in o and "FAILED" not in o, o[-300:])


def t10():
    hc = ROOT / "release" / "handoff_check.py"
    rc, o = sh([sys.executable, hc], ROOT)
    tab = tomllib.loads((ROOT / "release" / "blockers.toml").read_text()) if (ROOT / "release" / "blockers.toml").is_file() else {"row": []}
    tab.setdefault("row", [])
    open_rows = [r["id"] for r in tab["row"] if r.get("state") == "open"]
    check("T10 the hand-off check exits 1 on this tree and names every open row", rc == 1 and bool(open_rows) and all(i in o for i in open_rows), f"rc={rc} {o[-300:]}")
    exp = re.search(r"(?s)EXPECTED\s*=\s*(\[.*?\])", hc.read_text())
    ids = ast.literal_eval(exp.group(1)) if exp else []
    check("T10 the check holds a closed list of expected rows", len(ids) > 20, str(len(ids)))
    with tempfile.TemporaryDirectory() as t:
        full = "".join(f'[[row]]\nid = "{i}"\nstate = "owner-gated"\nruling = "ruled"\ncheck = ""\n' for i in ids)
        (Path(t) / "ok.toml").write_text(full)
        rc, o = sh([sys.executable, hc, "--blockers", Path(t) / "ok.toml"], ROOT)
        check("T10 it exits 0 when every row is owner-gated with a recorded ruling", rc == 0, o[-300:])
        (Path(t) / "gone.toml").write_text(full.replace(f'[[row]]\nid = "{ids[0]}"\nstate = "owner-gated"\nruling = "ruled"\ncheck = ""\n', ""))
        rc, o = sh([sys.executable, hc, "--blockers", Path(t) / "gone.toml"], ROOT)
        check("T10 with one row deleted it exits 1 naming the missing row", rc == 1 and ids[0] in o, o[-300:])
        (Path(t) / "open.toml").write_text(full.replace('state = "owner-gated"', 'state = "open"', 1))
        rc, o = sh([sys.executable, hc, "--blockers", Path(t) / "open.toml"], ROOT)
        check("T10 with one row open it exits 1", rc == 1, o[-200:])
        (Path(t) / "noruling.toml").write_text(full.replace('ruling = "ruled"', 'ruling = ""', 1))
        rc, o = sh([sys.executable, hc, "--blockers", Path(t) / "noruling.toml"], ROOT)
        check("T10 an owner-gated row without a ruling exits 1", rc == 1, o[-200:])


def t12(a):
    notice, readme, cff = (ROOT / "NOTICE").read_text(), (ROOT / "README.md").read_text(), (ROOT / "CITATION.cff").read_text() if (ROOT / "CITATION.cff").is_file() else ""
    check("T12 NOTICE, README and CITATION.cff name the kernel port", not notice_findings(notice, readme, cff, True), str(notice_findings(notice, readme, cff, True)))
    check("T12 breaker: NOTICE without the cc/kernel.py line FAILS", bool(notice_findings(notice.replace("cc/kernel.py", "the kernel"), readme, cff, True)))
    check("T12 breaker: a distribution without cc/kernel.py FAILS", bool(notice_findings(notice, readme, cff, False)))
    check("T12 breaker: a README without the Acknowledgements heading FAILS", bool(notice_findings(notice, readme.replace("Acknowledgements", "Thanks"), cff, True)))
    for label, arc in (("wheel", a["wheel"]), ("sdist", a["sdist"])):
        names = {n: b for n, b in test_wheel.members(arc)}
        pick = lambda f: next((b.decode() for n, b in names.items() if n.endswith("/" + f) or n == f), "")   # noqa: E731
        kern = any(n.endswith("cc/kernel.py") for n in names)
        got = notice_findings(pick("NOTICE"), pick("README.md"), pick("CITATION.cff"), kern)
        check(f"T12 the {label} carries NOTICE, README and CITATION.cff that name the kernel port, and cc/kernel.py", not got, str(got))
    leak = [n for n, v in test_wheel.scan_members(a["wheel"]).items() for _, p in v if re.search(r"Metatron|Macomber|Relational Relativity", p)]
    check("T12 the scan lists none of Metatron, Robin Macomber, Relational Relativity (their credit is allowed text)", not leak and not test_wheel.scan_text("Robin Macomber, Metatron Dynamics, Relational Relativity Corp.") and bool(test_wheel.scan_text("Robin Smith")))


def main():
    t3()
    guarded("T10", t10)
    T = Path(tempfile.mkdtemp(prefix="t-dist-"))
    try:
        a = build(T)
        if not all(a.get(k) for k in ("wheel", "sdist", "data", "wheel2")):
            return
        rows = {"wheel": a["wheel"], "sdist": a["sdist"], "data": a["data"]}
        sizes = {k: v.stat().st_size for k, v in rows.items()}
        print("sizes:", sizes)
        check("T6 the code wheel is at most 15 MiB compressed", sizes["wheel"] <= CODE_WHEEL_MAX, f"{sizes['wheel']} bytes")
        check("T6 the data wheel is below 60 MiB (PyPI's limit is 100 MB)", sizes["data"] <= DATA_WHEEL_MAX, f"{sizes['data']} bytes")
        sealed = sealed_names()
        stems = {Path(r["path"]).name for r in tomllib.loads((ROOT / "tests" / "sealed-records.toml").read_text())["record"]}
        for k, v in rows.items():
            inside = [n for n in paths(v) if n.rsplit("/", 1)[-1] in sealed and "results/" in n]
            check(f"T5 no sealed record is in the {k}", not inside and bool(stems), f"{len(inside)} of {len(stems)}: {inside[:3]}")
        code, data = result_names(a["wheel"]), result_names(a["data"])
        tracked = {p.name for p in (T / "src" / "results").iterdir() if p.is_file()}
        check("T7 every result is in exactly one place: code and data are disjoint", not code & data, str(sorted(code & data)[:3]))
        check("T7 code + data = every tracked result minus the sealed ones", code | data == tracked - sealed, f"missing {sorted(tracked - sealed - code - data)[:3]}; extra {sorted((code | data) - tracked)[:3]}")
        frozen = {Path(k).name for k in json.loads((ROOT / "FROZEN.json").read_text())["files"] if k.startswith("results/")}
        check("T7 the code wheel carries every FROZEN result", frozen <= code, str(sorted(frozen - code)[:3]))
        check("T7 the sdist holds what the code wheel holds: the wheel built from it has the same files", paths(a["wheel2"], W) == paths(a["wheel"], W), f"{sorted(paths(a['wheel2'], W) ^ paths(a['wheel'], W))[:4]}")
        w = paths(a["wheel"], W)
        for f in ("registry.toml", "DATA-LICENSE"):
            check(f"T4 {f} is in the workspace of the wheel", W + f in w, "absent")
        check("T4 DATA-LICENSE is also under dist-info/licenses/", any(n.endswith(".dist-info/licenses/DATA-LICENSE") for n in paths(a["wheel"])), "absent")
        guarded("T9", lambda: t9(a))
        guarded("T12", lambda: t12(a))
        rows = {k: test_wheel.scan_members(v) for k, v in {"wheel": a["wheel"], "sdist": a["sdist"], "data wheel": a["data"]}.items()}
        for k, r in rows.items():
            check(f"T8 the scan of every file of the {k} is clean", not r, "; ".join(f"{n}:{','.join(str(i) for i, _ in v)}" for n, v in sorted(r.items())))
        guarded("T4-T8", lambda: t4_to_t8(T, a))
    finally:
        shutil.rmtree(T, ignore_errors=True)


guarded("T3-T12", main)
print("test_dist: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
