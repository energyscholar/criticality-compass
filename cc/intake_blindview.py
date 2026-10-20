"""intake_blindview - `bin/cc intake blind`: the BLINDED VIEW of a RESERVED run (plan 1160 A41; role intake_blindview, its own line cap,
tests/test_budget.py BLINDVIEW_CAP, so the core cap is not raised). A deposit's file names can carry the slow value; a declaration whose
[source] is BLINDED reads only the view, a directory <cc-blind>/<id>/ of hard links named by ordinal (001.csv ...), so every Detail, census
line and report names ordinals. The name<->ordinal key is written to <cc-blind>/<id>.KEY.json, beside the view and outside it (the loader's
outside-universe partition, so an in-process read of it is logged as a bypass and S6 refuses the run); its sha256 is printed for the
declaration's [source] key_sha256, so the seal records it through the declaration's own sha256. No intake stage reads the key.
Invariant: it opens no data byte (a hard link and a stat only) and prints no selected name: a refusal's Detail counts names, never prints one."""
import hashlib
import json
import os
import re
from pathlib import Path

import intake_bytes
from intake_blind import Refuse, detail, gate
from intake_convert import ctables

USAGE = "bin/cc intake blind: usage: blind <id> <name>/<path> <file> [<file> ...]   (the deposit's directory, then the selected files in curve order)"
EXT = {True: lambda n: Path(n).suffix, False: lambda n: ""}   # an ordinal keeps a word-like suffix only: "run h=0.5" has the suffix ".5", a value


def ordinals(names):
    """One ordinal name per selected file, in order: 001.<ext> ... (wider when there are more than 999)."""
    width = max(3, len(str(len(names))))
    return [f"{k:0{width}d}" + EXT[re.fullmatch(r"\.[A-Za-z]\w*", Path(n).suffix) is not None](n) for k, n in enumerate(names, 1)]


def blind(ident, source, names, t):
    """The view and the key, or a Refuse: BLIND_ID_REFUSED | ROOT_UNRESOLVED | BLIND_NAME_REPEATED | SOURCE_FILE_ABSENT | BLIND_VIEW_EXISTS |
    BLIND_NOT_ONE_DEVICE, each decided before any link is made. A selected name is found by membership of the source's actual listing."""
    src, home = intake_bytes.located(source, t["roots"]), intake_bytes.located("<cc-blind>", t["roots"])
    view, key = Path(home) / ident, Path(home) / f"{ident}.KEY.json"
    have = lambda: {p.relative_to(src).as_posix() for p in Path(src).rglob("*") if p.is_file()}
    absent = lambda: [n for n in names if n not in have()]
    return gate([(lambda: re.fullmatch(r"\w[\w.-]*", ident) is not None, "BLIND_ID_REFUSED", lambda: detail(counts={"characters": len(ident)})),
                 (lambda: src != "" and Path(src).is_dir() and home != "" and Path(home).is_dir(), "ROOT_UNRESOLVED",
                  lambda: detail(words=[f"source '{source}'", "<cc-blind> (a name of intake/ROOTS.toml naming an existing directory)"])),
                 (lambda: len(set(names)) == len(names), "BLIND_NAME_REPEATED", lambda: detail(counts={"names given more than once": len(names) - len(set(names))})),
                 (lambda: not absent(), "SOURCE_FILE_ABSENT", lambda: detail(counts={"selected names not in the source's listing": len(absent())})),
                 (lambda: not view.exists() and not key.exists(), "BLIND_VIEW_EXISTS", lambda: detail(words=[f"<cc-blind>/{ident}"])),
                 (lambda: {(Path(src) / n).stat().st_dev for n in names} == {Path(home).stat().st_dev}, "BLIND_NOT_ONE_DEVICE",
                  lambda: detail(words=["a hard link cannot cross devices: <cc-blind> must be on the deposit's device"]))],
                lambda: _make(ident, source, src, names, view, key))


def _make(ident, source, src, names, view, key):
    view.mkdir()
    [os.link(Path(src) / n, view / o) for n, o in zip(names, ordinals(names))]
    body = json.dumps({"schema": 1, "kind": "intake-blind-key", "id": ident, "source": source, "key": dict(zip(ordinals(names), names))}, indent=1) + "\n"
    key.write_text(body)
    return len(names), ordinals(names), hashlib.sha256(body.encode()).hexdigest()


def blind_cli(root, ident, args, t):
    """bin/cc intake blind <id> <name>/<path> <file>...: the view and the key, and what to declare; exit 0, or the refusal and exit 1."""
    ct = ctables()
    say = {**ct["sentences"], **{r["code"]: r["sentence"] for r in ct["blind_reason"]}}
    ok = len(args) > 1 and not [a for a in args if a.startswith("--")]
    got = {True: lambda: blind(ident, args[0], args[1:], t), False: lambda: None}[ok]()
    text = {(True, True): lambda: f"blind {ident}: " + got.text(say),
            (True, False): lambda: f"blind {ident}: {got[0]} links under <cc-blind>/{ident}/ ({got[1][0]} .. {got[1][-1]}); the key is <cc-blind>/{ident}.KEY.json,"
                                   f" sha256 {got[2]}.\n  Declare [source] kind = \"BLINDED\", root = \"<cc-blind>/{ident}\", blinded_from = \"{args[0]}\","
                                   f" key_sha256 = \"{got[2]}\", and [selection] the ordinals. No intake stage reads the key; keep it unread until unblinding.",
            (False, False): lambda: USAGE}[(ok, isinstance(got, Refuse))]
    print(text())
    return {True: 0, False: 1}[ok and not isinstance(got, Refuse)]
