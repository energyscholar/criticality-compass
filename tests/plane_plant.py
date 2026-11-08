"""plane_plant - plan 1176 phase C: the planted 2-D bank (cc/intake_synth.py --plane) as intake declarations in a scratch copy of the Compass,
walked by `bin/cc navigate family` and scored by `bin/cc navigate score` (shared by tests/test_synth_plane.py and the RECON run on the compute host).
Test infrastructure (checks.toml [roles] test_infrastructure). It reads no real data.
The DECLARER here is this file: it reads the plant's truth.json (outside the bank) for the guessed line, writes [suspect] = the guess's two END
vertices (the first and last curve of the slice) and the checkpoints = the guess on every interior curve to <tmp>/held-out/, outside
declarations/. The intake and the navigator never see truth.json: it is not under any root they read (C1 checks the access log).
    python3 tests/plane_plant.py RECON <out.md> [seed ...]   # every family x density (x slice) declaration, S0-S10 -> family -> score
"""
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake_synth  # noqa: E402
import linenav  # noqa: E402
from intake_plant import long_table, per_file  # noqa: E402
from lib import cc as run_cc  # noqa: E402

SIZES, LEVELS, N = [27, 81, 243], [2, 3, 4], 3000
# Delta(a->b)(L): yD1 = -0.5, yD2 = -0.05 (raw SLOW-); with r = 0.1 the transform reads (-0.05 + 0.05)/0.9 = 0 (ZERO!). Delta(b->c)(L): yD1 = 0, yD2 = +0.5 (RELEVANT, RAW).
GROWTH = {("a", "b"): (-0.5, -0.05), ("b", "c"): (0.0, 0.5)}
TOP = {"a": 0.004, "b": 0.004, "c": 0.08}     # needle velocity of the top matched pair; the previous pair's is 0.04, so r = 0.1 (a, b: CONVERGING) and r = 2 (c: PERSISTENT)


def planted(tmp, instruments):
    rng, files, mean = np.random.default_rng(11), [], {"a": {L: 0.5 for L in SIZES}}
    for (p, q), (y1, y2) in GROWTH.items():
        d = {27: 0.1, 81: 0.1 * 3 ** y1, 243: 0.1 * 3 ** (y1 + y2)}
        mean[q] = {L: mean[p][L] + d[L] for L in SIZES}
    for pt in "abc":
        for L, nb in zip(SIZES, LEVELS):
            lv = {27: [0.40, 0.46], 81: [0.30, 0.40, 0.50], 243: [0.2, 0.3, 0.4, 0.5 + TOP[pt]]}[L]
            np.savez(Path(tmp) / f"{pt}-{L}.npz", G=mean[pt][L] + 0.01 * rng.standard_normal(N), GL=np.array(lv) + 0.01 * rng.standard_normal((N, nb)))
            files.append({"point": pt, "size": L, "start": "random", "path": f"{pt}-{L}.npz", "arrays": {"G": {"key": "G"}, "GL": {"key": "GL"}}})
    rel = lambda t, **kw: {"template": t, "provenance": "Coupling", **kw}   # noqa: E731
    return {"instruments": instruments, "obtained": {p: "truth" for p in "abc"},
            "axes": {"point": ["a", "b", "c"], "size": SIZES, "starts": ["random"], "main_start": "random"},
            "observable": {"name": "g", "definition": "planted", "levels": LEVELS, "final_size": 9},
            "relations": {"size": rel("chain", axis="size"), "control": rel("chain", axis="point"), "chain": rel("matched-chain", axis="size", pairs=[[243, 81], [81, 27]])},
            "interval": {"method": "block", "b": 50, "resamples": 100, "level": 0.95, "seed": 3}, "eps": {"y": 0.25, "drift": 0.5},
            "data": {"format": "npz-v1", "files": files}}


RUN_P = lambda t: t.replace('identity = "NONE"', 'identity = "RUN"', 1).replace('[replicate.key]\nkind = "NONE"', '[replicate.key]\nkind = "COLUMN"\ncolumn = "p"', 1)  # noqa: E731
CASES = [(f, "dense") for f in intake_synth.FAMILIES] + [(f, "sparse") for f in intake_synth.FAMILIES if f != "misaligned"]   # misaligned: a dense variant of sharp
EXCLUDED = 'excluded = [ { file = "MANIFEST.json", why = "metadata (in basis), not a curve" } ]'   # the long table's universe partition
CONFIRMED = "plan 1176 phase C planted bank (test declarer, not a human)"


@dataclass(frozen=True)
class Refused:
    """A typed refusal word printed by `navigate family` (`REFUSED <code>:`): the RECON outcome when no walk happened."""
    code: str

    @property
    def name(self):
        return self.code


def outcome(word):
    """The typed outcome of a `navigate family` transcript word: linenav.Verdict[word], a Refused code, or Refused('NONE') (no line printed)."""
    return {True: lambda: linenav.Verdict[word], False: lambda: Refused(word)}[word in linenav.Verdict.__members__]()


def keep_rows(bank, m, k):
    """(edit) every curve file of a PER_FILE bank cut to its first k data rows."""
    for f in m["files"]:
        lines = (bank / f["name"]).read_text().splitlines(keepends=True)
        (bank / f["name"]).write_text("".join(lines[:1 + k]))
    return m


def keep_curves(bank, m, k):
    """(edit) a PER_FILE bank cut to its first k curves (the other files removed)."""
    [(bank / f["name"]).unlink() for f in m["files"][k:]]
    return {**m, "files": m["files"][:k]}


EDITS = {   # breaker edit -> (bank edit (bank dir, MANIFEST) -> MANIFEST, suspect (the guess) -> its two vertices); total over the breakers' edit words
    "none": (lambda b, m: m, lambda g: [g[0], g[-1]]),
    "one-curve": (lambda b, m: keep_curves(b, m, 1), lambda g: [g[0], [g[0][0], g[0][1] + 0.5]]),   # both vertices on the one curve
    "two-row-curve": (lambda b, m: keep_rows(b, m, 2), lambda g: [g[0], g[-1]]),
    "suspect-off-plane": (lambda b, m: m, lambda g: [[g[0][0], 9.9], g[-1]]),   # the first vertex's fast beyond every curve's span [1.5, 3.5]
}


def copy(tmp):
    """A scratch copy of the Compass whose ROOTS.toml names <tmp>/banks as <plane-test>; returns (its root, the banks dir)."""
    w, banks = Path(tmp) / "cc", Path(tmp) / "banks"
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
    with (w / "intake" / "ROOTS.toml").open("a") as f:
        f.write(f'\n"<plane-test>" = "{banks}"   # plane_plant: the planted plane banks\n')
    banks.mkdir()
    return w, banks


def cc(w, *args):
    return run_cc(w, *args)[::-1]   # lib.cc returns (returncode, output); this module reads (output, returncode)


def bank(banks, tmp, bid, seed, family, density):
    """Write one plane bank <banks>/<bid> (truth in <tmp>/truth/<bid>-TRUTH); returns (MANIFEST, truth)."""
    intake_synth.plane_write(banks / bid, Path(tmp) / "truth" / f"{bid}-TRUTH", bid, seed, family, density)
    found = [t for t in sorted(Path(tmp).rglob("truth.json")) if t.parent.name in (bid, f"{bid}-TRUTH")]   # wherever the writer put it (C1 judges where)
    return json.loads((banks / bid / "MANIFEST.json").read_text()), json.loads(found[0].read_text())


def guess(truth, p):
    """The guessed line on slice p, in slow order: [[h, T], ...]."""
    return [[g["h"], g["T"]] for g in truth["guess"] if g["p"] == p]


TEXT = {   # layout -> (MANIFEST, declaration id, bank id) -> the intake.toml text before [plane] / [suspect]
    "PER_FILE": lambda m, ident, bid: per_file(m, ident).replace("<long-test>/pf", f"<plane-test>/{bid}"),
    "LONG_TABLE": lambda m, ident, bid: RUN_P(long_table(flat(m), ident).replace("<long-test>/pf", f"<plane-test>/{bid}")).replace("excluded = []", EXCLUDED, 1),
}
flat = lambda m: {**m, "files": [{**f, "h": 0.0} for f in m["files"]]}   # noqa: E731  the long table's one file has no slow value (its slow is a column)
SLICE = {"PER_FILE": lambda p: "", "LONG_TABLE": lambda p: f'[plane.slice]\ncolumn = "p"\nvalue = {p!r}\n'}


def declare(w, tmp, ident, bid, m, truth, p, edit="none"):
    """declarations/<ident>/ on bank <bid> at slice p: intake.toml with [plane] and [suspect] (the guess's END vertices), transducer.toml,
    profiled; the checkpoints (the guess on every interior curve) to <tmp>/held-out/<ident>.toml. Returns the checkpoints path."""
    g = guess(truth, p)
    d = w / "declarations" / ident
    d.mkdir(parents=True)
    text = (TEXT[m["layout"]](m, ident, bid) + '\n[plane]\naxes = "slow-fast"\n' + SLICE[m["layout"]](p)
            + f'\n[suspect]\nvertices = {EDITS[edit][1](g)!r}\ncorridor = "continuous"\n')
    (d / "intake.toml").write_text(text)
    (d / "transducer.toml").write_text(intake_synth.declare(flat(m), ident, "pf")[2])
    [cc(w, "intake", "profile", ident, root) for root in re.findall(r'^root = "([^"]*)"', text, re.M)[:1]]
    cc(w, "intake", "seal", ident, "--author", "plan 1176 plane_plant", "--as", "ai-draft", "--confirmed-by", CONFIRMED)   # the plant's declarer confirms it
    held = Path(tmp) / "held-out" / f"{ident}.toml"
    held.parent.mkdir(exist_ok=True)
    held.write_text(f"points = {g[1:-1]!r}   # the guessed line on every interior curve (plane_plant)\n")
    return held


def walked(w, ident, held):
    """(PRIMARY verdict word, navigator verdict, terminals, checkpoints within w_c, checkpoints, family stdout, score stdout, the feature census
    {kind: curves}, the path kinds [kind per traced point]) of one declaration (plan 1176 C', O2: the census as navigate family prints it)."""
    run, _ = cc(w, "intake", "run", ident)
    fam, _ = cc(w, "navigate", "family", ident)
    sc, _ = cc(w, "navigate", "score", ident, str(held))
    prim = (re.findall(r"\b(PRIMARY_READY|PRIMARY_INCOMPLETE|PRIMARY_REFUSED_AT)\b", run) + ["NONE"])[0]
    verdict = outcome((re.findall(r"^verdict: (\w+)$", fam, re.M) + re.findall(r"^REFUSED (\w+):", fam, re.M) + ["NONE"])[0])
    terms = (re.findall(r"^terminals: (.*)$", fam, re.M) + [""])[0]
    within = [(int(a), int(b)) for a, b in re.findall(r"^score: (\d+) of (\d+) checkpoints within", sc, re.M)] + [(0, 0)]
    census = {k: int(v) for k, v in re.findall(r"(\w+) (\d+)", (re.findall(r"^census: (.*) \(curves per Feature kind\)$", fam, re.M) + [""])[0])}
    kinds = (re.findall(r"^path kinds: (.*) \(each traced point's curve\)$", fam, re.M) + ["(none)"])[0].replace("(none)", "").split()
    return prim, verdict, terms, within[0][0], within[0][1], fam, sc, census, kinds


def narrow(kinds):
    """Is the traced path's census all-narrow: at least one point, every point's curve Located (O5: the C4 condition)."""
    return len(kinds) > 0 and set(kinds) == {"Located"}


def census_cell(census):
    """The census as a compact RECON cell: Located/Broad/AtSpanEnd/Absent counts (L/B/E/A)."""
    return "/".join(str(census.get(k, 0)) for k in ("Located", "Broad", "AtSpanEnd", "Absent"))


def kinds_cell(kinds):
    """The path kinds as a RECON cell: count per kind in first-seen order, or '-' when nothing was traced."""
    return ", ".join(f"{k} {kinds.count(k)}" for k in dict.fromkeys(kinds)) or "-"


def plant_all(w, banks, tmp, seed, cases=CASES, edit="none", tag=""):
    """Every case at one seed (a breaker's edit applied to each bank and suspect): [(family, density, slice p, declaration id, checkpoints path)]."""
    out = []
    for family, density in cases:
        bid = f"{family}-{density}-s{seed}{tag}"
        m, truth = bank(banks, tmp, bid, seed, family, density)
        m = EDITS[edit][0](banks / bid, m)
        for i, p in enumerate(intake_synth.DENSITY[density][1]):
            ident = f"{bid}-p{i}"
            out.append((family, density, p, ident, declare(w, tmp, ident, bid, m, truth, p, edit)))
    return out


def table(rows):
    """The RECON markdown: one row per declaration, then family x density pooled. rows: (family, density, p, seed, PRIMARY, outcome, terminals,
    k, n, census, path kinds). Census columns (plan 1176 C', O2): curves per Feature kind L/B/E/A, and the traced path's kinds."""
    word = lambda v: getattr(v, "name", f"BARE:{v}")   # noqa: E731  a bare string is shown as one (C6 refuses it)
    lines = ["| family | density | slice p | seed | intake | verdict | terminals | checkpoints within w_c | census L/B/E/A | path kinds |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {f} | {d} | {p} | {s} | {pr} | {word(v)} | {t} | {k}/{n} ({(k / n if n else 0):.2f}) | {census_cell(c)} | {kinds_cell(ks)} |"
              for f, d, p, s, pr, v, t, k, n, c, ks in rows]
    summ = {}
    [summ.setdefault((f, d), []).append((word(v), k, n, c, ks)) for f, d, p, s, pr, v, t, k, n, c, ks in rows]
    lines += ["", "| family | density | runs | FOLLOWED | FOLLOWED, path all Located | verdicts | checkpoints within w_c (pooled) | curves L/B/E/A (pooled) |",
              "|---|---|---|---|---|---|---|---|"]
    lines += [f"| {f} | {d} | {len(r)} | {sum(v == 'FOLLOWED_IN_CORRIDOR' for v, *_ in r)} | {sum(v == 'FOLLOWED_IN_CORRIDOR' and narrow(ks) for v, _, _, _, ks in r)} | "
              + ", ".join(f"{x} {sum(v == x for v, *_ in r)}" for x in sorted({v for v, *_ in r}))
              + f" | {sum(k for _, k, *_ in r)}/{sum(n for _, _, n, *_ in r)} ({sum(k for _, k, *_ in r) / max(1, sum(n for _, _, n, *_ in r)):.2f})"
              + f" | {census_cell({x: sum(c.get(x, 0) for _, _, _, c, _ in r) for x in ('Located', 'Broad', 'AtSpanEnd', 'Absent')})} |" for (f, d), r in summ.items()]
    return "\n".join(lines) + "\n"


def recon(out_md, seeds):
    """RECON: every case at every seed, S0-S10 (intake run) -> navigate family -> navigate score; the table to out_md. Measurement, not a gate."""
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        w, banks = copy(tmp)
        for seed in seeds:
            for family, density, p, ident, held in plant_all(w, banks, tmp, seed):
                prim, verdict, terms, k, n, _, _, census, kinds = walked(w, ident, held)
                rows.append((family, density, p, seed, prim, verdict, terms, k, n, census, kinds))
                print(f"{family:10s} {density:6s} p={p} seed={seed} {prim} {verdict.name} [{terms}] {k}/{n} census {census_cell(census)} path [{kinds_cell(kinds)}]", flush=True)
    Path(out_md).write_text(table(rows))
    return rows


if __name__ == "__main__" and sys.argv[1:2] == ["RECON"]:
    recon(sys.argv[2], [int(s) for s in sys.argv[3:]] or [1176])
