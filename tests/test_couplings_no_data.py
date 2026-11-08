"""test_couplings_no_data - plan 1282 P2a (R-P2.1): a couplings.toml whose sibling m.toml declares no [data], or a [data] without format or
without files, is ONE finding at the couplings file naming what is missing, never a KeyError. Each case copies inputs/k4-m1 (its m.toml with the
[data] parts cut as text) into a temporary root beside cc.toml, checks.toml and instruments/, and calls declare.check_file, the entry `bin/cc validate`
reaches chk_couplings through (declare.KIND["couplings"]).
Seen RED on 3e0b80f (every case FAILs on KeyError: 'data', 'format' or 'files', raised from scalar_keys)."""
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")

SRC = "k4-m1"


def sections(text):
    """The m.toml cut into (header, lines) at each line that opens a table; the preamble's header is None."""
    out = [[None, []]]
    for ln in text.splitlines(keepends=True):
        if re.match(r"^\[", ln):
            out.append([ln.strip(), []])
        out[-1][1].append(ln)
    return out


def cut(drop_table, drop_files, drop_format):
    secs = sections((ROOT / "inputs" / SRC / "m.toml").read_text())
    keep = [(h, [ln for ln in body if not (drop_format and h == "[data]" and ln.startswith("format"))]) for h, body in secs
            if not (drop_table and h in ("[data]", "[[data.files]]")) and not (drop_files and h == "[[data.files]]")]
    return "".join(ln for _, body in keep for ln in body)


def run(name, text, missing):
    import declare
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for f in ("cc.toml", "checks.toml"):
            shutil.copy(ROOT / f, t / f)
        shutil.copytree(ROOT / "instruments", t / "instruments")
        (t / "inputs" / SRC).mkdir(parents=True)
        shutil.copy(ROOT / "inputs" / SRC / "couplings.toml", t / "inputs" / SRC / "couplings.toml")
        (t / "inputs" / SRC / "m.toml").write_text(text)
        out = declare.check_file(t / "inputs" / SRC / "couplings.toml", root=t)
    check(f"{name}: exactly one finding", len(out) == 1, repr(out))
    check(f"{name}: located at the couplings file", len(out) == 1 and out[0].loc.split(":")[0] == f"inputs/{SRC}/couplings.toml", repr(out))
    check(f"{name}: the message names {missing}", len(out) == 1 and all(k in out[0].msg for k in missing), repr(out))


for name, args, missing in (("C1 no [data]", (True, False, False), ["[data].format", "[data].files"]),
                            ("C2 [data] without format", (False, False, True), ["[data].format"]),
                            ("C3 [data] without files", (False, True, False), ["[data].files"])):
    guarded(name, lambda name=name, args=args, missing=missing: run(name, cut(*args), missing))
print("".join(f"FAILED {b}\n" for b in bad) + "test_couplings_no_data: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
