"""Plan 1511: the environment-side config loaders (Parse B, server side) and the plugin loader (§11.0).
`system-instantiated` has a hyphen, so the plugin is loaded by path (importlib spec_from_file_location)."""
import importlib.util
import tomllib
from dataclasses import dataclass
from pathlib import Path

from navigator import reader as R

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "system-instantiated" / "plugins"
SYSTEMS = ("at",)  # the plugins this host knows


@dataclass(frozen=True)
class EnvConfig:
    system: str
    port: int
    run_dir_root: str


def load_toml(path):
    """-> dict | Malformed(field=<basename>)."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return R.Malformed(Path(path).name, str(e))


def parse_env_cfg(d):
    if not isinstance(d, dict):
        return R.Malformed("environment.toml", "table required")
    system = d.get("system")
    if system not in SYSTEMS:
        return R.Malformed("system", f"one of {SYSTEMS}")
    port = d.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return R.Malformed("port", "int 1..65535")
    root = d.get("run_dir_root")
    if not isinstance(root, str) or not root:
        return R.Malformed("run_dir_root", "non-empty str")
    return EnvConfig(system, port, root)


def plugin_dir(system):
    return PLUGINS / system


def load_plugin(system):
    f = plugin_dir(system) / "plugin.py"
    spec = importlib.util.spec_from_file_location(f"plugin_{system}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_server_cfgs(env_path, at_path=None):
    """-> (EnvConfig, AtConfig, TauConfig) | Malformed. tau-v0.toml is a SIBLING of at.toml (§11.6)."""
    envd = load_toml(env_path)
    if isinstance(envd, R.Malformed):
        return envd
    env = parse_env_cfg(envd)
    if isinstance(env, R.Malformed):
        return env
    at_path = Path(at_path) if at_path else plugin_dir(env.system) / "at.toml"
    atd = load_toml(at_path)
    if isinstance(atd, R.Malformed):
        return atd
    at = R.parse_at_cfg(atd)
    if isinstance(at, R.Malformed):
        return at
    taud = load_toml(at_path.parent / "tau-v0.toml")
    if isinstance(taud, R.Malformed):
        return taud
    tau = R.parse_tau_cfg(taud)
    if isinstance(tau, R.Malformed):
        return tau
    return env, at, tau
