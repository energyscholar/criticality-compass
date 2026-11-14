"""Test 6 (plan 1511 §3): the vendored sampler matches the sha256 pin in vendor/VENDOR.toml — re-computed, none hardcoded."""
import hashlib
import shutil
import tomllib

from conftest import PLUGIN_DIR

VENDOR = PLUGIN_DIR / "vendor"


def mismatches(vendor_dir):
    pin = tomllib.loads((vendor_dir / "VENDOR.toml").read_text())["sha256"]
    got = {n: hashlib.sha256((vendor_dir / n).read_bytes()).hexdigest() for n in pin}
    return sorted(n for n in pin if got[n] != pin[n]), sorted(pin)


def test_vendored_files_match_the_pin():
    bad, names = mismatches(VENDOR)
    assert names == ["lattice_at.py", "observables_at.py", "scale.py"]
    assert bad == []


def test_a_tampered_copy_is_caught(tmp_path):
    d = tmp_path / "vendor"
    shutil.copytree(VENDOR, d, copy_function=shutil.copyfile)
    (d / "scale.py").write_bytes((d / "scale.py").read_bytes() + b"\n# tamper\n")
    assert mismatches(d)[0] == ["scale.py"]
