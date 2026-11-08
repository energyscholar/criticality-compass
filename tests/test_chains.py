"""test_chains - plan 0937 P1 (interval method `chains`, T18-B): (A1) the readout equals navigator v2's nav2.interval on 1000 seeded vectors (and an off-by-one r differs);
rank(m, alpha) equals nav2.rank; the method tables are TOTAL over cc.toml alphabets.interval_method; (A3) the loader refuses a block input under v10-rules and (via reverdict)
a block result under v10-rules and a chains result under v08-rules. Needs the toolset (nav2.py, sha256 pinned) at the data root's parent."""
import hashlib
import importlib.util
import json
import sys
import tomllib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import detect  # noqa: E402
import door  # noqa: E402
import readout  # noqa: E402
import reverdict  # noqa: E402
import schema  # noqa: E402


cfg = tomllib.loads((ROOT / "cc.toml").read_text())
nav = Path(schema.resolve_data_root(cfg)[0]).parent / "studies" / "NAV-AT" / "nav2.py"
check("nav2.py is the pinned reference (sha256 c5a52cf1...)", nav.is_file() and hashlib.sha256(nav.read_bytes()).hexdigest().startswith("c5a52cf1"), str(nav))
spec = importlib.util.spec_from_file_location("nav2", nav)
nav2 = importlib.util.module_from_spec(spec)
bootstrap(nav.parent.parent.parent, "tools")
spec.loader.exec_module(nav2)
rng = np.random.default_rng(937)
same = off = 0
for _ in range(1000):
    d = rng.normal(size=10) * rng.uniform(0.1, 5) + rng.normal()
    v = np.concatenate([[d[0]], d])                      # row 0 = the reference row (chain 0), rows 1..m the chains
    est, lo, hi, cell = readout.chains(v, 2, 0.1)
    same += (float(lo), float(hi)) == nav2.interval(d, 10) and est == np.median(d)
    off += (float(readout.chains(v, 3, 0.1)[1]), float(readout.chains(v, 3, 0.1)[2])) != nav2.interval(d, 10)
check("A1 chains readout == nav2.interval on 1000 seeded vectors (m 10, r 2), estimate = median", same == 1000, str(same))
check("A1 seen red: r off by one differs on 1000 of 1000", off == 1000, str(off))
check("rank(m, alpha) == nav2.rank for m 4..40 and the sealed alpha 22/1024", all(readout.rank(m, a) == nav2.rank(m, a) for m in range(4, 41) for a in (22 / 1024, 0.05, 0.01)) and readout.rank(10, 22 / 1024) == 2)
al = set(cfg["alphabets"]["interval_method"])
check("door.COVERAGE, door.ROW_COUNT, detect.ROWS and cc.toml interval_fields are total over the alphabet", set(door.COVERAGE) == set(door.ROW_COUNT) == set(detect.ROWS) == set(cfg["interval_fields"]) == al, str(al))
check("chains coverage = 1 - alpha = 0.978515625", door.COVERAGE["chains"]({"alpha": 22 / 1024}) == 0.978515625)
check("v10-rules reads only chains; v08-rules the resampling methods", schema.interval_methods(ROOT, "v10-rules") == ["chains"] and "chains" not in schema.interval_methods(ROOT, "v08-rules"))
try:
    detect.run_keyed("w2-potts-2", "v10-rules", False)
    check("A3 a block input under v10-rules is refused", False, "ran")
except detect.Refused as e:
    check("A3 a block input under v10-rules is refused (loader, with a Next line)", "Next:" in str(e) and "chains" in str(e), str(e))
res = json.loads(next(ROOT.joinpath("results").glob("w2-potts-2@v0*.json")).read_text())
check("A3 a block result is not re-verdicted under v10-rules", (reverdict.reverdict_refusal(res, "v10-rules") or "").startswith("REFUSED"))
fake = {**res, "interval": {"method": "chains"}}
check("A3 a chains result is not re-verdicted under v08-rules", (reverdict.reverdict_refusal(fake, "v08-rules") or "").startswith("REFUSED"))
print("test_chains: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
