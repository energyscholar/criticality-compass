"""resources - the memory a measurement needs, as declared data (plan 0881 P1.1). A measured input records its peak resident
memory in its result (`peak_rss_mb`); a pool of measuring workers is SIZED from the declared budget (cc.toml [check] memory_gb)
and those recorded peaks, so the sum of its workers' peaks cannot exceed the budget. Nothing here retries or catches a kill."""
import json
import resource
from pathlib import Path


def reset_peak():
    """Zero this process's high-water mark (Linux: clear_refs 5), so the next peak_mb() is that of one measurement alone."""
    Path("/proc/self/clear_refs").write_text("5")


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024   # Linux reports KiB


def recorded_peaks(root, names, tables):
    """{input: recorded peak MB, or None when its result under `tables` records none (or does not exist)}."""
    out = {}
    for n in names:
        p = Path(root) / "results" / f"{n}@{tables}.json"
        out[n] = json.loads(p.read_text()).get("peak_rss_mb") if p.is_file() else None
    return out


def unrecorded(peaks):
    """The inputs whose peak is not recorded: their size is unknown, so each is measured ALONE, never in the pool."""
    return sorted(n for n, p in peaks.items() if p is None)


def pool_size(memory_gb, peaks, cpus):
    """max(1, floor(memory_gb*1024 / the largest RECORDED peak), at most cpus-2). Only inputs with a recorded peak belong to the pool
    (an unrecorded one is `unrecorded(peaks)`: its own slot); with none recorded the pool is one."""
    worst = max((p for p in peaks.values() if p is not None), default=memory_gb * 1024)
    return max(1, min(int(memory_gb * 1024 // worst), cpus - 2))
