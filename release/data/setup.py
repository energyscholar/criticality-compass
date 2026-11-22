"""criticality-compass-data (plan 1639 D1): the stored results the code distribution does not carry, derived by release/partition.py from the repository this file sits in
(release/data/ of a clone, or of a copy of one). No code: the results land in criticality_compass/workspace/results/, beside the code distribution's own, file-disjoint.
They are staged under build/stage/ first, because setuptools builds a wheel only from a package; that package has no __init__.py here, the code distribution owns it."""
import shutil
import sys
from pathlib import Path

from setuptools import setup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "release"))
import partition  # noqa: E402

STAGE = HERE / "build" / "stage"
DEST = STAGE / "criticality_compass" / "workspace" / "results"
shutil.rmtree(STAGE, ignore_errors=True)
DEST.mkdir(parents=True)
for n in sorted(partition.split(ROOT)[1]):
    shutil.copy2(ROOT / "results" / n, DEST / n)

setup(package_dir={"": str(STAGE.relative_to(HERE))}, packages=["criticality_compass"], package_data={"criticality_compass": ["workspace/results/*"]})
