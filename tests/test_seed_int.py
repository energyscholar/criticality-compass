"""test_seed_int - plan 1282 P1c D5: the declared seed reaches numpy.random.default_rng as a plain int, the integer half of A4.4 (0937's SeedSequence streams are the other half).
Characterises P1a's sampler, so it is RED-exempt: GREEN at the base (e90c90f) and at close. Reads the author's data root (cc.toml [check] needs_data)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, real_root  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import numpy as np  # noqa: E402
import sampler  # noqa: E402

REAL = real_root()


def d5():
    t = sampler.load(sampler.toolset_of(REAL))
    assert not isinstance(t, sampler.Mismatch), f"the toolset does not match the pins: {t}"
    seen, real = [], np.random.default_rng

    def spy(arg=None, *a, **k):
        seen.append(type(arg))
        return real(arg, *a, **k)

    np.random.default_rng = spy   # sampler looks default_rng up on np.random at call time
    try:
        sampler.sample(t, sampler.KC, 0.0, 27, "random", sampler.seed_of("1282-v10", "poc", "1.00", 27, "random", 0), sampler.Run(5, 1, 2))
    finally:
        np.random.default_rng = real
    check("D5 default_rng was called once, with an int", seen == [int], str(seen))


try:
    d5()
except Exception as e:  # noqa: BLE001
    check("D5", False, f"{type(e).__name__}: {e}")
print("".join(f"FAILED {b}\n" for b in bad) + "test_seed_int: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
