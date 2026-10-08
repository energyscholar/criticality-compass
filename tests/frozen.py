"""frozen - the ONE helper for a test that copies a directory the freeze made read-only (plan 0894 P2, E379/E391).
`thaw(path)` restores owner-write on a COPY (the path and everything under it); never call it on the live tree."""
import stat
from pathlib import Path


def thaw(path):
    p = Path(path)
    for q in [p, *(p.rglob("*") if p.is_dir() else [])]:
        q.chmod(q.stat().st_mode | stat.S_IWUSR)
    return p
