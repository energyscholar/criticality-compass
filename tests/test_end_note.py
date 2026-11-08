"""test_end_note - plan 0872 F3: a family names each end point (point, side, kind), and show / explain of that point print "end of a LINE run (family <id>, END-<kind>)"
beside its per-point reading. No verdict changes: the notes are read from the STORED family, and a point that ends nothing prints nothing."""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import family  # noqa: E402
import view  # noqa: E402

NULLS = ["NOT-MEASURED", "NOT-EVALUATED"]


SET = ROOT / "tables" / "v05-rules"
FAM, FTEXT = tomllib.loads((SET / "family.toml").read_text()), (SET / "family.toml").read_text()
PLANT = tomllib.loads((ROOT / "tests" / "planted" / "ends.toml").read_text())
M0 = {"instruments": [], "eps": {}}


def planted(pl):
    sig = [{"point": q.split(":")[0], **PLANT["kind"][q.split(":")[1]]} for q in pl["points"]]
    return family.compute({"interior": pl["interior"]}, {"signature": sig}, None, FAM, FTEXT, M0, NULLS)


for pl in PLANT["plant"]:
    got = planted(pl)
    ok = [e["point"] for e in got["ends"]] == got["end_point"] and all(e["kind"].startswith("END-") and e["side"] in ("lower", "upper") for e in got["ends"])
    check(f"planted: {pl['name'][:70]}: ends name each end point with its side and an END-kind ({len(got['ends'])} end(s))", ok, str(got["ends"]))
check("a planted family that ends nothing names no end", any(planted(pl)["ends"] == [] for pl in PLANT["plant"]))

res = json.loads((ROOT / "results" / "x2b-xy@v05-rules.json").read_text())
NOTE = "end of a LINE run (family x2b-xy, END-BKT-CANDIDATE)"
for mode in ("basic", "advanced"):
    lines = view.show(res, None, mode)
    at = [i for i, ln in enumerate(lines) if NOTE in ln]
    pts = [i for i, ln in enumerate(lines) if ln.startswith("point ")]
    owner = [ln.split()[1] for ln in (lines[max(i for i in pts if i < a)] for a in at)]
    check(f"show ({mode}) prints the note once, under point 0.89294 and no other", len(at) == 1 and owner == ["0.89294"], str(owner))
exp = view.explain(res, "0.89294", None, "basic")
check("explain of the end point prints the note; explain of another point does not", sum(NOTE in ln for ln in exp) == 1 and not any(NOTE in ln for ln in view.explain(res, "0.8", None, "basic")))
other = json.loads((ROOT / "results" / "b7-at-line-2@v05-rules.json").read_text())
check("a result whose family ends nothing prints no note", not any("end of a LINE run" in ln for ln in view.show(other, None, "basic")))
v04 = json.loads((ROOT / "results" / "x2-xy-line-3@v04-rules.json").read_text())
check("a set whose family rule has no sides prints no note", family.end_notes(ROOT, v04) == {} and not any("end of a LINE run" in ln for ln in view.show(v04, None, "advanced")))
check("the family's verdict is unchanged by the note (REFUSE-UNCLASSIFIED-v0 under v05-rules)", family.run(ROOT, "x2b-xy", "v05-rules")[1][1]["verdict"] == "REFUSE-UNCLASSIFIED-v0")
print("".join(f"FAILED {x}\n" for x in bad) + "test_end_note: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
