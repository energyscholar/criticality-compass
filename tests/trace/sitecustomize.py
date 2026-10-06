"""sitecustomize.py - the READ TRACER of tests/test_golden.py (plan 0882 P3). Imported by every python process that starts with this
directory on PYTHONPATH and CC_TRACE_LOG set. It OBSERVES what a transcript touches and changes nothing: one line per distinct path per
process, appended at once (a process that ends by os._exit loses nothing):
  R <path>  opened for reading (open, io.open, Path.open/read_*, np.load, zipfile, and the import system's open_code)
  S <path>  stat'ed (exists, is_file, is_dir, stat().st_size ...), present or not
  D <path>  a directory listing taken (os.scandir, os.listdir: glob, iterdir, rglob, walk)
and, at exit, R for every module file the process imported. Only paths under CC_TRACE_ROOT (the transcript's copy of the repo) and
CC_TRACE_DATA (the data root) and CC_TRACE_TOOLSET (the toolset root, the data root's parent: where a transducer's `update` sha check reads) are logged; nothing else is part of the read set."""
import atexit
import io
import os
import sys

_LOG = os.environ.get("CC_TRACE_LOG")
if _LOG:
    _ROOT = os.environ["CC_TRACE_ROOT"].rstrip("/") + "/"
    _DATA = os.environ["CC_TRACE_DATA"].rstrip("/") + "/"
    _TOOLSET = os.environ["CC_TRACE_TOOLSET"].rstrip("/") + "/"
    _seen = set()
    _fd = os.open(_LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT)

    def _note(kind, p):
        try:
            p = os.path.abspath(os.fsdecode(os.fspath(p)))
            if (p + "/").startswith(_ROOT) or p.startswith(_ROOT) or p.startswith(_DATA) or p.startswith(_TOOLSET) or (p + "/") == _ROOT or (p + "/") == _DATA or (p + "/") == _TOOLSET:
                if (kind, p) not in _seen:
                    _seen.add((kind, p))
                    os.write(_fd, f"{kind} {p}\n".encode())
        except Exception:   # a path that cannot be named is not a path the transcript can have read by name
            pass

    _open, _open_code, _stat, _scandir, _listdir = io.open, io.open_code, os.stat, os.scandir, os.listdir

    def _read(file, mode="r", *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and not (set(str(mode)) & set("wax+")):
            _note("R", file)
        return _open(file, mode, *a, **k)

    def _code(path):
        _note("R", path)
        return _open_code(path)

    def _st(path, *a, **k):
        if isinstance(path, (str, bytes, os.PathLike)):
            _note("S", path)
        return _stat(path, *a, **k)

    def _sd(path="."):
        _note("D", path)
        return _scandir(path)

    def _ld(path="."):
        _note("D", path)
        return _listdir(path)

    import _io
    import builtins
    io.open = builtins.open = _read
    _io.open_code = _code
    io.open_code = _code
    os.stat, os.scandir, os.listdir = _st, _sd, _ld

    def _modules():
        for m in list(sys.modules.values()):
            f = getattr(m, "__file__", None)
            if isinstance(f, str) and f.endswith(".py"):
                _note("R", f)
    atexit.register(_modules)
