"""Packaging (queue S6.6). The workspace the runtime reads (bin/, cc/, tables/, inputs/, cases/, results/ ...) is copied into the wheel as
criticality_compass/workspace/, so a NON-editable `pip install .` (and a built wheel) can run `compass validate`. bin/cc finds its root as the
parent of its own directory, so the copy keeps the clone's shape. A clone still wins: from an editable install the launcher uses the clone."""
import json
import shutil
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

sys.path.insert(0, str(Path(__file__).resolve().parent / "release"))
import partition  # noqa: E402  (plan 1639: which result goes in which distribution, derived)

# Plan 0985 phase 3: the wheel carries what the INSTALLED tool needs (evidence: a workspace copy without X, run through validate / show / run --dry / tabulate / bench verify):
#   results/ (frozen results: a run REFUSES without them), data/ (cc.toml [data] local: the CC0 l8 files; validate finds 'l8' absent without it), docs/ (tabulate writes
#   docs/verdict-table.html), benchmark/ (bench verify) - and of tests/ ONLY the files FROZEN.json names (the structure gate's C7 REFUSES a run without them).
#   The other tests are the clone's: `bin/cc check` in a workspace without them REFUSES (tests/test_install_refuses.py).
TREES = ["bin", "cc", "tables", "inputs", "cases", "expected", "families", "fixtures", "instruments", "results", "benchmark", "docs", "data",
         "environment", "navigator", "needlestream", "common", "system-instantiated", "needle-settings", "manual", "needleview"]   # plan 1634: the stage-4 path `compass hold` runs
FILES = ["cc.toml", "checks.toml", "FROZEN.json", "README.md", "CLAIMS.md", "LICENSE", "NOTICE", "HOWTO.md", "TUTORIAL.md", "KERNEL-IN-CC.md", "SIGNATURE-TABLE.md",
         "registry.toml", "DATA-LICENSE", "CITATION.cff", "CHANGELOG.md"]   # plan 1639: registry.toml (validate and family read it), the data licence the CC BY 4.0 results ride on
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "reduced", "_ext")   # _ext: the committed kernel_rs.so is one platform's binary; the kernel is an extra


class build_py_workspace(build_py):
    def run(self):
        super().run()
        here, dest = Path(__file__).resolve().parent, Path(self.build_lib) / "criticality_compass" / "workspace"
        shutil.rmtree(dest, ignore_errors=True)
        code = partition.split(here)[0]   # plan 1639: results/ carries the frozen results and every result a shipped document names; the rest is criticality-compass-data, the sealed records are in no distribution
        for t in TREES:
            if (here / t).is_dir():
                shutil.copytree(here / t, dest / t, ignore=(lambda d, names: set(SKIP(d, names)) | {n for n in names if Path(d).name == "results" and n not in code}) if t == "results" else SKIP)
        for f in json.loads((here / "FROZEN.json").read_text())["files"]:   # the frozen test files, whatever they are named: derived from the record, not listed here
            if f.startswith("tests/") and (here / f).is_file():
                (dest / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(here / f, dest / f)
        for f in FILES:
            if (here / f).is_file():
                shutil.copy2(here / f, dest / f)
        (dest / "cc" / "_ext").mkdir(parents=True, exist_ok=True)


class sdist_derived(sdist):
    """plan 1639: the sdist holds what the code wheel holds (so a wheel built from it is the same wheel), plus the frozen tests and the sealed-record list."""
    def make_distribution(self):   # setuptools' sdist.run builds the list through egg_info, so the filter sits where the archive is written
        here = Path(__file__).resolve().parent
        self.filelist.files[:] = [f for f in self.filelist.files if partition.keep(here, f.replace("\\", "/"))]
        super().make_distribution()


setup(cmdclass={"build_py": build_py_workspace, "sdist": sdist_derived}, data_files=[("share/man/man1", ["docs/man/compass.1"])])   # plan 1634: `man compass`
