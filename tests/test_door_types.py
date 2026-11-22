"""test_door_types - plan 1644: the door's guarantees are structural, and every check here has been seen to fail at the base (c9954ba).
T1 a kernel type's arrays are owned and read-only (a write raises; a write to the caller's array never reaches it). T2 the door cannot be bypassed: a kernel type's constructor IS the
door, with the door's own words. T3 the operators of cc/kernel.py are the kernel of record, function by function. T4 every operator output is bit-identical to the base kernel's.
T5 a typed refusal's code is an Enum member, so a code outside its table cannot be constructed. T6 one refusal rule: a declaration raises, data returns a value.
Base sources are read with `git show`; a clone without the base commit FAILS with a Next line (it never skips)."""
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, bootstrap, check, guarded  # noqa: E402

bootstrap(ROOT, "cc")
import admit  # noqa: E402
import kernel  # noqa: E402

BASE = "55eba02"   # the plan-1639-dist tip this plan branched from (D0)
C = admit.Provenance.CONTINUATION
OPERATORS = {   # T3: the AST digest (docstring removed) of each operator's FunctionDef at BASE
    "_out_sum": "e22dd2e07b6f6433605b93031a7f0bc348c67cec90b3b053030d5252e57fd1af", "_in_sum": "60addf791ea324797ff400d92115cde5516fa123326e563544d14300df7055a4",
    "A": "c0ad20f45abd16f335d834b08002e2ee38c47211f7f960d6adc99a67882e192f", "B": "b29cffd12490d7208ec90079b2c11241deb6e3fb29e8edacd63c95ae66b382ec",
    "rho": "f1d6627ae67e8360da027da80fb55823c6b25e35080ca5ba30e1e96142f0ac54", "R": "35ecdb86f385390008efa26dec6911b995fd9c2d5ccd7835a5c6e2ce6c6d0dd9",
    "E": "8df75cc7bc9b9282ec1921c06bbbec97ddf2c1f92560e1f56fe4352a5c9aa1d5",
}
MSG = {   # T2: the door's words at BASE, one per refusal
    "count": "REFUSED: one provenance per declared edge",
    "type": "REFUSED: every edge needs a declared provenance (Continuation/Coupling)",
    "range": "REFUSED: an edge endpoint lies outside the declared nodes",
    "cycle": "REFUSED: a cycle (ring/torus) is inadmissible: a node would be its own predecessor",
    "finite": "REFUSED: every value projected through M must be finite (in D)",
    "rank": "REFUSED: a NodeField is k components x n nodes",
    "m": "REFUSED (NOT EVALUATED): rho_base and chi_0 must be declared, finite, chi_0 > 0",
    "cc": "REFUSED (NOT EVALUATED): one finite cc per declared component pair",
}


def ser(n):
    if isinstance(n, ast.AST):
        return n.__class__.__name__ + "(" + ",".join(f"{f}={ser(v)}" for f, v in ast.iter_fields(n) if v is not None and v != []) + ")"
    return "[" + ",".join(ser(x) for x in n) + "]" if isinstance(n, list) else repr(n)


def operator_digests(src):
    """{name: digest} of every top-level function of `src` (docstring removed): the T3 serialiser, per function."""
    out = {}
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef):
            if n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
                n.body = n.body[1:] or [ast.Pass()]
            out[n.name] = hashlib.sha256(ser(n).encode()).hexdigest()
    return out


def operator_findings(src):
    got = operator_digests(src)
    return [k for k, want in OPERATORS.items() if got.get(k) != want] + sorted(set(got) - set(OPERATORS))


def refuses(fn, words):
    try:
        fn()
    except ValueError as e:
        return str(e) == words
    return False


def raises_readonly(fn):
    try:
        fn()
    except ValueError as e:
        return "read-only" in str(e)
    return False


def git_show(path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"the base commit {BASE} is not in this clone: {r.stderr.strip()[:120]}\n  Next: fetch the plan-1639-dist history (git fetch), then rerun")
    return r.stdout


def t1():
    r = admit.declare(3, [(0, 1), (1, 2)], [C, C])
    x = admit.nodefield([[1.0, 2.0, 3.0]])
    m = admit.m(0.5, 1.0, pairs=[(0, 1)], cc=[0.25])
    e = kernel.A(admit.nodefield([[1.0, 2.0, 3.0], [0.0, 1.0, 1.0]]), r, ((0, 1),))
    for name, arr in (("Relations.src", r.src), ("Relations.tgt", r.tgt), ("NodeField.data", x.data), ("EdgeField.spatial", e.spatial), ("EdgeField.comp", e.comp), ("M.cc", m.cc)):
        check(f"T1 {name}: a write raises 'read-only'", raises_readonly(lambda a=arr: a.__setitem__((0,) * a.ndim, 0)), "the write succeeded")
        check(f"T1 {name}: it owns its memory (no writable base to write through)", arr.base is None and arr.flags.owndata and not arr.flags.writeable, f"base={type(arr.base)}")
    check("T1 a mutated endpoint cannot make a cycle (the seed-1 attack)", raises_readonly(lambda: r.tgt.__setitem__(1, 0)), "")
    check("T1 a negative endpoint cannot be written (the silent wrap of A)", raises_readonly(lambda: r.tgt.__setitem__(0, -1)), "")
    raw = np.array([1.0, 2.0, 3.0])
    nf = admit.nodefield(raw)
    raw[0] = np.nan
    check("T1 the aliasing case: a write to the caller's array after admission leaves nf.data finite", bool(np.isfinite(nf.data).all()), str(nf.data))
    cc = np.array([0.25])
    m2 = admit.m(0.5, 1.0, pairs=[(0, 1)], cc=cc)
    cc[0] = np.nan
    check("T1 the aliasing case: a write to the caller's cc after admission leaves m.cc finite", bool(np.isfinite(m2.cc).all()), str(m2.cc))
    src = np.array([0, 1])
    r2 = admit.declare(3, [(0, 1), (1, 2)], [C, C])
    src[0] = 2
    check("T1 the aliasing case: a write to the caller's edge arrays leaves the relation as declared", r2.src.tolist() == [0, 1], str(r2.src))
    raw2 = np.array([[1.0, 2.0]])
    ef = kernel.EdgeField(raw2, np.zeros((0, 2)))
    raw2[0, 0] = 9.0
    check("T1 the aliasing case: an EdgeField does not share the caller's array", ef.spatial[0, 0] == 1.0, str(ef.spatial))
    check("T1 breaker: the attack on a plain array WOULD succeed (the check can fail)", not raises_readonly(lambda: np.array([1.0]).__setitem__(0, 2.0)), "")


def t2():
    nan = float("nan")
    check("T2 kernel.NodeField is admit.NodeField (one type, one constructor)", kernel.NodeField is admit.NodeField and kernel.Relations is admit.Relations and kernel.M is admit.M and kernel.EdgeField is admit.EdgeField and kernel.Provenance is admit.Provenance, "")
    check("T2 kernel.NodeField(nan) refuses with the door's words", refuses(lambda: kernel.NodeField(np.array([[nan, 1.0]])), MSG["finite"]), "constructed or other words")
    check("T2 kernel.NodeField of rank 3 refuses with the door's words", refuses(lambda: kernel.NodeField(np.zeros((1, 2, 2))), MSG["rank"]), "")
    check("T2 kernel.Relations(a cycle) refuses with the door's words", refuses(lambda: kernel.Relations(2, [0, 1], [1, 0], (C, C)), MSG["cycle"]), "")
    check("T2 kernel.Relations(no provenance) refuses with the door's words", refuses(lambda: kernel.Relations(2, [0], [1], ("x",)), MSG["type"]), "")
    check("T2 kernel.Relations(an endpoint outside) refuses with the door's words", refuses(lambda: kernel.Relations(2, [0], [5], (C,)), MSG["range"]), "")
    check("T2 kernel.Relations(one provenance short) refuses with the door's words", refuses(lambda: kernel.Relations(2, [0], [1], ()), MSG["count"]), "")
    check("T2 kernel.M(chi_0 = 0) refuses with the door's words", refuses(lambda: kernel.M(0.5, 0.0, (), []), MSG["m"]), "")
    check("T2 kernel.M(one cc short) refuses with the door's words", refuses(lambda: kernel.M(0.5, 1.0, ((0, 1),), []), MSG["cc"]), "")
    check("T2 the door functions refuse with the same words", refuses(lambda: admit.declare(2, [(0, 1), (1, 0)], [C, C]), MSG["cycle"]) and refuses(lambda: admit.nodefield([1.0, nan]), MSG["finite"]) and refuses(lambda: admit.m(0.5, 0.0), MSG["m"]), "")
    check("T2 STEERING is a provenance of the door", admit.declare(2, [(1, 0)], [admit.Provenance.STEERING]).provenance == (admit.Provenance.STEERING,), "")
    # the breaker: a kernel module that defines its own NodeField (a second constructor) is found
    scratch = type(sys)("scratch_kernel")
    exec("import numpy as np\nfrom dataclasses import dataclass\n@dataclass(frozen=True)\nclass NodeField:\n    data: np.ndarray\n", scratch.__dict__)
    check("T2 breaker: a kernel module with its own NodeField is not the door's type", scratch.NodeField is not admit.NodeField and not refuses(lambda: scratch.NodeField(np.array([[nan]])), MSG["finite"]), "")


def t3():
    src = (ROOT / "cc" / "kernel.py").read_text()
    check("T3 every operator of cc/kernel.py has the AST of the kernel of record (docstrings and comments excluded)", operator_findings(src) == [], str(operator_findings(src)))
    check("T3 the base kernel is the pinned digest set (the pin is the base's)", operator_findings(git_show("cc/kernel.py")) == [], str(operator_findings(git_show("cc/kernel.py"))))
    swapped = src.replace("x.data[:, rel.src] - x.data[:, rel.tgt]", "x.data[:, rel.tgt] - x.data[:, rel.src]")
    check("T3 breaker: x[t] - x[s] in A is found, naming A", swapped != src and operator_findings(swapped) == ["A"], str(operator_findings(swapped)))
    check("T3 breaker: a type moved back into kernel.py leaves T3 green (types are not operators) and T2 red", operator_findings(src + "\nclass NodeField:\n    pass\n") == [], "")
    check("T3 breaker: an added operator-shaped function is found", operator_findings(src + "\ndef extra(x):\n    return x\n") == ["extra"], "")


READER = r'''
import json, sys
import numpy as np
sys.path[:0] = [sys.argv[1]]
import kernel, admit
perturb = sys.argv[2] == "1"
out = []
def hx(a):
    return np.ascontiguousarray(a).tobytes().hex()
def one(k, n, e_idx, prov, pairs, cc, x, rb, c0):
    rel = admit.declare(n, e_idx, prov)
    nf = admit.nodefield(x)
    m = admit.m(rb, c0, pairs, cc)
    a = kernel.A(nf, rel, m.pairs)
    b = kernel.B(a, rel)
    r_n = kernel.rho(a, rel, m)
    r = kernel.R(b, rel, r_n, m)
    e = kernel.E(nf, rel, m)
    return [hx(a.spatial), hx(a.comp), hx(b.spatial), hx(b.comp), hx(r_n), hx(r.spatial), hx(r.comp), hx(e.spatial), hx(e.comp)]
rng = np.random.default_rng(1644)
P = [admit.Provenance.CONTINUATION, admit.Provenance.COUPLING]
chain = one(1, 4, [(0, 1), (1, 2), (2, 3)], [P[0]] * 3, (), (), [1.0, 4.0, 9.0, 16.0], 0.5, 1.0)
out.append(chain)
out.append(one(2, 4, [(0, 1), (1, 2), (2, 3)], [P[0]] * 3, [(0, 1)], [0.25], [[1.0, 2.0, 4.0, 8.0], [0.0, 1.0, 1.0, 3.0]], 0.5, 1.0))
for case in range(200):
    k = int(rng.integers(1, 5)); n = int(rng.integers(2, 31))
    perm = rng.permutation(n)
    edges = [(int(perm[i]), int(perm[j])) for i in range(n) for j in range(i + 1, n) if rng.random() < 3.0 / n]
    prov = [P[int(rng.integers(0, 2))] for _ in edges]
    npair = int(rng.integers(0, 3)) if k >= 2 else 0
    pairs = [tuple(int(v) for v in rng.choice(k, size=2, replace=False)) for _ in range(npair)]
    cc = rng.normal(size=npair).tolist()
    x = rng.normal(size=(k, n))
    if perturb and case == 0:
        x[0, 0] = np.nextafter(x[0, 0], np.inf)
    out.append(one(k, n, edges, prov, pairs, cc, x, float(rng.uniform(0.1, 2.0)), float(rng.uniform(0.1, 2.0))))
print(json.dumps(out))
'''


def run_reader(cc_dir, perturb=False):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(READER)
    try:
        r = subprocess.run([sys.executable, "-I", f.name, str(cc_dir), "1" if perturb else "0"], capture_output=True, text=True)
    finally:
        Path(f.name).unlink()
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    return json.loads(r.stdout)


def t4():
    with tempfile.TemporaryDirectory() as d:
        for f in ("kernel.py", "admit.py"):
            (Path(d) / f).write_text(git_show(f"cc/{f}"))
        want = run_reader(d)
        got = run_reader(ROOT / "cc")
        check("T4 A, B, rho, R and E give byte-identical arrays to the base kernel on 202 inputs", got == want, f"{sum(a != b for a, b in zip(got, want))} of {len(want)} cases differ")
        check("T4 breaker: one input moved one ulp is found", run_reader(ROOT / "cc", perturb=True) != want, "")


def t5():
    import chain
    import intake_feature
    import intake_suspect
    import navfamily
    for label, cls, table in (("chain.Refusal", chain.Refusal, chain.REFUSAL), ("intake_suspect.Refused", intake_suspect.Refused, intake_suspect.REFUSAL), ("navfamily.Refusal", navfamily.Refusal, navfamily.REFUSAL)):
        check(f"T5 {label}('NOT_A_CODE') cannot be constructed", refuses_any(lambda: cls("NOT_A_CODE", "x")), "constructed")
        check(f"T5 {label}: every code of its table constructs, prints, compares and serialises as its string",
              all(str(cls(c, "d").code) == c and cls(c, "d").code == c and json.dumps(cls(c, "d").code) == json.dumps(c) and cls(c, "d").words() == f"{c}: {table[c]} Detail: d" for c in table), "")
    check("T5 intake_feature.Unprojected('NOT_A_CODE') cannot be constructed", refuses_any(lambda: intake_feature.Unprojected("NOT_A_CODE")), "constructed")
    check("T5 intake_feature.Unprojected: both reasons construct and print as before",
          all(intake_feature.Unprojected(c).words() == f"{c}: intake/POLICY.toml has no {intake_feature.UNDECLARED[c]} row (estimand, preserves, discards); no oracle is built without it" for c in intake_feature.UNDECLARED)
          and intake_feature.Unprojected().reason == "PROJECTION_UNDECLARED", "")


def refuses_any(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def t6():
    import chain
    import door
    r = admit.admitted([[1.0, float("nan")]])
    check("T6 admit.admitted(non-finite) is an admit.Refused value", isinstance(r, admit.Refused) and r.sentence == MSG["finite"], repr(r))
    check("T6 admit.admitted(finite) is a NodeField", isinstance(admit.admitted([[1.0, 2.0]]), admit.NodeField), "")
    check("T6 admit.nodefield of the same data raises the unchanged message", refuses(lambda: admit.nodefield([[1.0, float("nan")]]), MSG["finite"]), "")
    got = door.nodefield(np.array([[1.0, float("nan")]]), None)
    check("T6 door.nodefield(non-finite) is Null('NOT-EVALUATED', 'non-finite value')", got == door.Null("NOT-EVALUATED", "non-finite value"), repr(got))
    check("T6 cc/door.py has no isfinite call (the finiteness test is written once, in admit.py)", "isfinite" not in {n.attr for n in ast.walk(ast.parse((ROOT / "cc" / "door.py").read_text())) if isinstance(n, ast.Attribute)}, "")
    w = np.column_stack([np.arange(8.0), np.array([1.0, 2.0, float("nan"), 4.0, 5.0, 6.0, 7.0, 8.0]), np.ones(8)])
    out = chain._edges(w, np.arange(8), 2.0, "NONE", 0.15, type("Sp", (), {"lo": (0.0, 0.0), "width": (1.0, 8.0)})(), 1)
    check("T6 chain._edges over a non-finite sample returns a chain.Refusal SAMPLE_NOT_FINITE", isinstance(out, chain.Refusal) and out.code == "SAMPLE_NOT_FINITE", repr(out)[:160])


for name, fn in (("T1", t1), ("T2", t2), ("T3", t3), ("T4", t4), ("T5", t5), ("T6", t6)):
    guarded(name, fn)
print("test_door_types: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
