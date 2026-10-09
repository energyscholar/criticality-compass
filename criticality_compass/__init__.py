"""criticality_compass - the launcher of the `compass` console script (plan 0929, ruling D-0929-1 (i) and (v)).
The clone IS the workspace: bin/cc finds its root as the parent of its own directory, the measurement keys hash the clone's cc/ and its git HEAD,
and inputs/ results/ tables/ expected/ live beside the code. So the only supported install is an EDITABLE one (`pip install -e <clone>`), where this
file is still inside the clone. This package holds no science and is not in any hash. It is named `compass`, never `cc` (a `cc` on PATH is the C compiler)."""
import runpy
import sys
from pathlib import Path


def clone_of(here):
    """The clone this launcher sits in, or None when it was copied out of one (a non-editable install)."""
    root = Path(here).resolve().parent.parent
    return root if (root / "bin" / "cc").is_file() and (root / "cc.toml").is_file() else None


def main(argv=None, here=__file__):
    root = clone_of(here)
    if root is None:
        print("REFUSED: this launcher is not inside a Criticality Compass clone (a non-editable install copies it into site-packages, where bin/cc and cc.toml are not).\n"
              "  Next: pip install -e <path to your clone>")
        return 1
    sys.argv = [str(root / "bin" / "cc"), *(sys.argv[1:] if argv is None else argv)]
    runpy.run_path(sys.argv[0], run_name="__main__")   # bin/cc ends in sys.exit(main(...))
    return 0
