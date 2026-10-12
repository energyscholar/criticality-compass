"""Packaging (queue S6.6). The workspace the runtime reads (bin/, cc/, tables/, inputs/, cases/, results/ ...) is copied into the wheel as
criticality_compass/workspace/, so a NON-editable `pip install .` (and a built wheel) can run `compass validate`. bin/cc finds its root as the
parent of its own directory, so the copy keeps the clone's shape. A clone still wins: from an editable install the launcher uses the clone."""
import json
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

# Plan 0985 phase 3: the wheel carries what the INSTALLED tool needs (evidence: a workspace copy without X, run through validate / show / run --dry / tabulate / bench verify):
#   results/ (frozen results: a run REFUSES without them), data/ (cc.toml [data] local: the CC0 l8 files; validate finds 'l8' absent without it), docs/ (tabulate writes
#   docs/verdict-table.html), benchmark/ (bench verify) - and of tests/ ONLY the files FROZEN.json names (the structure gate's C7 REFUSES a run without them).
#   The other tests are the clone's: `bin/cc check` in a workspace without them REFUSES (tests/test_install_refuses.py).
TREES = ["bin", "cc", "tables", "inputs", "cases", "expected", "families", "fixtures", "instruments", "results", "benchmark", "docs", "data"]
FILES = ["cc.toml", "checks.toml", "FROZEN.json", "README.md", "CLAIMS.md", "LICENSE", "NOTICE", "HOWTO.md", "TUTORIAL.md", "KERNEL-IN-CC.md", "SIGNATURE-TABLE.md"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "reduced", "_ext")   # _ext: the committed kernel_rs.so is one platform's binary; the kernel is an extra


class build_py_workspace(build_py):
    def run(self):
        super().run()
        here, dest = Path(__file__).resolve().parent, Path(self.build_lib) / "criticality_compass" / "workspace"
        shutil.rmtree(dest, ignore_errors=True)
        for t in TREES:
            if (here / t).is_dir():
                shutil.copytree(here / t, dest / t, ignore=SKIP)
        for f in json.loads((here / "FROZEN.json").read_text())["files"]:   # the frozen test files, whatever they are named: derived from the record, not listed here
            if f.startswith("tests/") and (here / f).is_file():
                (dest / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(here / f, dest / f)
        for f in FILES:
            if (here / f).is_file():
                shutil.copy2(here / f, dest / f)
        (dest / "cc" / "_ext").mkdir(parents=True, exist_ok=True)


setup(cmdclass={"build_py": build_py_workspace})
