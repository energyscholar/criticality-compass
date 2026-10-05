"""formats.py - the stack formats: readers and schema checks (plumbing; plan 0873 A1). A format is DATA: cc.toml [formats.<name>]
names its raw dims, its dtypes, the array kinds the door REDUCES from it (`reduces`) and one reader module per file extension; this
file holds no per-format code. A stack is s[N, L, L]; the levels it reduces to are derived from (L, final_size, factor), never trusted."""
import importlib.util
import tomllib
import zipfile
from functools import lru_cache
from pathlib import Path
import numpy as np
from numpy.lib import format as npy
import reduce

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def schemas(root=str(ROOT)):
    """{format name: schema} for every stack format cc.toml declares (a format with no table is a plain array file)."""
    return tomllib.loads((Path(root) / "cc.toml").read_text()).get("formats", {})


def have(module):
    return importlib.util.find_spec(module) is not None


def header(path, key):
    """(shape, dtype, None) of the stored stack without loading it, or (None, None, the keys the file holds)."""
    if Path(path).suffix == ".npz":
        with zipfile.ZipFile(path) as z:
            keys = [n[:-4] for n in z.namelist() if n.endswith(".npy")]
            return _head(z.open(key + ".npy")) if key in keys else (None, None, keys)
    with open(path, "rb") as f:
        return _head(f)


def _head(f):
    v = npy.read_magic(f)
    shape, _, dtype = npy.read_array_header_1_0(f) if v == (1, 0) else npy.read_array_header_2_0(f)
    return shape, dtype, None


def _tiff_header(path, key):
    import tifffile
    with tifffile.TiffFile(path) as t:
        return t.series[0].shape, t.series[0].dtype, None


def _tiff_read(path, key):
    import tifffile
    return tifffile.imread(path)


def _npy_read(path, key):
    z = np.load(path)
    return z if isinstance(z, np.ndarray) else z[key]


HEADER = {"numpy": header, "tifffile": _tiff_header}
READ = {"numpy": _npy_read, "tifffile": _tiff_read}


def levels_for(L, final, factor):
    """The number of block levels of an L-lattice that blocks down to `final` by `factor` (L = final * factor^k gives k + 1), else None."""
    if factor < 2 or final < 1:
        return None
    n = 1
    while final < L:
        final, n = final * factor, n + 1
    return n if final == L else None


def shape_of(fmt, path, key, root=str(ROOT)):
    """The shape of the stored stack, read from its header through the reader its extension names."""
    return HEADER[schemas(root)[fmt]["readers"][Path(path).suffix]](path, key)[0]


def read(fmt, path, key, root=str(ROOT)):
    """The raw stack s[N, L, L] of one file through the reader its extension names."""
    return READ[schemas(root)[fmt]["readers"][Path(path).suffix]](path, key)


def problems(fmt, loc, name, a, b, path, m, root=str(ROOT)):
    """[(field, message, Next)] for one reduced array (G or GL) of a block of a stack-format input: the file, its reader, its stack
    against cc.toml [formats.<fmt>], and the levels derived from (L, final_size, factor) against what m.toml declares."""
    sch, ext, at_ = schemas(root)[fmt], Path(path).suffix, f"{loc}.arrays.{name}"
    mod = sch["readers"].get(ext)
    if mod is None:
        return [(f"{loc}.path", f"{b['path']}: '{ext}' is not a file of format {fmt}", f"use a file with one of: {' '.join(sch['readers'])}")]
    if not have(mod):
        return [(f"{loc}.path", f"{b['path']}: no reader for {ext} files ({mod} is not importable)",
                 f"pip install {sch.get('pip', {}).get(mod, mod)}, or convert the stack to .npy (shape [N, L, L])")]
    shape, dtype, keys = HEADER[mod](path, a["key"])
    if shape is None:
        return [(at_, f"key '{a['key']}' absent from {b['path']} (keys: {' '.join(keys)})", "fix the key")]
    if len(shape) != sch["dims"] or shape[1] != shape[2] or str(dtype) not in sch["dtypes"]:
        return [(at_, f"{b['path']} stores {a['key']} as {str(dtype)} {list(shape)}; {fmt} needs {sch['dims']}-D [N, L, L] of {'/'.join(sch['dtypes'])}",
                 "write the stack as s[N, L, L], or declare another data.format")]
    ob, bm = m.get("observable"), m.get("block_map")
    if ob is None or bm is None:
        return [(at_, f"a {fmt} stack is reduced through the declared map, so m.toml needs [observable] and [block_map]", "add both tables")]
    L, out = shape[1], []
    out += [(f"{loc}.size", f"stored L {L} differs from the declared size {b['size']}", "fix size, or the file")] if L != b["size"] else []
    n = levels_for(L, ob["final_size"], bm["factor"])
    out += [("block_map.name", f"'{bm['name']}' is not a declared block map", f"use one of: {' '.join(reduce.MAPS)}")] if bm["name"] not in reduce.MAPS else []
    out += [("observable.final_size", f"L {L} is not final_size * factor^k (final_size {ob['final_size']}, factor {bm['factor']})",
             "set [observable] final_size and [block_map] factor so that L = final_size * factor^k, or fix the file")] if n is None else []
    want = ob["levels"][m["axes"]["size"].index(b["size"])] if b["size"] in m["axes"]["size"] else n
    out += [("observable.levels", f"{b['path']} reduces to {n} levels but observable.levels declares {want} for size {b['size']}",
             "set observable.levels to the derived level count")] if n is not None and want != n else []
    k = a.get("level")
    return out + ([(at_, f"level {k} is outside the {n} derived levels", f"use a level from 0 to {n - 1}")] if k is not None and n is not None and not 0 <= k < n else [])
