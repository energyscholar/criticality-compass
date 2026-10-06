"""test_explain_pair - `explain <input> a->b` prints, for each instrument that reads the pair, THAT instrument's own stored numbers
under its own heading (plan 0881 P2.1). The defect: the first reading of the pair (across_delta) was printed with the ALONG
trace (ln|Delta|, A, B recomputed from delta) under its heading; the stored y_steps and ratio were never shown."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


out = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), "explain", "x2b-xy-3", "0.85->0.89294", "--tables", "v08-rules"],
                     capture_output=True, text=True).stdout.splitlines()
heads = [i for i, ln in enumerate(out) if ln and not ln.startswith(" ") and "(pair " in ln]
sec = {out[i].split()[0]: "\n".join(out[i:(heads[k + 1] if k + 1 < len(heads) else len(out))]) for k, i in enumerate(heads)}
check("one section per instrument that reads the pair", set(sec) == {"across_delta", "along", "stability_delta"}, str(sorted(sec)))
ad, al = sec.get("across_delta", ""), sec.get("along", "")
check("across_delta shows its stored y_steps (0.09186, 0.04746) and ratio", "y_steps" in ad and "0.09186" in ad and "ratio 0" in ad, ad)
check("across_delta shows its own reading y_last 0.04746", "y_last 0.04746" in ad)
check("across_delta carries NO along trace (the along B value 0.06966 is not under its heading)", "0.06966" not in ad and "KERNEL" not in ad, ad)
check("along keeps its ln|Delta| A,B trace and its own reading", "KERNEL" in al and "0.06966" in al and "y_along 0.06966" in al, al)
check("stability_delta shows its stored y_steps", "y_steps" in sec.get("stability_delta", "") and "d -0.0444" in sec.get("stability_delta", ""))
print("test_explain_pair: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
