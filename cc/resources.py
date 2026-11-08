"""resources - the memory a measurement needs, as declared data (plan 0881 P1.1). A measured input records its peak resident
memory in its result (`peak_rss_mb`); a pool of measuring workers is SIZED from the declared budget (cc.toml [check] memory_gb)
and those recorded peaks, so the sum of its workers' peaks cannot exceed the budget. Nothing here retries or catches a kill."""
import json
import resource
import sys
from pathlib import Path
from typing import NamedTuple
import schema


def _clear_refs():
    Path("/proc/self/clear_refs").write_text("5")   # Linux: clear_refs 5 zeroes this process's high-water mark
    return True


def _no_row():
    raise ImportError(f"cc/resources: no platform row for {sys.platform!r}; add one to PLATFORMS")


class Platform(NamedTuple):
    reset: object       # a function that zeroes the high-water mark and returns True, or None where the OS has none
    unit_bytes: int     # bytes per ru_maxrss unit (Linux KiB, macOS bytes)


PLATFORMS = {"linux": Platform(_clear_refs, 1024), "darwin": Platform(None, 1)}
ROW = PLATFORMS.get(sys.platform) or _no_row()


def reset_peak(row=None):
    """Zero the high-water mark where the platform can; True iff it did (plan 1335), so a peak is recorded only after a real reset."""
    row = row or ROW
    return bool(row.reset and row.reset())


def peak_mb(row=None):
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (row or ROW).unit_bytes / 2**20


def recorded_peaks(root, names, tables):
    """{input: recorded peak MB, or None when its result under `tables` records none (or does not exist)}."""
    out = {}
    for n in names:
        p = schema.result_path(root, n, tables)
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
