"""test_standing - plan 1337: a declared comparison (size, matched, chain, start, steps) is a project.Comparison inside projection C, built only by
door.comparison_for; it has no provenance and no src/tgt, so admit.declare cannot take it and kernel.A/B cannot read it. The control relation
stays a kernel.Relations. T1 routing, T2 a report cannot become an edge (by type), T3 the arithmetic is bit-identical to kernel.A/B,
T4 door.STANDING and cc.toml [step_labels] are total and agree, T5 validate: provenance is optional on a comparison, required on control.
Seen RED on 1066c43 (door.comparison_for / project.Comparison / door.STANDING absent; validate requires provenance on every relation)."""
import dataclasses
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import numpy as np  # noqa: E402
import admit  # noqa: E402
import declare  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402
import kernel  # noqa: E402
import project  # noqa: E402
from host import NotEvaluableHere  # noqa: E402

COMPARISONS = ("size", "matched", "chain", "start")


def raises(fn, exc):
    try:
        fn()
    except exc as e:
        return str(e) or type(e).__name__
    return None


def t1():
    m = detect.load_input("x4-ising-field-ch")
    for name in ("needle", "across", "two_start"):
        ctx = door.context(m, detect.instrument(name)[0])
        got = {n: type(r).__name__ for n, r in ctx.rel.items()}
        check(f"T1 x4-ising-field-ch {name}: every ctx.rel entry ({sorted(got)}) is a project.Comparison, none a kernel.Relations",
              bool(got) and all(isinstance(r, project.Comparison) and not isinstance(r, kernel.Relations) for r in ctx.rel.values()), str(got))
    ctx = door.context(m, detect.instrument("across")[0])
    check("T1 across builds steps, a project.Comparison", isinstance(ctx.rel.get("steps"), project.Comparison), str(type(ctx.rel.get("steps"))))
    k4 = detect.load_input("k4-m1-ch")
    ctx = door.context(k4, detect.instrument("along")[0])
    check("T1 k4-m1-ch along: unit_rel (control) IS a kernel.Relations with provenance (COUPLING,)",
          isinstance(ctx.unit_rel, kernel.Relations) and ctx.unit_rel.provenance == (kernel.Provenance.COUPLING,), repr(ctx.unit_rel))
    check("T1 k4-m1-ch along: its size is a project.Comparison", isinstance(ctx.rel["size"], project.Comparison), str(type(ctx.rel["size"])))


def t2():
    m = detect.load_input("x4-ising-field-ch")
    c = door.comparison_for(m, "size")
    msg = raises(lambda: admit.declare(2, [(1, 0)], [c]), ValueError)
    check("T2 admit.declare refuses a Comparison as a provenance (ValueError naming provenance)", msg is not None and "provenance" in msg, str(msg))
    check("T2 kernel.A cannot read a Comparison (AttributeError)",
          raises(lambda: kernel.A(admit.nodefield([[1.0, 2.0, 3.0]]), c), AttributeError) is not None)
    names = {f.name for f in dataclasses.fields(project.Comparison)}
    check("T2 project.Comparison has no src, tgt or provenance field", not names & {"src", "tgt", "provenance"}, str(names))


def as_edge(m, n):
    """The reference: the old route, relations_for over the same declaration with a provenance supplied (a comparison declares none after Edit B)."""
    return door.relations_for({**m, "relations": {**m["relations"], n: {**m["relations"][n], "provenance": "Coupling"}}}, n)


def t3():
    m, rng = detect.load_input("k4-m1-ch"), np.random.default_rng(1337)
    for n in COMPARISONS:
        c, rel = door.comparison_for(m, n), as_edge(m, n)
        x = admit.nodefield(rng.standard_normal((5, c.n)))
        check(f"T3 {n}: compared(x, c) is bit-identical to kernel.A(x, rel).spatial ({c.n} nodes, {len(c.hi)} differences)",
              project.compared(x, c).tobytes() == kernel.A(x, rel).spatial.tobytes() and project.compared(x, c).shape == kernel.A(x, rel).spatial.shape)
    c, rel = door.comparison_for(m, "size"), as_edge(m, "size")
    x = admit.nodefield(rng.standard_normal((5, c.n)))
    g = kernel.A(x, rel).spatial
    ref = kernel.B(kernel.EdgeField(g, np.zeros((0, rel.n))), rel).spatial
    check("T3 size: continued(g, c) is bit-identical to kernel.B(EdgeField(g), rel).spatial",
          project.continued(g, c).tobytes() == ref.tobytes() and project.continued(g, c).shape == ref.shape)
    ctx = door.context(m, detect.instrument("across")[0])
    k = len(m["axes"]["size"]) - 1
    old = admit.declare(k, [(i + 1, i) for i in range(k - 1)], [kernel.Provenance.COUPLING] * (k - 1))
    s = ctx.rel["steps"]
    check("T3 steps: a project.Comparison whose (hi, lo) equal the old edge list's (src, tgt)",
          isinstance(s, project.Comparison) and s.n == old.n and np.array_equal(s.hi, old.src) and np.array_equal(s.lo, old.tgt), repr(s))


def t4():
    names = {r for p in sorted((ROOT / "instruments").glob("*.toml")) for r in tomllib.loads(p.read_text()).get("relations", [])}
    check("T4 every relation name of instruments/*.toml is a key of door.STANDING", names <= set(door.STANDING), str(names - set(door.STANDING)))
    check("T4 size, matched, chain, start build with comparison_for", all(door.STANDING[n].build is door.comparison_for for n in COMPARISONS))
    check("T4 control builds with relations_for", door.STANDING["control"].build is door.relations_for)
    labels = tomllib.loads((ROOT / "cc.toml").read_text())["step_labels"]
    labels = {n: v for n, v in labels.items() if isinstance(v, str)}
    check("T4 cc.toml [step_labels] names the same relations as door.STANDING", set(labels) == set(door.STANDING), f"{sorted(labels)} vs {sorted(door.STANDING)}")
    check("T4 [step_labels][n] == COMPARISON iff door.STANDING[n] builds with comparison_for",
          all((labels.get(n) == "COMPARISON") == (s.build is door.comparison_for) for n, s in door.STANDING.items()), str(labels))


def planted(tmp, input_id, section, key):
    """A scratch copy of the repo whose inputs/<input_id>/m.toml has `key` deleted under [relations.<section>] for each listed section."""
    repo = tmp / input_id
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust", "results"))
    p, cur, out = repo / "inputs" / input_id / "m.toml", None, []
    for ln in p.read_text().splitlines(keepends=True):
        cur = ln.strip()[1:-1] if ln.startswith("[") else cur
        out += [] if cur in {f"relations.{s}" for s in section} and ln.startswith(key) else [ln]
    p.write_text("".join(out))
    return repo


def content(found):
    return [f for f in found if isinstance(f, declare.F) and not isinstance(f, NotEvaluableHere)]


def t5():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = planted(tmp, "x4-ising-field-ch", ("size", "matched", "start"), "provenance")
        left = (repo / "inputs" / "x4-ising-field-ch" / "m.toml").read_text().count("provenance")
        found = [f for f in content(declare.validate(repo, "x4-ising-field-ch", "v10-rules")[0]) if "relations." in f.loc]
        check(f"T5 x4-ising-field-ch with its 3 comparison provenance lines deleted ({left} left): no finding at relations.*",
              left == 0 and not found, str(found))
        repo = planted(tmp, "k4-m1-ch", ("control",), "provenance")
        found = content(declare.validate(repo, "k4-m1-ch", "v10-rules")[0])
        check("T5 k4-m1-ch with [relations.control] provenance deleted: missing required field at relations.control.provenance",
              any(f.loc.endswith("relations.control.provenance") and f.msg == "missing required field" for f in found),
              str([f for f in found if "relations." in f.loc]))


for name, fn in (("T1", t1), ("T2", t2), ("T3", t3), ("T4", t4), ("T5", t5)):
    guarded(name, fn)
print("".join(f"FAILED {b}\n" for b in bad) + "test_standing: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
