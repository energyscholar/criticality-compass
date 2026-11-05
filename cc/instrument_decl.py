"""The one instrument loader (plan 1282 P2a, R-P2.3): an instrument declaration (instruments/<name>.toml) with its optional fields filled
from ONE declared defaults table, beside the schema of cc/declare.py chk_instrument. A reader reads inst["per_point"] and restates no default.
Standard library only (cc/schema.py imports it)."""
import tomllib
from pathlib import Path

DEFAULT = {"per_point": False}   # an optional field whose absence has a fixed meaning -> that meaning: a pair instrument not read per point


def fill(parsed):
    """The declaration with DEFAULT under it: the one place a default is applied."""
    return {**DEFAULT, **parsed}


def load(name, root):
    """fill of the parsed instruments/<name>.toml under `root`."""
    return fill(tomllib.loads((Path(root) / "instruments" / f"{name}.toml").read_text()))
