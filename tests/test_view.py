"""test_view - BASIC and ADVANCED are one view of one result: the expansion property, no hidden don't-know,
no REFUSE name outside BLANK (...), a view never changes the result, and the help text."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import view  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def blocks(lines):
    out, now = [], None
    for ln in lines:
        if ln.startswith("point "):
            now = []
            out.append(now)
        if now is not None:
            now.append(ln)
    return out


BLANK = re.compile(r"BLANK \(([A-Z-]+)(?::[^)]*)?\)")
runs = {i: detect.run(i, "verdict-x-rules", write=False) for i in ("b7-at-line", "w2-potts")}
for inp, res in runs.items():
    before = json.dumps(res, sort_keys=True)
    basic, adv = view.show(res, None, "basic"), view.show(res, None, "advanced")
    pts = [s["point"] for s in res["signature"]]
    one, other = view.explain(res, pts[-1], None, "basic"), view.explain(res, pts[-1], None, "advanced")
    check(f"{inp}: a view never changes the result", json.dumps(res, sort_keys=True) == before)
    ok, why = True, ""
    for bb, ab, sig in zip(blocks(basic), blocks(adv), res["signature"]):
        ok &= len(bb) == len(ab)
        for b, a in zip(bb, ab):
            keep = BLANK.sub(r"\1", b).split()
            hit = b.split()[:2 if b.startswith("point") else 1] == a.split()[:2 if a.startswith("point") else 1]
            if not (hit and all(t in a for t in keep)):
                ok, why = False, f"{b!r} is not inside {a!r}"
        want = f"BLANK ({sig['verdict']})" if sig["verdict_class"] == "REFUSE" else f"=> verdict {sig['verdict']}"
        if want not in bb[-2]:
            ok, why = False, f"{bb[-2]!r} lacks {want!r}"
    check(f"{inp}: every ADVANCED line holds its BASIC line (BLANK (x) read as x)", ok, why)
    left = [BLANK.sub("", ln) for ln in basic + one]
    check(f"{inp}: BASIC prints no REFUSE name outside BLANK (...)", not any("REFUSE" in ln for ln in left), str(left[:3]))
    allowed = {"NOT-MEASURED", "NOT-EVALUATED", "UNRES"} | {s["verdict"] for s in res["signature"]}
    blank = [ln for ln in basic + one if "BLANK" in ln]
    named = all(ln.count("BLANK") == ln.count("BLANK (") == len(BLANK.findall(ln)) and set(BLANK.findall(ln)) <= allowed for ln in blank)
    check(f"{inp}: every BLANK names its precise value", named and blank, str(blank[:2]))
    check(f"{inp}: ADVANCED shows the discarded fields", all(w in "\n".join(adv) for w in ("eps ", "flags: ", "code_commit", "class ")))
    check(f"{inp}: explain gives the same numbered steps in both modes", [x.split()[0] for x in one] == [x.split()[0] for x in other])
text = "\n".join(view.explain(runs["b7-at-line"], "0.07", None, "basic"))
why = runs["b7-at-line"]["signature"][1]["why"]
for want in ("b7/L4-0.0700-L27.npz", "27 <- 81 <- 243", "bL 3, bU 3 -> SIG+", "verdict.toml line 133", why):
    check(f"explain b7-at-line 0.07 contains {want!r}", want in text)
stale = json.loads(json.dumps(runs["b7-at-line"]))
stale["read"]["instruments/across.toml"] = "0" * 64
for name, lines in (("show", view.show(stale, None, "basic")), ("explain", view.explain(stale, "0.07", None, "basic"))):
    check(f"{name} refuses a result whose read hash changed, with a Next line",
          lines[0].startswith("REFUSED: instruments/across.toml changed") and lines[1].startswith("  Next: bin/cc run b7-at-line"), str(lines[:2]))
cc = lambda *a: subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), *a], capture_output=True, text=True).stdout  # noqa: E731
check("help ends with the start line", cc("help").endswith("start: bin/cc show b7-at-line\n"))
check("help --advanced lists freeze", "freeze" in cc("help", "--advanced"))
print("test_view: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
