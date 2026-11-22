"""test_public - plan 1640: the repository, not the wheel, can go public: the history scan, the rewrite, the tree scan, the public-face files, the CI file
and its run set, and the turn-public check. SLOW (cc.toml [check].slow): CI never runs it.
Several checks need things that are not in the tree, each named by an environment variable; without it the check prints `NOT RUN: <reason>` (never a silent pass):
CC_PRIVATE_PATTERNS (the private name list, never committed), CC_PUBLIC_MIRROR (a bare mirror of the private origin), CC_PUBLIC_REHEARSAL (a rehearsal
directory holding origin.git and out.git, written by release/public-rewrite.sh), CC_CI_LOCAL_RESULT (the result file of release/ci-local.sh).
Words the scans must find are spelled from parts, so this file never matches its own scan. Every check has a planted fault it must see (the breakers named in each block)."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMAIL = "energyscholar+criticality-compass@gmail.com"
UPSTREAM_COC_SHA = "977d781349351fd7c1f076e4c7dc7de2a05b40e12c773542c3815dd4ce7f37ba"   # plan 1640 M6: the Contributor Covenant 2.1 Markdown, contributor-covenant.org
PENDING = ("AGENTS.md", "docs/READING-THE-CODE.md", "docs/try-to-break-it.md")   # plan 1639's files: links to them are strict once any of them exists
PLANTED_WORD = "Arg" + "us"
OWNER = "energyscholar"   # the identities below are spelt from parts: this file is a tracked file the tree scan reads
GMAIL, NOREPLY = OWNER + "@gmail.com", OWNER + "@users.noreply.github.com"
TAIL = "CJDk5ZDNhYjEtNzE4ZC00YjQ5LWI2ZmQtNDc4MTFkODRlNjEyAAIqWzMsIjhkZjJlMzY0LTJhNWItNGQ1Ny1iZDgxLWM3ZDkzNGRkYzJkNCJdAAAGIJ2pT4"   # the tail a real upload token has; an all-A tail is not read as one by gitleaks
NOBODY = "t" + "@users.noreply.github.com"
OWNER_ROWS = ["OQ1", "OQ2", "OQ3", "OQ4", "gh-noreply-form", "create-repo", "flip", "project-urls-0.1.0", "readme-clone-url"]
LEAKS = ["release/public", "release/ci-", "release/turn-public-check.sh", ".github/", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", ".gitleaks.toml"]
from lib import bad, check as _check  # noqa: E402

# CC_PUBLIC_ONLY=T7,T8 runs and prints only the checks of those blocks, and never reaches T11: release/turn-public-check.sh runs T7-T9 this way for its rows,
# and T11 runs that script, so the one selector is what keeps the two from calling each other for ever.
ONLY = [s for s in os.environ.get("CC_PUBLIC_ONLY", "").split(",") if s]


def check(name, ok, why=""):
    if ONLY and not any(name.startswith(o + " ") for o in ONLY):
        return
    _check(name, ok, why)


def sh(*a, cwd=ROOT, env=None):
    r = subprocess.run(list(map(str, a)), cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    return r.returncode, r.stdout + r.stderr


def git(repo, *a):
    return sh("git", "-C", repo, *a)[1].strip()


def need(name, var):
    v = os.environ.get(var)
    if not v:
        print(f"NOT RUN: {name}: {var} is not set")
    return v


def hits(out, cls):
    return [ln for ln in out.splitlines() if ln.startswith(cls + "\t")]


PAT = os.environ.get("CC_PRIVATE_PATTERNS")
SCAN = ["python3", ROOT / "release" / "public_scan.py"]


def scan(*a):
    return sh(*SCAN, "--private-patterns", PAT, *a)


def planted_repo(t, files, exempt=None):
    """A scratch git repo holding `files` ({path: text}); `exempt` is the text of release/public-tree-exempt.toml."""
    d = Path(t) / "tree"
    d.mkdir()
    for p, s in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_text(s)
    if exempt is not None:
        (d / "release").mkdir(exist_ok=True)
        (d / "release" / "public-tree-exempt.toml").write_text(exempt)
    sh("git", "init", "-q", d)
    sh("git", "-C", d, "add", "-A")
    return d


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ---- the patterns file exists and holds what the planted faults need
if not PAT or not Path(PAT).is_file():
    print("NOT RUN: T1, T2, T6 scans: CC_PRIVATE_PATTERNS is not set or not a file (the scan refuses to run without it)")
else:
    text = Path(PAT).read_text()
    check("the patterns file has a [hard] and a [soft] section", "[hard]" in text and "[soft]" in text)
    rc, out = sh(*SCAN, "--tree", ROOT)   # no --private-patterns
    check("the scan REFUSES without --private-patterns (exit 2)", rc == 2, f"exit {rc}: {out[:120]}")

    # ---- T6 the tree scan, planted faults first (breakers), then the real tree
    with tempfile.TemporaryDirectory() as t:
        tok = "xx" + "ex.ts" + ".net"
        e_text = "keep " + PLANTED_WORD + "\n"
        bad_text = "gone " + PLANTED_WORD + "\n"
        d = planted_repo(t, {"a.txt": bad_text, "b.txt": f"mail {EMAIL}\n", "c.txt": "mail someone" + "@example.org\n", "d.txt": "p = '/ho" + "me/x'\n",
                             "e.txt": e_text, "f.txt": e_text + "changed\n", "g.txt": "host " + tok + "\n", "ok.txt": "nothing here\n"},
                         exempt=f'[[exempt]]\npath = "e.txt"\nsha256 = "{sha(e_text)}"\nreason = "planted"\n[[exempt]]\npath = "f.txt"\nsha256 = "{sha(e_text)}"\nreason = "planted, stale"\n')
        rc, out = scan("--tree", d)
        where = {ln.split("\t")[2].split(":")[0] for ln in out.splitlines() if ln.count("\t") >= 3}
        check("T6 breaker: the tree scan finds a planted word, an other email, a home path, a private host, a stale exemption (exit 1)",
              rc == 1 and where == {"a.txt", "c.txt", "d.txt", "f.txt", "g.txt"}, f"exit {rc} files {sorted(where)}")
    rc, out = scan("--tree", ROOT)
    check("T6 the tree has no hit of the vocabulary, hosts, home paths or private names (exit 0)", rc == 0, f"exit {rc}: " + "\n".join(out.splitlines()[:12]))

# ---- T1 the history scan sees the hard items
mirror = need("T1", "CC_PUBLIC_MIRROR")
if mirror and PAT:
    era = ",".join(git(mirror, "for-each-ref", "--format=%(objectname)").split())   # the private era: every tip of the mirror
    rc, out = scan("--history", mirror, "--private-era", era)
    check("T1 the mirror has 62 identities in the .local domain (HARD identity lines), exit 1", rc == 1 and len([l for l in hits(out, "HARD") if l.split("\t")[1] == "identity"]) == 62, f"exit {rc}")
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "p.git"
        w = Path(t) / "w"
        sh("git", "clone", "-q", "--bare", mirror, p)
        sh("git", "clone", "-q", "-b", "compass-main", p, w)
        (w / "data" / "ta").mkdir(parents=True)
        (w / "tok.txt").write_text("t = " + "pypi-" + "AgEIcHlwaS5vcmc" + TAIL + "\n")
        (w / "data" / "ta" / ("rij" + "ke.csv")).write_text("thermo" + "acoustic,x\n1,2\n")
        (w / "note.txt").write_text("host " + "ex.ts" + ".net\n")
        sh("git", "-C", w, "add", "-A")
        sh("git", "-C", w, "-c", "user.name=t", "-c", f"user.email={NOBODY}", "commit", "-qm", "plant")
        sh("git", "-C", w, "push", "-q", "origin", "HEAD:compass-main")
        rc, out = scan("--history", p, "--private-era", era)
        got = {ln.split("\t")[1] for ln in hits(out, "HARD")}
        check("T1 breaker: a planted token, a research-use-only path and header, and a private host are each a HARD class", {"secret", "ruo-path", "ruo-content", "private-hard"} <= got, str(sorted(got)))
        gl = shutil.which("gitleaks") or str(Path.home() / "1640-out/bin/gitleaks")
        if Path(gl).exists():
            rc, out = sh(gl, "git", "--no-banner", "--exit-code", "7", "--config", ROOT / ".gitleaks.toml", "--log-opts=--all", p)
            check("T1 breaker: gitleaks also finds the planted token", rc == 7, f"exit {rc}")
        else:
            print("NOT RUN: T1 gitleaks half: no gitleaks")

# ---- T2-T5 on the rehearsal
reh = need("T2-T5", "CC_PUBLIC_REHEARSAL")
if reh and mirror and PAT:
    origin, out_ = Path(reh) / "origin.git", Path(reh) / "out.git"
    V = ROOT / "release" / "public-verify.sh"
    era = git(origin, "rev-parse", "compass-main")
    allowed = {f"{OWNER} <{GMAIL}>", f"{OWNER} <{NOREPLY}>", "Gener" + f"ator <{GMAIL}>"}

    def idents(repo, br):
        return set(git(repo, "log", br, "--format=%an <%ae>%n%cn <%ce>").splitlines())
    check("T2 breaker: the unrewritten origin does NOT have only the allowed identities", idents(origin, "compass-main") - allowed != set())
    check("T2 the rewritten copy has exactly the allowed identities", idents(out_, "main") <= allowed and len(idents(out_, "main")) >= 2, str(sorted(idents(out_, "main") - allowed)))
    rc, o = scan("--history", out_, "--private-era", git(out_, "rev-parse", "main"))   # the era tip of the COPY (the origin's tip moved)
    check("T2 our history scan of the copy has 0 HARD and 0 late SOFT hits (exit 0)", rc == 0, o[-300:])
    rc, o = sh("bash", V, "--only", "V1", out_, origin, env={"CC_PRIVATE_PATTERNS": PAT})
    check("T2 gitleaks over every ref of the copy, with .gitleaks.toml: 0", rc == 0, o[-300:])
    rc, o = sh("bash", V, "--only", "V4", out_, origin)
    check("T3 nothing but the identity moved: trees, dates, topology, messages, count (V4)", rc == 0, o[-300:])
    with tempfile.TemporaryDirectory() as t:   # breakers of V1, V5 and V8 on scratch copies of the rehearsal
        q, w = Path(t) / "q.git", Path(t) / "w"
        sh("git", "clone", "-q", "--bare", out_, q)
        sh("git", "clone", "-q", "-b", "main", q, w)
        (w / "tok.txt").write_text("t = " + "pypi-" + "AgEIcHlwaS5vcmc" + TAIL + "\n")
        sh("git", "-C", w, "add", "-A")
        sh("git", "-C", w, "-c", "user.name=t", "-c", f"user.email={NOBODY}", "commit", "-qm", "plant")
        sh("git", "-C", w, "push", "-q", "origin", "HEAD:main")
        rc, o = sh("bash", V, "--only", "V1", q, origin, env={"CC_PRIVATE_PATTERNS": PAT})
        check("T2 breaker: a planted token in the copy fails V1 (gitleaks)", rc != 0, f"exit {rc}")
        o2 = Path(t) / "o2.git"
        shutil.copytree(origin, o2)
        sh("git", "-C", o2, "update-ref", "refs/heads/zz-planted", era)
        rc, o = sh("bash", V, "--only", "V5", out_, o2)
        check("T4 breaker: an origin that gained a ref fails V5", rc != 0, f"exit {rc}")
        c = Path(t) / "c.git"
        shutil.copytree(out_, c)
        (c / "objects" / "ab").mkdir(exist_ok=True)
        (c / "objects" / "ab" / ("c" * 38)).write_bytes(b"not a git object")
        rc, o = sh("bash", V, "--only", "V8", c, origin)
        check("V8 breaker: a corrupt object fails git fsck", rc != 0, f"exit {rc}")
    with tempfile.TemporaryDirectory() as t:   # breaker: a planted --replace-text on a scratch copy
        pl = Path(t) / "planted.git"
        sh("git", "clone", "-q", "--bare", "--no-local", "--single-branch", "-b", "compass-main", origin, pl)
        (Path(t) / "r.txt").write_text("BLANK==>BLANKED\n")
        rc, o = sh("git", "filter-repo", "--replace-text", Path(t) / "r.txt", cwd=pl)
        rc, o = sh("bash", V, "--only", "V4", pl, origin)
        check("T3 breaker: a planted --replace-text fails V4 and names a commit", rc != 0 and re.search(r"V4 FAIL [0-9a-f]{40}", o) is not None, f"exit {rc}: {o[-200:]}")
    for bad_out in (Path(reh) / "out.git", origin / "inside", origin):
        rc, o = sh("bash", ROOT / "release" / "public-rewrite.sh", "--origin", origin, "--out", bad_out)
        check(f"T4 breaker: public-rewrite.sh refuses the out dir {bad_out.name} (exit 2)", rc == 2, f"exit {rc}")
    rc, o = sh("bash", V, "--only", "V5", out_, origin)
    check("T4 the origin's refs and pack files are the same before and after (V5)", rc == 0, o[-300:])
    rc, o = sh("bash", V, "--only", "V6", out_, origin)
    check("T5 every self-sha in the copy's tree is preserved or listed, and no test passes a moved sha to git (V6)", rc == 0, o[-300:])
    with tempfile.TemporaryDirectory() as t:   # breaker: a test line that passes a MOVED sha to git
        mv = [ln.split()[0] for ln in (out_ / "filter-repo" / "commit-map").read_text().splitlines()[1:] if ln.split()[0] != ln.split()[1]]
        check("T5 the commit map has moved commits (the rewrite moved something)", bool(mv), "identity map")
        moved = (mv or ["0" * 40])[0][:7]
        pl, w = Path(t) / "q.git", Path(t) / "w"
        sh("git", "clone", "-q", "--bare", out_, pl)
        shutil.copytree(out_ / "filter-repo", pl / "filter-repo")
        sh("git", "clone", "-q", "-b", "main", pl, w)
        (w / "tests" / "zz_planted.py").write_text('import subprocess\nsubprocess.run(["git", "diff", "' + moved + '"])\n')
        sh("git", "-C", w, "add", "-A")
        sh("git", "-C", w, "-c", "user.name=t", "-c", f"user.email={NOBODY}", "commit", "-qm", "plant")
        sh("git", "-C", w, "push", "-q", "origin", "HEAD:main")
        rc, o = sh("bash", V, "--only", "V6", pl, origin)
        check("T5 breaker: a test that passes a moved sha to git fails V6 and names the file", rc != 0 and "zz_planted.py" in o, f"exit {rc}: {o[-200:]}")
        (w / "tests" / "zz_planted.py").write_text('BASE = "' + moved + '"   # a base held as a constant: no git call on this line\n')
        sh("git", "-C", w, "add", "-A")
        sh("git", "-C", w, "-c", "user.name=t", "-c", f"user.email={NOBODY}", "commit", "-qm", "plant2")
        sh("git", "-C", w, "push", "-q", "origin", "HEAD:main")
        rc, o = sh("bash", V, "--only", "V6", pl, origin)
        check("T5 breaker: a test that HOLDS a moved sha as a string constant (no git call on the line) fails V6 and names the file", rc != 0 and "zz_planted.py" in o, f"exit {rc}: {o[-200:]}")
        (w / "tests" / "zz_planted.py").write_text('"""the base was ' + moved + '"""\n# and ' + moved + '\n')
        sh("git", "-C", w, "add", "-A")
        sh("git", "-C", w, "-c", "user.name=t", "-c", f"user.email={NOBODY}", "commit", "-qm", "plant3")
        sh("git", "-C", w, "push", "-q", "origin", "HEAD:main")
        rc, o = sh("bash", V, "--only", "V6", pl, origin)
        check("T5 a moved sha in a docstring or a comment of a test is prose: V6 passes", rc == 0, f"exit {rc}: {o[-200:]}")
    rc, o = sh("bash", V, "--only", "V8", out_, origin)
    check("V8 git fsck --full is clean", rc == 0, o[-200:])

# ---- T7 the public-face files
files = set(sh("git", "ls-files", "--cached", "--others", "--exclude-standard")[1].splitlines())
coc = ROOT / "CODE_OF_CONDUCT.md"
if coc.is_file():
    c = coc.read_text()
    check("T7 CODE_OF_CONDUCT.md is the Contributor Covenant 2.1 with one substitution, the contact method", c.count(EMAIL) == 1 and sha(c.replace(EMAIL, "[INSERT CONTACT METHOD]")) == UPSTREAM_COC_SHA, "text differs from upstream")
else:
    check("T7 CODE_OF_CONDUCT.md exists", False, "missing")
sec = ROOT / "SECURITY.md"
s = sec.read_text() if sec.is_file() else ""
check("T7 SECURITY.md names the project email, private vulnerability reporting and the kernel_rs.so known item", EMAIL in s and re.search(r"private vulnerability reporting", s, re.I) is not None and "kernel_rs.so" in s and "known items" in s.lower(), "missing")
cl = (ROOT / "CLAIMS.md").read_text().lower()
check("T7 AQ7: CLAIMS.md says the `toolset:` cells name files of the author's private research repository by sha256 and are not public", "private research repository" in cl and "not public" in cl and "toolset:" in cl.split("## claims")[0], "sentence missing above the table")
planned = {"CONTRIBUTING.md", "SECURITY.md", ".github/pull_request_template.md", ".github/ISSUE_TEMPLATE/bug_report.md", ".github/ISSUE_TEMPLATE/reading_question.md", ".github/ISSUE_TEMPLATE/feature_request.md"}
check("T7 every planned public-face file exists", all((ROOT / f).is_file() for f in planned | {"CODE_OF_CONDUCT.md", ".github/ISSUE_TEMPLATE/config.yml"}), str(sorted(f for f in planned if not (ROOT / f).is_file())))
pending = not any((ROOT / p).is_file() for p in PENDING)
print(("PENDING: links to " + ", ".join(PENDING) + " are not checked (none of them exists at this base; they arrive with plan 1639)") if pending else "links to the plan 1639 files are checked")


def dead_links(path, text):
    out = []
    for m in re.finditer(r"\]\(([^)\s#]+)(?:#[^)]*)?\)", text):
        tgt = m.group(1)
        if re.match(r"[a-z]+:", tgt):
            continue
        rel = os.path.normpath(os.path.join(os.path.dirname(path), tgt))
        if rel not in files and not (pending and rel in PENDING):
            out.append(f"{path}: {tgt}")
    return out


check("T7 breaker: a link to a file that does not exist is found", dead_links("README.md", "see [x](no/such/file.md)") == ["README.md: no/such/file.md"])
dead = []
for f in sorted(planned):
    if (ROOT / f).is_file():
        dead += dead_links(f, (ROOT / f).read_text())
rd = (ROOT / "README.md").read_text().splitlines()
dead += dead_links("README.md", "\n".join(rd[:40]))
check("T7 every relative link of CONTRIBUTING, SECURITY, the first 40 lines of README and the templates resolves to a file", not dead, str(dead[:6]))
for f in sorted(planned - {"CONTRIBUTING.md", "SECURITY.md"}):
    if (ROOT / f).is_file():
        fm = (ROOT / f).read_text().split("---")
        head = fm[1] if len(fm) > 2 and fm[0].strip() == "" else ""
        if f.endswith("pull_request_template.md"):
            check(f"T7 {f} has the checklist items", all(k in (ROOT / f).read_text() for k in ("bin/cc check --fast", "declared")), "missing")
        else:
            check(f"T7 {f} has name: and about: front matter", re.search(r"^name:", head, re.M) is not None and re.search(r"^about:", head, re.M) is not None, "no front matter")
cfg = ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
check("T7 config.yml turns blank issues off and names no external URL", cfg.is_file() and "blank_issues_enabled: false" in cfg.read_text() and "http" not in cfg.read_text(), "config.yml")

# ---- T8 the README first screen
first = "\n".join(rd[:30])
bullets = [ln for ln in rd[:30] if re.match(r"\s*[-*] ", ln)]
check("T8 the first 30 lines hold 3 to 5 payoff bullets, each linking READING-THE-CODE or try-to-break-it", 3 <= len(bullets) <= 5 and all(("docs/READING-THE-CODE.md" in b or "docs/try-to-break-it.md" in b) for b in bullets), f"{len(bullets)} bullets")
check("T8 an install line, and a licence and citation line, in the first 30 lines", "pip install" in first and "Apache-2.0" in first and "CITATION.cff" in first, "missing")
check("T8 no Glossary heading before line 31", not any(re.match(r"#+\s*Glossary", ln) for ln in rd[:30]), "glossary on the first screen")
check("T8 no hype word in the first 40 lines", not re.search(r"\b(novel|revolutionary|unique|groundbreaking)\b", "\n".join(rd[:40]), re.I), "hype word")
para = [ln for ln in rd[1:] if ln.strip()][0] if len(rd) > 1 else ""
check("T8 one sentence says what CC is (the first paragraph line is one sentence)", para.count(". ") == 0 and para.rstrip().endswith("."), para[:80])

# ---- T9 the workflow
wf = ROOT / ".github" / "workflows" / "ci.yml"
al = shutil.which("actionlint") or str(Path.home() / "1640-out/bin/actionlint")


def wf_problems(t):
    p = []
    if not re.search(r"^on:\s*\n\s+push:\s*\n\s+branches:\s*\[main\]\s*\n\s+pull_request:", t, re.M):
        p.append("triggers are not push (main) and pull_request")
    if re.search(r"pull_request_target", t):
        p.append("pull_request_target")
    if not re.search(r"os:\s*\[ubuntu-latest, macos-latest\]", t):
        p.append("os matrix is not exactly ubuntu-latest, macos-latest")
    if not re.search(r"python-version:\s*\[\"3\.11\", \"3\.12\"\]", t):
        p.append("python-version is not exactly 3.11, 3.12")
    if "fetch-depth: 0" not in t:
        p.append("fetch-depth is not 0")
    if not re.search(r"^permissions:\s*\n\s+contents: read\s*$", t, re.M):
        p.append("permissions is not contents: read")
    p += [f"unpinned {u}" for u in re.findall(r"uses:\s*(\S+)", t) if not re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u)]
    if len(re.findall(r"uses:[^\n]*#\s*v\d", t)) != len(re.findall(r"uses:", t)):
        p.append("a uses: line has no version comment")
    runs = re.findall(r"^\s+run:\s*(.+)$", t, re.M)
    if [r for r in runs if "release/ci-run.sh" not in r and "pip install" not in r]:
        p.append("a run step other than the install and release/ci-run.sh")
    if "release/ci-run.sh" not in t:
        p.append("the test step is not release/ci-run.sh")
    return p


if wf.is_file():
    wt = wf.read_text()
    check("T9 breaker: a planted fetch-depth: 1 fails the plain-text checks", "fetch-depth is not 0" in wf_problems(wt.replace("fetch-depth: 0", "fetch-depth: 1")))
    check("T9 the workflow's plain-text checks pass", not wf_problems(wt), str(wf_problems(wt)))
    if Path(al).exists():
        rc, o = sh(al, wf)
        check("T9 actionlint exits 0 on ci.yml", rc == 0, o[:300])
    else:
        print("NOT RUN: T9 actionlint: no actionlint")
else:
    check("T9 .github/workflows/ci.yml exists", False, "missing")

# ---- T10 the CI run set is total and honest
cfgt = tomllib.loads((ROOT / "cc.toml").read_text())["check"]
stems = [Path(f).stem for f in tomllib.loads((ROOT / "checks.toml").read_text())["roles"]["tests"]]
fast = [x for x in stems if x not in cfgt["slow"]]
skip_want = {x: n for n in ("needs_data", "needs_rust", "needs_commit_host") for x in cfgt[n] if x in fast}


UNDECLARED_FAILING = ["test_claims", "test_intake_example", "test_intake_terminal"]   # AQ3: fail with the data root too, so they are a real failure and an open blocker row, never a skip
check("T10 AQ3: test_frozen_run_1282 and test_docs_match (pass with the data root, fail without it) are in needs_data; the five that fail with it are in no skip list", {"test_frozen_run_1282", "test_docs_match"} <= set(cfgt["needs_data"]) and not set(UNDECLARED_FAILING) & (set(cfgt["needs_data"]) | set(cfgt["needs_rust"]) | set(cfgt["needs_commit_host"])), str(cfgt["needs_data"][-3:]))


def totality(run, skipped, fast_):
    return set(run) | set(skipped) == set(fast_) and not set(run) & set(skipped) and set(skipped) == set(skip_want)


check("T10 breaker: overlapping, partial and extra sets are each refused", not totality(fast, list(skip_want), fast) and not totality(fast[:-1], list(skip_want), fast) and not totality([x for x in fast if x not in skip_want] + ["extra"], list(skip_want), fast))
cr = ROOT / "release" / "ci-run.sh"
if cr.is_file():
    rc, o = sh("bash", cr, "--list")
    run = [ln.split()[1] for ln in o.splitlines() if ln.startswith("RUN ")]
    sk = {ln.split()[1].rstrip(":"): ln for ln in o.splitlines() if ln.startswith("SKIPPED ")}
    check("T10 ci-run.sh --list: RUN and SKIPPED are disjoint, total over the fast set, SKIPPED = fast and (needs_data or needs_rust)", rc == 0 and totality(run, list(sk), fast), f"exit {rc} run {len(run)} skipped {len(sk)} fast {len(fast)}")
    check("T10 every SKIPPED line cites the list it came from", all(skip_want.get(k) and skip_want[k] in v for k, v in sk.items()) and bool(sk), "reason missing")

    def jobs_seen(env, rust="['test_b']"):   # F3: the worker count a planted tree's `bin/cc test` receives from ci-run.sh, with or without CC_JOBS in the caller's environment
        with tempfile.TemporaryDirectory() as td:
            r = Path(td)
            (r / "release").mkdir(); (r / "bin").mkdir(); (r / "tests").mkdir()
            shutil.copy(cr, r / "release" / "ci-run.sh")
            (r / "checks.toml").write_text('[roles]\ntests = ["tests/test_a.py", "tests/test_b.py"]\n')
            (r / "cc.toml").write_text("[check]\nslow = []\nneeds_data = []\nneeds_rust = " + rust + "\nneeds_commit_host = []\n")
            (r / "bin" / "cc").write_text("import os, sys\nprint('STUB', sys.argv[1], 'JOBS=' + os.environ.get('CC_JOBS', 'unset'))\n")
            e = {k: v for k, v in os.environ.items() if k != "CC_JOBS"}
            e.update(env, PYTHON=sys.executable)
            q = subprocess.run(["bash", str(r / "release" / "ci-run.sh")], capture_output=True, text=True, env=e)
            return re.findall(r"STUB test JOBS=(\S+)", q.stdout), q.returncode
    check("T10 F3: ci-run.sh gives bin/cc test 2 workers by default (the 2-core limit), and honours CC_JOBS", jobs_seen({}) == (["2"], 0) and jobs_seen({"CC_JOBS": "5"}) == (["5"], 0), f"{jobs_seen({})} {jobs_seen({'CC_JOBS': '5'})}")
    check("T10 F-C5: ci-run.sh over a tree whose every skip list is empty prints no SKIPPED line and still runs every test (exit 0)", jobs_seen({}, "[]") == (["2"], 0), f"{jobs_seen({}, '[]')}")
else:
    check("T10 release/ci-run.sh exists", False, "missing")
res = need("T10 ci-local result", "CC_CI_LOCAL_RESULT")
if res:
    rt = Path(res).read_text()
    tree = git(ROOT, "rev-parse", "HEAD^{tree}")
    check("T10 the ci-local result is for the current tree and has zero FAILED lines", f"tree {tree}" in rt and not re.search(r"^FAILED ", rt, re.M), f"tree {tree}: " + "; ".join(re.findall(r"^FAILED .*", rt, re.M))[:200])

if ONLY and "T11" not in ONLY:
    print("test_public: " + ("FAILED " + str(len(bad)) + ": " + "; ".join(bad) if bad else "ok") + " (only " + ",".join(ONLY) + ")")
    sys.exit(1 if bad else 0)
# ---- T11 the turn-public check can fail; nothing leaks into the wheel
tp = ROOT / "release" / "turn-public-check.sh"
if tp.is_file() and PAT:
    env = {"CC_PRIVATE_PATTERNS": PAT}
    rc, o = sh("bash", tp, env={"CC_PRIVATE_PATTERNS": ""})
    check("T11 without CC_PRIVATE_PATTERNS the check REFUSES with exit 2 (it does not scan nothing)", rc == 2 and "REFUSED" in o, f"exit {rc}: {o[-120:]}")
    rc, o = sh("bash", tp, env=env)
    check("T11 on today's tree the check exits 1 naming every owner-gated row and idiom-followon", rc == 1 and all(r in o for r in OWNER_ROWS + ["idiom-followon"]), f"exit {rc}")
    with tempfile.TemporaryDirectory() as t:
        cp = Path(t) / "c"
        shutil.copytree(ROOT, cp, ignore=shutil.ignore_patterns(".git", "results", "__pycache__"))
        blk = cp / "release" / "public-blockers.toml"
        rows = tomllib.loads(blk.read_text())["row"]
        names = [r["name"] for r in rows]
        gated = {r["name"] for r in rows if r["state"] == "owner-gated"}
        synth = "".join(f'[[row]]\nname = "{n}"\nstate = "{"owner-gated" if n in gated else "closed"}"\ncheck = "true"\nruling = "planted"\n' for n in names)
        blk.write_text(synth)
        rc, o = sh("bash", cp / "release" / "turn-public-check.sh", cwd=cp, env=env)
        check("T11 breaker: with every row closed by a passing check the script exits 0 (it can say yes)", rc == 0, f"exit {rc}: {o[-200:]}")
        first_closed = next(r["name"] for r in rows if r["state"] == "closed")
        blk.write_text(synth.replace(f'name = "{first_closed}"\nstate = "closed"', f'name = "{first_closed}"\nstate = "open"', 1))
        rc, o = sh("bash", cp / "release" / "turn-public-check.sh", cwd=cp, env=env)
        check("T11 an open row exits 1 naming it", rc == 1 and first_closed in o, f"exit {rc}: {o[-200:]}")
        blk.write_text(synth.replace('check = "true"', 'check = "false"', 1))
        rc, o = sh("bash", cp / "release" / "turn-public-check.sh", cwd=cp, env=env)
        check("T11 a closed row whose check fails is re-run and exits 1", rc == 1, f"exit {rc}")
        blk.write_text(synth.split("[[row]]", 2)[0] + "[[row]]" + synth.split("[[row]]", 3)[2] if len(names) > 2 else synth)
        rc, o = sh("bash", cp / "release" / "turn-public-check.sh", cwd=cp, env=env)
        check("T11 a deleted row exits 1 naming the missing row", rc == 1 and names[0] in o, f"exit {rc}: {o[-200:]}")
        blk.write_text(synth)
        (cp / "tests" / "zz_planted.txt").write_text(PLANTED_WORD + "\n")
        sh("git", "init", "-q", cwd=cp)
        sh("git", "add", "-A", cwd=cp)
        rc, o = sh("bash", cp / "release" / "turn-public-check.sh", cwd=cp, env=env)
        check("T11 a planted vocabulary word in a tracked file exits 1", rc == 1, f"exit {rc}")
else:
    check("T11 release/turn-public-check.sh exists (and CC_PRIVATE_PATTERNS is set)", False, "missing")


def leaked(names):
    return [n for n in names for k in LEAKS if n.startswith(("criticality_compass/workspace/" + k, k))]


check("T11 breaker: a wheel listing that carries a release/public file is found", leaked(["criticality_compass/workspace/release/public_scan.py"]) != [])
with tempfile.TemporaryDirectory() as t:
    src = Path(t) / "src"
    for n in [n for n in sh("git", "ls-files", "-z")[1].split("\0") if n]:
        if (ROOT / n).is_file():
            (src / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / n, src / n)
    for n in files:   # the new, not yet tracked files count: the wheel is built from the working tree
        if (ROOT / n).is_file() and not (src / n).exists():
            (src / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / n, src / n)
    rc, o = sh(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", Path(t) / "dist", src)
    whl = sorted((Path(t) / "dist").glob("*.whl"))
    check("T11 a wheel builds", rc == 0 and len(whl) == 1, o[-200:])
    if whl:
        names = zipfile.ZipFile(whl[0]).namelist()
        check("T11 the wheel carries none of release/public*, release/ci-*, turn-public-check, .github, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, .gitleaks.toml", not leaked(names), str(leaked(names)[:5]))

print("test_public: " + ("FAILED " + str(len(bad)) + ": " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
