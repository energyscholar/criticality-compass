"""test_format_optional - plan 1176 phase D0 (the gate note on phase A): the FORMAT rows that state `required = false`
are EXACTLY [plane], [plane.slice], [plane.fast_window] (plan 1176 amendment E0) and [suspect]. Phase A's E1 lets a row stating `required = false` be absent (intake_blind.section), so
without this test any section could be made silently optional by one line of intake/FORMAT.toml, and nothing would go red.
It walks the whole of intake/FORMAT.toml (every table and every array of tables, not only [fields]) and reads no data.
 D0. the set of dotted paths whose row states `required = false` is {fields.plane, fields.plane.fields.slice,
     fields.plane.fields.fast_window, fields.suspect} (E0 added fast_window: absent = the whole span).
     Red: `required = false` added to [fields.knobs] in intake/FORMAT.toml (the set gains fields.knobs; FAIL by this name)."""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPTIONAL = {"fields.plane", "fields.plane.fields.slice", "fields.plane.fields.fast_window", "fields.suspect"}   # only these may be absent (plan 1176 A; E0)


from lib import bad, check  # noqa: E402


KIDS = {dict: lambda node: node.items(), list: lambda node: ((str(i), v) for i, v in enumerate(node))}   # a table's or an array's children


def optional(node, at):
    """Every dotted path under `node` whose table states `required = false` (arrays of tables are walked by index)."""
    here = {at} if isinstance(node, dict) and node.get("required") is False else set()
    return here.union(*(optional(v, f"{at}.{k}".lstrip(".")) for k, v in KIDS.get(type(node), lambda node: ())(node)))


fmt = tomllib.loads((ROOT / "intake" / "FORMAT.toml").read_text())
found = optional(fmt, "")
check("D0. the FORMAT rows stating required = false are exactly plane, plane.slice, plane.fast_window and suspect", found == OPTIONAL,
      f"extra {sorted(found - OPTIONAL)}, missing {sorted(OPTIONAL - found)}")
print(f"{len(bad)} failed" if bad else "test_format_optional: all passed")
sys.exit(1 if bad else 0)
