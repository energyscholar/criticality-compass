"""intake - `bin/cc intake explain | lint | seal | run | synth | convert | peek`: the command-line surface of the intake pipeline.
Invariant: the only intake module that prints or exits, every exit code from a table; it reads the tables and the declaration's text (never
a data byte: S3 reads those, cc/intake_bytes.py) and registers the stage bodies; it is what bin/cc and docs/gen-intake.py import."""
import tomllib
from pathlib import Path

import intake_blind as blind
import intake_bytes
import intake_census
import intake_choices
import intake_feasible
import intake_say
import intake_seal
import intake_terminal
from intake_blind import Mark
from intake_fold import Primary, before_data, fold, verdicts


ROOT = Path(__file__).resolve().parent.parent


def tables(root=ROOT):
    """The intake's tables as plain values: STAGES, POLICY and FORMAT, cc.toml's alphabets and interval fields (with FORMAT's own), every sentence."""
    load = {n: tomllib.loads((Path(root) / "intake" / f"{n.upper()}.toml").read_text()) for n in ("stages", "policy", "format")}
    cfg = tomllib.loads((Path(root) / "cc.toml").read_text())
    admit = {"policy.projection": load["policy"]["projection"], "policy.bridge": load["policy"]["bridge"],
             **{f"alphabet.{k}": v for k, v in cfg["alphabets"].items()}}
    sentences = {r["code"]: r["sentence"] for s in load["stages"]["stage"] for r in s["reason"]}
    roots = {k: str(Path(root) / Path(v).expanduser()) for k, v in tomllib.loads((Path(root) / "intake" / "ROOTS.toml").read_text())["root"].items()}
    fields = {**cfg["interval_fields"], **load["format"]["interval_fields"]}   # the intake's methods STATED and NONE (FORMAT.toml)
    return {**load, "admit": admit, "interval_fields": fields, "sentences": sentences, "roots": roots}


def bodies(t, d, text, findings):
    """The registered bodies of one run: S0 FORMAT, S1 CHOICES (cc/intake_choices.py), S2 SEAL (verify, advisory), plus
    intake_bytes.bodies (S3, S6), intake_census.bodies (S4, S5) and intake_feasible.bodies (S7, S8, S9) and intake_terminal.bodies (S10). Invariant: its keys are exactly the stages whose implemented = true (tests/test_intake.py)."""
    return {"S0": lambda: blind.format_stage(text, findings, t), "S1": lambda declaration: intake_choices.choices(declaration, t["policy"]),
            "S2": lambda declaration: intake_seal.verify(declaration, d, t),
            **intake_bytes.bodies(t, d), **intake_census.bodies(t, d), **intake_feasible.bodies(t, d), **intake_terminal.bodies(t, d)}


def _findings(root, d, ident):
    """The CC transducer check on the declaration's transducer.toml, as text lines (plumbing: it reads the toolset's git for the update pin)."""
    import schema
    import transducer
    data, bad = schema.load(d / "transducer.toml", root)
    found = {True: lambda: bad, False: lambda: transducer.chk_transducer(f"declarations/{ident}/transducer.toml", data, schema.Ctx(root), ident)}[data is None]()
    return [f"{f.loc}: {f.msg} (Next: {f.nxt})" for f in found]


def _go(root, ident, pick):
    t, d = tables(root), Path(root) / "declarations" / ident
    text = {True: lambda: (d / "intake.toml").read_text(), False: lambda: ""}[(d / "intake.toml").is_file()]()
    return t, d, fold(pick(t), bodies(t, d, text, _findings(root, d, ident)))


def _before(root, ident):
    """(tables, declaration dir, fold, refused) of the stages before data (lint and seal), each execution printed."""
    t, d, out = _go(root, ident, before_data)
    print("\n".join(f"{k} {e.text(t)}" for k, e in out.items()))
    return t, d, out, any(e.mark is Mark.REFUSED for e in out.values())


def lint(root, ident, args):
    return {True: 1, False: 0}[_before(root, ident)[3]]


def _mint(root, ident, args, t, d, out):
    who = {"author": blind.flag(args, "--author", ""), "author_kind": intake_seal.AUTHOR_KIND[blind.flag(args, "--as", "")], "confirmed_by": blind.flag(args, "--confirmed-by", "")}
    res = intake_seal.mint(out["S0"].result.evidence, d, blind.flag(args, "--universe", ""), who, root, t)
    print(f"seal {ident}: " + res.text(t["sentences"]))
    return {Mark.PASSED: 0, Mark.REFUSED: 1}[res.mark]


def seal(root, ident, args):
    usage = [u for ok, u in ((blind.flag(args, "--author", "") != "", "--author NAME"), (blind.flag(args, "--as", "") in intake_seal.AUTHOR_KIND, "--as human|ai-draft"),
                             ((blind.flag(args, "--confirmed-by", "") != "") != ("--unconfirmed" in args), "exactly one of --confirmed-by NAME | --unconfirmed")) if not ok]
    return {True: lambda: _usage(f"seal needs {'; '.join(usage)}"), False: lambda: _seal(root, ident, args)}[len(usage) > 0]()


def _seal(root, ident, args):
    t, d, out, refused = _before(root, ident)
    return {True: lambda: 1, False: lambda: _mint(root, ident, args, t, d, out)}[refused]()


def run(root, ident, args):
    t, d, out = _go(root, ident, lambda t: t["stages"]["stage"])
    text = intake_say.report(t, ident, out, intake_seal.ordering(d, t))
    (d / "intake-report.md").write_text(text)
    intake_terminal.write(root, t, d, out, verdicts(t, out)[0].kind.name)   # RESULT.json when S10 passed, else removed
    print(text, end="")
    return {Primary.PRIMARY_READY: 0, Primary.PRIMARY_INCOMPLETE: 0, Primary.PRIMARY_REFUSED_AT: 1}[verdicts(t, out)[0].kind]


def _usage(why):
    print(f"bin/cc intake: {why}\n  usage: bin/cc intake explain | synth <id> --seed N [--curves K] [--out DIR] | lint <id> | seal <id> --universe DIR --author NAME --as human|ai-draft "
          "(--confirmed-by NAME | --unconfirmed) | run <id> | convert <id> [--verify] | peek <id> <file> [--sheet NAME] [--depth N]\n  Next: bin/cc intake explain")
    return 1


def _with_id(f):
    """A subcommand that names a declaration: it runs only when declarations/<id>/ is a directory."""
    return lambda root, a: {True: lambda: f(root, a[0], a[1:]),
                            False: lambda: _usage("name a declaration: declarations/<id>/ must be a directory")}[len(a) > 0 and (Path(root) / "declarations" / a[0]).is_dir()]()


def synth(root, args):
    """bin/cc intake synth: the planted bank generator (cc/intake_synth.py, test infrastructure), imported here only: no stage imports it."""
    import intake_synth
    return intake_synth.cli(root, args)


def _handoff(pick):
    """bin/cc intake convert | peek: the conversion before the intake (cc/intake_convert.py, role intake_handoff), imported when asked for."""
    def go(root, ident, a):
        import intake_convert
        return pick(intake_convert)(root, ident, a, tables(root))
    return _with_id(go)


INTAKE = {"explain": lambda root, a: print(intake_say.explain(tables(root)), end="") or 0, "lint": _with_id(lint), "seal": _with_id(seal), "run": _with_id(run),
          "synth": synth, "convert": _handoff(lambda m: m.convert_cli), "peek": _handoff(lambda m: m.peek_cli)}


def cli(root, args):
    """bin/cc intake <sub>: a total lookup over the subcommands of INTAKE; any other word is a usage refusal."""
    sub = {True: lambda: args[0], False: lambda: ""}[len(args) > 0]()
    return blind.look(INTAKE, sub, lambda root, a: _usage(f"unknown subcommand '{sub}'"))(root, args[1:])
