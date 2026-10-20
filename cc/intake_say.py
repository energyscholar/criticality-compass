"""intake_say - the text of the intake: `bin/cc intake explain` (docs/INTAKE.md) and intake-report.md.
Invariant: every sentence comes from intake/STAGES.toml (the tables), and the output is a pure function of (tables, fold); it imports only
intake_blind and intake_fold, constructs no Path and opens nothing."""
import intake_blind as blind
from intake_blind import Mark
from intake_fold import Scope, scoped, verdicts


def state(s):
    return {True: "LIVE", False: "STUB"}[s["implemented"]]


LIVE = {True: "live", False: "NOT LIVE"}


def not_live(t):
    """The reason rows no body can return yet (live = false in intake/STAGES.toml), as a Markdown section that explain and every
    report carry: a refusal named there cannot be seen today, so its absence from a report says nothing."""
    rows = [f"- {s['id']} {r['code']}" for s in t["stages"]["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, []) if not r["live"]]
    return t["stages"]["report"]["not_live"] + (rows or [t["stages"]["report"]["all_live"]]) + [""]


def unseen(t):
    """The tail of explain and of every report: the reason rows no body can return yet, then what no stage can see."""
    return not_live(t) + ["## What no stage can see", ""] + [f"- {u}" for u in t["stages"]["report"]["unenforced"]]


def explain(t):
    """The stage table as Markdown: `bin/cc intake explain` prints it and docs/INTAKE.md is it, byte for byte (docs/gen-intake.py)."""
    st, po = t["stages"], t["policy"]
    out = [f"# The intake pipeline (stage table {st['version']}, policy {po['version']})", "",
           *st["report"]["explain"],
           f"**The seal.** {st['report']['seal_claim']}", "", "| id | name | state | reads data bytes | needs | verdict |", "|---|---|---|---|---|---|"]
    out += [f"| {s['id']} | {s['name']} | {state(s)} | {s['reads_bytes']} | {', '.join(s['needs']) or '-'} | {s['verdict']} |" for s in st["stage"]]
    for s in st["stage"]:
        out += ["", f"## {s['id']} {s['name']} ({state(s)})", "", s["purpose"], "", "| reason | live | what it means |", "|---|---|---|"]
        out += [f"| {r['code']} | {LIVE[r['live']]} | {r['sentence']} |" for r in s["reason"]]
        out += {True: lambda: ["", "| reader reason (READER_REFUSED) | live | what it means |", "|---|---|---|"] + [f"| {r['code']} | {LIVE[r['live']]} | {r['sentence']} |" for r in s["reader_reason"]],
                False: lambda: []}["reader_reason" in s]()
        out += {True: lambda: ["", "| seal status | what it means |", "|---|---|"] + [f"| {r['code']} | {r['sentence']} |" for r in s["status"]], False: lambda: []}["status" in s]()
    out += ["", f"## Policy ({po['status']}, {po['version']})", "", po["evidence_note"], ""]
    for link in ("projection", "bridge"):
        out += [f"- {link} **{k}**: " + "; ".join(f"{f} = {v}" for f, v in row.items()) for k, row in po[link].items()]
    out += [f"- policy: " + "; ".join(f"{k} = {v}" for k, v in po["policy"].items()), ""] + unseen(t)
    return "\n".join(out) + "\n"


def profiled(t, out):
    """The report's Profile line (plan 1165) from S3: PROFILED <sha256 prefix 12> (n files, m findings, 0 contradictions) | NOT PROFILED (S3 refused PROFILE_ABSENT) | not reported, with S3's text."""
    s3 = out[[s["id"] for s in t["stages"]["stage"] if s["name"] == "SOURCE_INTEGRITY"][0]]
    return {(True, False): lambda: (lambda p: f"PROFILED {p['sha256'][:12]} ({len(p['files'])} files, {len(p['findings'])} findings, 0 contradictions)")(s3.result.evidence.profile),
            (False, True): lambda: "NOT PROFILED", (False, False): lambda: "not reported: " + s3.text(t)}[(s3.mark is Mark.PASSED, s3.mark is Mark.REFUSED and s3.result.reason == "PROFILE_ABSENT")]()


def report(t, ident, out, note):
    """intake-report.md of a run: the verdicts, the seal status and the ordering note (`note`, an (Ordering, sentence) read after the run), then
    every stage in plain sentences, then the seal claim and what no stage can see."""
    seal = t["stages"]["seal_stage"]
    p, r = verdicts(t, out)
    names = {s["id"]: s["name"] for s in t["stages"]["stage"]}
    words = lambda v: ", ".join(f"{m} {blind.look(names, m, '')}".strip() for m in v.missing) or "none"
    handoff = scoped(t, Scope.HANDOFF)[0]
    lines = [f"# Intake report: {ident}", "", f"Written by `bin/cc intake run {ident}`. Stage table {t['stages']['version']}, policy {t['policy']['version']}.", "",
             f"- **Mode** (the declarer's sealed statement of what they had seen): {out['S0'].result.mode()}",
             f"- **PRIMARY verdict: {p.kind.name}**" + {True: f" at {p.at}", False: ""}[p.at != ""] + f". Missing: {words(p)}.",
             f"- **ROBUSTNESS verdict: {r.kind.name}**" + {True: f" at {r.at}", False: ""}[r.at != ""] + f". Missing: {words(r)}.",
             f"- **{handoff} {names[handoff]}** (the terminal; it counts toward PRIMARY): {out[handoff].atom.name}.",
             "- **Seal status** (advisory; sealing is recommended and not enforced): " + {True: lambda: out[seal].result.evidence.summary(),
                                                                                           False: lambda: "not reported: " + out[seal].text(t)}[out[seal].mark is Mark.PASSED](),
             f"- **Profile** (plan 1165): {profiled(t, out)}", f"- **Ordering** (information, never a refusal): {note[0].name}. {note[1]}"]
    lines += {True: [f"- **confirmation**: {t['stages']['report']['confirmation']}"], False: []}["confirmation" in p.missing]
    lines += ["",
             "| stage | name | state | reads data bytes | execution |", "|---|---|---|---|---|"]
    lines += [f"| {s['id']} | {s['name']} | {state(s)} | {s['reads_bytes']} | {out[s['id']].atom.name} |" for s in t["stages"]["stage"]]
    lines += [""] + [f"- **{s['id']} {s['name']}** ({state(s)}): {out[s['id']].text(t)}" for s in t["stages"]["stage"]]
    census = [s["id"] for s in t["stages"]["stage"] if s["name"] == "CENSUS"][0]   # the census section: only when the census passed
    lines += {True: lambda: ["", "## Census", "", f"The curves of {census} CENSUS, by ordinal and file name (never by slow value):", ""] + out[census].result.evidence.listing(),
              False: lambda: []}[out[census].mark is Mark.PASSED]()
    lines += ["", "## What the seal proves", "", t["stages"]["report"]["seal_claim"], ""] + unseen(t)
    return "\n".join(lines) + "\n"
