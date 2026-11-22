"""test_wheel - plan 0985 phase 3: what a built wheel carries. The workspace copy holds what the installed tool NEEDS at run time and nothing else:
the code, the declared data (tables, inputs, cases, expected, families, fixtures, instruments), the stored results and the frozen record (a run refuses
when a frozen result or frozen test file is absent, seen below), the CC0 data under data/ (cc.toml [data] local), docs/ (tabulate writes docs/verdict-table.html),
benchmark/ (bench verify), and README, CLAIMS, LICENSE, NOTICE. Of tests/ it carries ONLY the files FROZEN.json names (the structure gate's C7); the other
tests are the clone's. No file of the wheel names a home directory, a user's tree or one of the author's machines.
Plan 1639 T1/T2 (declared edit): the scan reads EVERY text file of the wheel and of the sdist (not .py/.md/.html only), names the process vocabulary of the review
agents as well as of the roles (Fable, planner, Sonnet, Opus, Claude, Anthropic), no longer hits numpy's own `Generator` or the `E412 trap`, prints the FULL hit lists,
and exempts only (a) the one public address of the author, by exact match, (b) the three transducer files named by sha256 in EXEMPT (never a pattern).
`scan_text`/`scan_members` are imported by tests/test_dist.py and release/release.sh; the run below happens only as a script.
Builds a wheel (python -m pip wheel --no-deps --no-build-isolation) into a scratch directory; needs setuptools."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = "criticality_compass/workspace/"
ALLOWED_EMAIL = "energyscholar+criticality-compass@gmail.com"
# plan 1639 D4: exempt by sha256, a list and never a pattern: the three result-pinned transducer files (inputs/x2b-xy{,-2,-3}-ch/transducer.toml) and expected/v04-v07-rules.toml (pinned by benchmark/MANIFEST.toml) that still carry a review word
EXEMPT = {"6de44f328cb460f116d2581c825690521912920765676eb7768d494bc9b67d89", "a44bda2fc7affab86bdc83886f755c53288a24df5a4b9e9ad5b0333fecfddcf6", "90ae9ebc2150b1eb6dce24cb2e88fa835b4176f5fdabf474fc41ff2a0fa66259", "129f2e2b6e48c495b019c51add5cea61978472132a5b42050b55a96b4e33ad91", "8674577ec6fd3cd14dbe1d9b95a9518dae07db9731aafad920bcab38f7cef6bc", "c1693be7228c0028ed31c38eaa6551e1b4e514fb36a787b6b76d2cd4bb6c7a32", "99fa66dc924afeeb2054903ad6874f31c84e11d1de696e57eedf645fb53be979"}
# built from parts so this file does not match itself
HOST = [re.compile(p) for p in ("/ho" + "me/", "/Us" + "ers/", "~/soft" + "ware", r"(?i)\bpen" + r"guin\b", r"(?i)\bji" + r"ll\b", r"(?i)\bporch" + r"light\b", "hal-" + "main", "has-anyone-" + "looked", "aura" + "sys", "structure-" + "checks",
        r"\bRo" + r"bin\b(?! Macomber)", r"\bBr" + r"uce\b(?! Stephenson)")]
# plan 1639: the process vocabulary of any file. `Generator` is a role only when it is not numpy's class (`random.Generator`, `Generator(PCG64)`); the old `\bE\d{3}\b` is the
# log form `LOG E123` now (an `E731` noqa or "the E412 trap" is no process word).
VOCAB = [re.compile(p) for p in (r"(?i)\bar" + r"gus\b", r"\bAudi" + r"tor\b", r"(?<!random\.)\bGene" + r"rator\b(?!\()", r"GPT" + r"-6", r"(?i)\brel" + r"ay \d", r"\bLOG " + r"E\d+",
        r"(?i)\bfa" + r"ble\b", r"(?i)\bplan" + r"ner\b", r"\bSon" + r"net\b", r"\bOp" + r"us\b", r"\bCla" + r"ude\b", r"(?i)\bAnthr" + r"opic\b")]
EMAIL = re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|org|net|edu|io|gov|info|de|uk|fr|ch|ac)\b")
SKIP_MEMBER = (".dist-info/WHEEL", ".dist-info/RECORD")   # the build tool's own lines ("Generator: setuptools") are not ours


def scan_text(text):
    """-> [(line, pattern)] of every host, vocabulary or stray-address hit of `text`."""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        out += [(i, p.pattern) for p in HOST + VOCAB if p.search(ln)]
        out += [(i, "address:" + m.group(0)) for m in EMAIL.finditer(ln) if m.group(0) != ALLOWED_EMAIL]
    return out


def members(path):
    """-> (name, bytes) of every file of a wheel (.whl) or an sdist (.tar.gz)."""
    if str(path).endswith(".whl"):
        z = zipfile.ZipFile(path)
        return [(n, z.read(n)) for n in z.namelist() if not n.endswith("/")]
    t = tarfile.open(path)
    return [(m.name, t.extractfile(m).read()) for m in t.getmembers() if m.isfile()]


def scan_members(path, exempt=EXEMPT):
    """-> {member: [(line, pattern)]} for every text member of the archive that is not a build-tool file and whose sha256 is not in `exempt`."""
    rows = {}
    for n, b in members(path):
        if b"\0" in b or n.endswith(SKIP_MEMBER) or hashlib.sha256(b).hexdigest() in exempt:
            continue
        if (h := scan_text(b.decode("utf-8", "replace"))):
            rows[n] = h
    return rows


if __name__ == "__main__":
    from lib import bad, check  # noqa: E402
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / "src"
        src.mkdir()
        names = [n for n in subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, check=True).stdout.decode().split("\0") if n]
        for n in names:   # the tracked files as they are in the working tree (a hook runs before the commit exists)
            if (ROOT / n).is_file():
                (src / n).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / n, src / n)
        r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", str(Path(t) / "dist"), str(src)], capture_output=True, text=True)
        wheels = sorted((Path(t) / "dist").glob("*.whl"))
        check("a wheel builds", r.returncode == 0 and len(wheels) == 1, r.stderr[-300:])
        if wheels:
            z = zipfile.ZipFile(wheels[0])
            names = [n[len(W):] for n in z.namelist() if n.startswith(W)]
            have = set(names)
            frozen = json.loads((ROOT / "FROZEN.json").read_text())["files"]
            frozen_tests = {k for k in frozen if k.startswith("tests/")}
            check("the frozen record and every frozen file of it are in the wheel", "FROZEN.json" in have and all(k in have for k in frozen), str([k for k in frozen if k not in have][:3]))
            check("tests/ holds exactly the files FROZEN.json names", {n for n in have if n.startswith("tests/")} == frozen_tests, str(sorted(n for n in have if n.startswith("tests/") and n not in frozen_tests)[:3]))
            check("the CC0 data under data/ is in the wheel (cc.toml [data] local)", "data/l8/ATTRIBUTION.md" in have, "data/ missing")
            check("README, CLAIMS, LICENSE and NOTICE are in the wheel", all(f in have for f in ("README.md", "CLAIMS.md", "LICENSE", "NOTICE")), str([f for f in ("README.md", "CLAIMS.md", "LICENSE", "NOTICE") if f not in have]))
            check("the run-time trees are in the wheel", all(any(n.startswith(d + "/") for n in have) for d in ("bin", "cc", "tables", "inputs", "cases", "expected", "families", "fixtures", "instruments", "results", "docs", "benchmark")))
            check("no platform binary (cc/_ext/*.so) is in the wheel", not [n for n in have if n.endswith(".so")])
            rows = scan_members(wheels[0], EXEMPT)
            host = {n: [h for h in v if not any(h[1] == p.pattern for p in VOCAB) and not h[1].startswith("address:")] for n, v in rows.items()}
            vocab = {n: [h for h in v if any(h[1] == p.pattern for p in VOCAB) or h[1].startswith("address:")] for n, v in rows.items()}
            host, vocab = {n: v for n, v in host.items() if v}, {n: v for n, v in vocab.items() if v}
            full = lambda d: "; ".join(f"{n}:{','.join(str(i) for i, _ in v)}" for n, v in sorted(d.items()))   # noqa: E731  (the FULL list: nothing is truncated)
            check("no file of the wheel names a home directory, one of the author's machines or trees, or a private person", not host, f"{len(host)} files: {full(host)}")
            check("no text file of the wheel (help, docs, CLAIMS, code, data notes) uses the process vocabulary", not vocab, f"{len(vocab)} files: {full(vocab)}")
    print("test_wheel: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
    sys.exit(1 if bad else 0)
