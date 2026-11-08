"""test_two_start_c2 - replay of the frozen C2 two-start screen (Blume-Capel, L = 81, 27 points)."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import detect  # noqa: E402

Z, S = "ZERO!", "SIG+"
B3, B2 = {Z, "SLOW+", "SLOW-"}, {"SLOW+", Z}
KS = ["1.0", "1.2", "1.4", "1.6", "1.8", "2.0", "2.3", "2.6", "3.0"]
WANT = {**{f"d2.0-K{k}": c for k, c in zip(KS, [B3, B2, Z, Z, Z, S, S, S, S])},
        **{f"d1.95-K{k}": c for k, c in zip(KS, [B3, Z, Z, Z, B3, B3, S, S, S])},
        **{f"d1.9-K{k}": c for k, c in zip(KS, [B3, B2, B2, B3, B3, B3, B3, B3, S])}}


frozen = {}
for d in ("2.0", "1.95", "1.9"):
    text = (Path(os.environ.get("CC_TOOLSET") or Path(os.environ["CC_DATA_ROOT"]).parent) / "results" / f"C2-run-{d}.txt").read_text()
    frozen.update({f"d{d}-K{m[0]}": float(m[1]) for m in re.findall(r"K ([\d.]+): .* D=([+-][\d.]+) ", text)})
res = detect.run("c2-bc-two-start", "verdict-x-rules", write=False)
rd = {r["unit"]["point"]: r for r in res["readings"] if r["instrument"] == "two_start"}
check("the 27 frozen D values were read", len(frozen) == 27 and set(frozen) == set(WANT), str(len(frozen)))
check("D estimates equal the printed ones (+-6e-4)",
      all(abs(rd[p]["per_size"][0]["estimate"] - v) < 6e-4 for p, v in frozen.items()))
cells = {p: rd[p]["per_size"][0]["cell"] for p in WANT}
check("cells (exact, boundary cells as sets)",
      all(cells[p] == w if isinstance(w, str) else cells[p] in w for p, w in WANT.items()), str(cells))
print("boundary cells landed:", {p: c for p, c in cells.items() if not isinstance(WANT[p], str)})
check("codes: COEXIST where SIG+, INDEP elsewhere",
      all(rd[p]["code"] == ("COEXIST" if cells[p] == S else "INDEP") for p in WANT))
print("".join(f"FAILED {b}\n" for b in bad) + "test_two_start_c2: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
