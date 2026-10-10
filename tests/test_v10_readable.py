"""test_v10_readable - plan 0937 A4: the old Detector stays READABLE. Every stored result under results/ renders byte-identically through `show`
and re-verdicts (under its own rules) byte-identically (but for code_hash, which records the edited code), as recorded by the tree BEFORE the v10 edits (tests/v10_readable.tsv: result id, sha256 of
the show text, sha256 of the re-verdicted JSON). measure_hash epoch 2 moves every result's reuse key (declared in advance, toolset LOG E597 and the
Plan 0937 phase 1 commit message), never what a result says. `--record` rewrites the table (run it only on a tree whose readers are the reference)."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import reverdict  # noqa: E402
import score  # noqa: E402
import view  # noqa: E402

TSV = ROOT / "tests" / "v10_readable.tsv"
H = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731


def digests():
    out = {}
    for f in sorted((ROOT / "results").glob("*.json")):
        res = json.loads(f.read_text())
        if res.get("kind") != "result":
            continue
        shown = "\n".join(view.show(res, score.join(res["input"]), "basic", ""))
        again = json.dumps({k: v for k, v in reverdict.reverdict_result(res, detect.load_tables(res["tables"])).items() if k != "code_hash"}, sort_keys=True)   # code_hash records the code, which this plan edits by design
        out[res["run_id"]] = (H(shown), H(again))
    return out


if "--record" in sys.argv:
    rec = digests()
    TSV.write_text("".join(f"{k}\t{a}\t{b}\n" for k, (a, b) in rec.items()))
    print(f"recorded {len(rec)} results in {TSV}")
    sys.exit(0)
want = {k: (a, b) for k, a, b in (ln.split("\t") for ln in TSV.read_text().splitlines())}
got = digests()
moved = sorted(k for k in want if got.get(k) != want[k])
print(f"test_v10_readable: {len(want)} stored results, {len(moved)} moved" + (f": {moved[:3]}" if moved else ""))
bad = [] if want and not moved and set(got) == set(want) else ["moved"]
print("PASS test_v10_readable" if not bad else "FAIL test_v10_readable\n  Next: a stored result no longer reads as recorded; an unpredicted move is a STOP, never a re-record")
sys.exit(bool(bad))
