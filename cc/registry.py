"""registry.py - the ONE reader of the registry projection (plan 1016; draft compass-cc-registry-gate-2026-10-14 s2, amended by rulings R1-R3).
registry.toml is a generated projection of the toolset's REGISTRY.toml (id, status, scope, release_module; never gated_by or note). cc.toml [registry]
pins its sha256, maps every unit this release can run (instrument.<name>, interval.<method>, family) to a registry id ([registry.units]) and holds the
TOTAL table (status, obtained) -> Run | RunScoped | Refuse ([registry.table]). The registry is a property of the RELEASE: nothing here is written into a result file.
Unreachable by construction: a Refuse holds no module; this file is the only importlib call site for units; an unknown id, status or pin reads as a Refuse VALUE."""
import functools
import hashlib
import importlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "cc" / "instruments") not in sys.path:
    sys.path.insert(0, str(ROOT / "cc" / "instruments"))


@dataclass(frozen=True)
class Run:
    module: str
    scope: tuple = ()

    def load(self):
        return _import(self.module)


@dataclass(frozen=True)
class RunScoped:
    module: str
    scope: tuple = ()

    def load(self):
        return _import(self.module)


@dataclass(frozen=True)
class Refuse:
    reason: str
    scope: tuple = ()


REFUSE_UNAVAILABLE = Refuse("mechanism not yet available")
VERBS = ("Run", "RunScoped", "Refuse")
GATE_STATUS = "no-module"   # the key of a row that names no release_module (cc.toml [registry.table])
ANY = "any"                 # an obtained value for a lookup with no input in hand (module loading, reading a stored result)


@functools.lru_cache(maxsize=None)
def _import(name):
    return importlib.import_module(name)   # measure-key: seeded


def config(root):
    return tomllib.loads((Path(root) / "cc.toml").read_text())


def sha256_of(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def table_keys(cfg):
    """Every key the total table must hold: (status or no-module) x (obtained or any)."""
    return [f"{s}/{o}" for s in [*cfg["alphabets"]["registry_status"], GATE_STATUS] for o in [*cfg["alphabets"]["obtained"], ANY]]


def build(verb, module, scope):
    """One Entry from a table value ('Run', 'RunScoped' or 'Refuse: <reason>'). A Refuse is made from the reason alone: it never sees the module."""
    head, _, reason = verb.partition(": ")
    return {"Run": lambda: Run(module), "RunScoped": lambda: RunScoped(module, scope), "Refuse": lambda: Refuse(reason)}[head]()


def _stem(path):
    return Path(path).stem


def parse(root):
    """(cfg, rows) or raises ValueError(reason): the pin checked, every id unique among live rows, every status in the alphabet."""
    root = Path(root)
    cfg = config(root)
    f = root / "registry.toml"
    if not f.is_file():
        raise ValueError("registry pin mismatch: registry.toml is missing")
    if sha256_of(f) != cfg["registry"]["sha256"]:
        raise ValueError("registry pin mismatch")
    live = {}
    for r in tomllib.loads(f.read_text())["row"]:
        if r["status"] not in cfg["alphabets"]["registry_status"]:
            raise ValueError(f"registry projection invalid: unknown status {r['status']}")
        if r["status"] != "superseded":
            if r["id"] in live:
                raise ValueError(f"registry projection invalid: two live rows for id {r['id']}")
            live[r["id"]] = r
    missing = [k for k in table_keys(cfg) if k not in cfg["registry"]["table"]]
    if missing:
        raise ValueError(f"registry projection invalid: cc.toml [registry.table] has no entry for {missing[0]}")
    return cfg, live


@functools.lru_cache(maxsize=None)
def dispatch(root=ROOT):
    """{(unit, obtained): Entry}. On any failure to load, EVERY key reads as the same Refuse (the release refuses to start, as a value)."""
    root = Path(root)
    cfg = config(root)
    keys = [(u, o) for u in cfg["registry"]["units"] for o in [*cfg["alphabets"]["obtained"], ANY]]
    try:
        cfg, rows = parse(root)
    except ValueError as e:
        return {k: Refuse(str(e)) for k in keys}
    out = {}
    for u, o in keys:
        row = rows.get(cfg["registry"]["units"][u])
        if row is None:
            out[(u, o)] = REFUSE_UNAVAILABLE
            continue
        kind = row["status"] if row["release_module"] else GATE_STATUS
        out[(u, o)] = build(cfg["registry"]["table"][f"{kind}/{o}"], _stem(row["release_module"]), (row["scope"],) if row["scope"] else ())
    return out


def lookup(unit, obtained=ANY, root=ROOT):
    """The Entry for one unit; a unit the map does not name is a default VALUE, not a branch."""
    return dispatch(Path(root)).get((unit, obtained), REFUSE_UNAVAILABLE)


def pin(root=ROOT):
    return config(root)["registry"]["sha256"]


def refusal(units, obtained_values, root=ROOT):
    """The first Refuse over every declared unit and every obtained value of an input, as (unit, Refuse), else None."""
    return next(((u, e) for u in units for o in sorted(obtained_values) if isinstance(e := lookup(u, o, root), Refuse)), None)


def scope_lines(units, root=ROOT):
    """The report lines for the units a result used: the pinned registry, then one line per distinct scope (a Run has none). Read from the CURRENT pinned
    projection at report time, so a stored result is never edited."""
    groups = {}
    for u in units:
        e = lookup(u, ANY, root)
        groups.setdefault(f"REFUSED ({e.reason})" if isinstance(e, Refuse) else "; ".join(e.scope), []).append(u.split(".", 1)[-1] if "." in u else u)
    return [f"registry: sha256 {pin(root)[:12]}"] + [f"scope: {s} — {', '.join(us)}" for s, us in groups.items() if s]


def project(text, blob, commit):
    """registry.toml text from REGISTRY.toml text. The only writer of the projection's content (bin/cc registry pull). Two live rows for one id fail here."""
    rows, live = [], set()
    for s in tomllib.loads(text)["structure"]:
        if s["status"] != "superseded":
            if s["id"] in live:
                raise ValueError(f"two live rows for id {s['id']}")
            live.add(s["id"])
        mod = s.get("release_module", "")
        scope = s.get("scope") or ("; ".join(s.get("awaiting", [])) if mod else "")
        rows.append((s["id"], s["status"], scope, mod))
    q = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'   # noqa: E731
    head = ('# registry.toml - GENERATED by `bin/cc registry pull <toolset-commit>`; never edit. A projection of the toolset REGISTRY.toml:\n'
            '# id, status, scope, release_module. It holds no gated_by and no note. cc.toml [registry] pins its sha256.\n'
            f'schema = 1\nkind = "registry-projection"\nsource_blob = "{blob}"\nsource_commit = "{commit}"\n')
    return head + "".join(f"\n[[row]]\nid = {q(i)}\nstatus = {q(st)}\nscope = {q(sc)}\nrelease_module = {q(m)}\n" for i, st, sc, m in rows)
