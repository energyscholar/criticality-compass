# SCHEMA-1533 — the needle's report, schema 2 (`compass-report/2`)

Frozen by plan 1533 (stage 2 of the roadmap). A needle's report is a **stream of typed records**, one JSON object per
line, each line written and flushed when it is known. Later stages add record *content* through new schema files; they
never change a key, a token or a table that is frozen here.

Schema 1 is the one-line report of SCHEMA-1525. It is not changed, and it is still read (section 9).

## 1. The stream

```
start                      exactly one, first
step  step  ...  step      zero or more, in order, numbered from 1
outcome                    exactly one, last
```

- **Append-only.** A record is never rewritten. Every prefix that ends on a line end is a readable stream; while it
  has no `outcome` record its outcome is *pending*. A text whose last line has no line end is not readable.
- **Live.** The `start` record is on stdout before the first `measure` is answered. Step *r* is on stdout before
  `measure` *r+1* is sent. The outcome follows the last step.
- A refusal to start (exit 2) writes nothing on stdout. An unreachable wire (exit 1) writes nothing on stdout.

## 2. The alphabet

Every token of this schema is in this table **once**. Tokens are compared exactly; no two tokens differ only in case.
A later schema file may add tokens. It may not reuse one of these, and it may not reuse a token that a shipped schema
uses with another meaning (section 10 lists the ones this schema avoided).

<!-- alphabet:begin -->
| token | family | meaning |
|---|---|---|
| `SIG-` | reading | the interval `[d - z*s, d + z*s]` lies wholly below 0 |
| `UNRES` | reading | the sign cannot be said. With no margin, as here, that is: the interval holds 0; this is exactly `abs(d) <= z*s`, the near-zero rule of `narrow` |
| `SIG+` | reading | that interval lies wholly above 0 |
| `n/e` | reading | the reading never arrived (the wire's reply was not evaluated) |
| `narrow` | step kind | both ends are resolved and the crossing lies between them |
| `lean-lo` | step kind | the low end is resolved and says the crossing lies below it |
| `lean-hi` | step kind | the high end is resolved and says the crossing lies above it |
| `unresolved` | step kind | the two ends do not decide: an end is `UNRES`, or the ends contradict the declared order |
| `not-evaluated` | step kind | the step has no reading; it is the last step of its stream |
| `Located` | outcome kind | every step was `narrow`; the outcome carries a bracket (the schema-1 meaning, unchanged) |
| `PAST-LO` | outcome kind | every step was `lean-lo`: the searched range lies above the crossing |
| `PAST-HI` | outcome kind | every step was `lean-hi`: the searched range lies below the crossing |
| `UNDECIDED` | outcome kind | the steps did not all say the same resolved thing |
| `REFUSE` | outcome kind | the needle declined to conclude (the schema-1 meaning, unchanged) |
| `floor` | refuse reason | no step was taken: `n_eq < k * tau` (unchanged) |
| `budget` | refuse reason | a step was not evaluated (unchanged) |
| `bracketing` | phase | a step that asks for one grid of moments over the current bracket and narrows it |
| `OFF` | mode | the client holds no `nudge` op: it cannot apply a hold correction. It may place the knob |
| `ON` | mode | the client holds the `nudge` op |
| `declare` | wire op | SCHEMA-1525 |
| `measure` | wire op | SCHEMA-1525: place the knob on a grid and return moments |
| `nudge` | wire op | reserved for stage 5a: move a held dial by signed whole ticks. No wire serves it yet |
| `unknown` | belief | the slot was not declared to the needle |
| `g` | sigma | the unit of the offset: the declared granularity of the dial it is measured on |
| `not-defined` | sigma | no measured definition of the offset is frozen by this schema |
| `HIT` | score cell | exactly SCHEMA-1525's: Located, the bracket contains K_c, and it is narrow enough. Nothing else scores `HIT` |
| `LEAN-TRUE` | score cell | the outcome is `PAST-LO` or `PAST-HI` and the crossing really is past that end of the searched range (owner ruling OQ-E) |
| `LEAN-FALSE` | score cell | the outcome is `PAST-LO` or `PAST-HI` and the crossing is not past that end |
| `MISS` | score cell | exactly SCHEMA-1525's: Located, and the bracket does not contain K_c or is not narrow enough. Nothing else scores `MISS` |
| `NO-CALL` | score cell | the outcome kind was `UNDECIDED`: the needle made no claim to score |
| `REFUSED` | score cell | SCHEMA-1525: the outcome kind was `REFUSE` |
| `below-range` | truth side | the true crossing is below the low end of the searched range |
| `inside` | truth side | the true crossing is inside the searched range, ends included |
| `above-range` | truth side | the true crossing is above the high end of the searched range |
| `+K` | ordered side | the ordered phase is at high K: `d` rises through 0 as K rises |
| `-K` | ordered side | the ordered phase is at low K: `d` falls through 0 as K rises |
<!-- alphabet:end -->

The three resolved reading classes are the sign cells of `cc/sign.py` at `eps = 0` (the same names, the same
meaning), declared again here because the needle's import allowlist excludes `cc`. They are not a second sign alphabet.

`d` is the level-1 minus level-0 block correlation `D = Gs[1] - Gs[0]` at a grid point, and `s` is
`sqrt(Gs_err[1]**2 + Gs_err[0]**2)`, the same expression `narrow` uses.

## 3. The `start` record

```json
{"rec": "start", "schema": "compass-report/2", "needle": "recover-adaptive-v1",
 "settings": {"bracket": [0.2, 0.5], "m": 9, "N": 5, "n_eq": 450, "S": 2000, "skip": 1, "z": 2.0,
              "detectors": [{"name": "A", "role": "peak", "reads": "C"}, {"name": "B", "role": "crossing", "reads": "Gs"}]},
 "mode": {"ops": ["declare", "measure"], "feedback": "OFF"},
 "sigma": {"offset": 0, "unit": "g", "measured": "not-defined"},
 "dials": [],
 "belief": {"knobs_K": {"declared": [0.2, 0.5]}, "ordered_side": {"declared": "+K"}, "L": {"declared": 81},
            "tau": {"declared": 67.0}, "k": {"declared": 6}, "index_unit": {"declared": "sweep"},
            "index_kind": {"declared": "sample_counter"}, "observable": {"declared": "moments"}, "nlev": {"declared": 2},
            "system": "unknown", "roles": "unknown"},
 "declared_other": {}}
```

Exactly these nine keys, in this order.

**settings** — the needle's own configuration, the values it was started with. Exactly the eight keys shown. The key set of `settings` belongs to the needle named in `needle`: these eight are
`recover-adaptive-v1`'s. Another needle declares its own in its own schema file (section 11).

**mode** — `ops` is the list of wire ops this client holds (it can send no other). `feedback` is a function of `ops`
and nothing else: `ON` if `nudge` is among them, `OFF` otherwise. **OFF may scan** (owner ruling Q1, 2026-11-15): OFF
forbids hold corrections, not the declared ignition scan. The stage-3a needle holds `declare` and `measure`; its mode
is `OFF`. Mode is not a setting: there is no key that sets it, so a needle cannot claim a mode its ops do not give it.
A reader holds `feedback` to `ops`. A wire reading at the current position without moving (a `read` op, for a stage-5a
wire) is not frozen here; when a wire serves it, its schema file adds the token.

**sigma** — the operating point as an **unsigned safe-side offset, a whole number of units of `g`**, the granularity of
the dial the offset is measured on. `offset` is an int `>= 0`. There is no floor that depends on a jackknife error and
no fluctuation ratio. `measured` is `not-defined`: this schema freezes no measured definition of the offset; stage 5a
may define one in its own schema file under a new token. The stage-3a needle runs at offset 0. It is not configurable:
`recover2.toml` has no sigma key, and the strict parser refuses one.

**dials** — the names of the dials this needle holds, that is, the dials a hold step may judge and move: none, one
named dial, or more (owner ruling Q2: 0, 1 or 2 dials). A list of distinct names. A verdict's `dial` is null or one of
them. The stage-3a needle brackets along the knob and holds nothing: `[]`. Like the mode, it is what the needle is, not
a key of its config file.

**belief** — the declaration **as received**. One key per slot, always all eleven:
`knobs_K, ordered_side, L, tau, k, index_unit, index_kind, observable, nlev, system, roles`.
A slot's value is `{"declared": <the declared value, verbatim>}` or the bare token `unknown`. Nothing is filled in,
inferred or defaulted. A declared value that happens to be the string `"unknown"` is `{"declared": "unknown"}`, which
is a different value from the token. The stage-3a wire declares the first nine slots; `system` and `roles` are
`unknown` on that wire.

**declared_other** — every key of the `declared` reply that is not a slot, verbatim, except `op` (the reply's
envelope). `{}` on the stage-3a wire.

## 4. The `step` record

```json
{"rec": "step", "step": 1, "phase": "bracketing", "index": 164700, "evaluated": true,
 "verdict": [{"kind": "narrow", "reason": "SIG-|SIG+", "dial": null, "ticks": null}],
 "scan": {"round": 1, "grid": [], "C": [], "C_err": [], "Gs": [], "Gs_err": [], "D": [], "A": [], "B": [],
          "lo": 0.3125, "hi": 0.3875, "index": 164700, "evaluated": true}}
```

Exactly these seven keys: six that every phase has (`rec, step, phase, index, evaluated, verdict`) and one payload
key that the phase names. Phase `bracketing` names `scan`. `step`, `index` and `evaluated` repeat `scan.round`, `scan.index` and `scan.evaluated`.

**scan** is the 13-key ROUND object of SCHEMA-1525, unchanged, with the same numbers `recover-adaptive-v0` reports.
Step *r+1* scans the bracket step *r* left: `scan.grid[0] == lo` and `scan.grid[-1] == hi` of the step before, and the
first grid's ends are `settings.bracket`.

**verdict** is the frozen envelope: a list of objects with exactly the keys `kind, reason, dial, ticks`. One entry per
dial the step judges. A `bracketing` step judges no dial and holds no dial: it has exactly one entry, with `dial` and
`ticks` null. A later phase (the hold of stage 5a) writes one entry per dial, names the dial, and gives signed whole
ticks; its kinds and its table belong to its own schema file. That table must give "the crossing is resolved here" and
"cannot tell" two different cells, and must give a reading that never arrived its own cell, as this one does.

### The step table (phase `bracketing`)

The reading class of an end is the position of the interval `[d - z*s, d + z*s]` against the single cut point 0
(section 2). The table is keyed on the classes at the two ends of the grid, low end first, for `ordered_side = +K`:

| low end | high end | kind | why |
|---|---|---|---|
| `SIG-` | `SIG+` | `narrow` | above the low end and below the high end |
| `SIG-` | `SIG-` | `lean-hi` | above the high end |
| `UNRES` | `SIG-` | `lean-hi` | above the high end; the low end says nothing |
| `SIG+` | `SIG+` | `lean-lo` | below the low end |
| `SIG+` | `UNRES` | `lean-lo` | below the low end; the high end says nothing |
| `SIG-` | `UNRES` | `unresolved` | above the low end; no upper end |
| `UNRES` | `SIG+` | `unresolved` | below the high end; no lower end |
| `UNRES` | `UNRES` | `unresolved` | neither end says anything |
| `SIG+` | `SIG-` | `unresolved` | the ends contradict the declared order |

For `ordered_side = -K` the two classes are negated (`SIG-` and `SIG+` swap) and the same table is read. An
`ordered_side` that is neither has no cell: the needle refuses to start (`field=ordered_side parse=A`).

A step with no reading has the kind `not-evaluated` and the reason `n/e`. It is its own cell, not a row of the table.

`reason` names the cell exactly: `"<low class>|<high class>"` as read (before any negation), or `n/e`.

The table is total: 9 cells for each ordered side, plus the one cell for no reading. There is no fallback row.

The table reads the crossing detector only. The peak detector still narrows the bracket (its hull is in `scan.A`), but
it does not vote on the kind: recon measured that after the first step its hull covers most of the grid.

## 5. The `outcome` record

```json
{"rec": "outcome", "kind": "Located", "reason": null, "bracket": [0.329, 0.3327], "A_hull": [0.329, 0.3327],
 "B_hull": [0.3308, 0.3318], "agree": true, "steps": 5}
```

Exactly these eight keys. `steps` is the number of step records.

The outcome is a **fold of the set of step kinds**, and nothing else:

| the set of step kinds | kind | reason |
|---|---|---|
| empty (no step) | `REFUSE` | `floor` |
| holds `not-evaluated` | `REFUSE` | `budget` |
| `{narrow}` | `Located` | null |
| `{lean-lo}` | `PAST-LO` | `lean-lo` |
| `{lean-hi}` | `PAST-HI` | `lean-hi` |
| anything else | `UNDECIDED` | the kinds that were said, in alphabet order, joined by `+` (for example `narrow+lean-hi`) |

The table is total over the sets of this schema's five step kinds. "Anything else" is a declared row, not a default:
it is every set of two or more kinds without `not-evaluated`, and `{unresolved}`. A phase added later brings its own
kinds and its own fold rows (section 11); this fold is the fold of `bracketing` steps.

`bracket`, `A_hull`, `B_hull` and `agree` are those of schema 1 when the kind is `Located`, and null for every other
kind: a needle that did not bracket the crossing does not publish a bracket.

`PAST-LO` and `PAST-HI` say on which side of the searched range the crossing lies. They do not say there is none: the
worlds of this stage cannot show absence, so no token here means "absent" (stage 3 owns that).

## 6. The needle `recover-adaptive-v1`

`python -m navigator.recover2 --needle recover2.toml --port P`. Settings: the eight keys of `recover-adaptive-v0`,
`needle_structure = "recover-adaptive-v1"`. Order: parse config (B) → connect → declare (A) → `nlev` → `ordered_side`
→ bracket inside `knobs_K` → **start record** → floor → steps → **outcome record**. Exit codes as SCHEMA-1525.

Its numbers are `recover-adaptive-v0`'s: the same grid, the same `narrow`, the same floats in the same order.
`navigator/estimate.py` and `navigator/recover.py` are not edited.

### The clamp in `narrow`, and the exceptions to identity

`narrow` intersects the padded hull with the measured bracket (`max(lo0, ...)`, `min(hi0, ...)`). Schema 2 keeps that
arithmetic, because byte identity with stage 3a needs the same float expressions. What the clamp hid, that the crossing
may lie past an end, is no longer hidden: the step kind comes from the total table over the end classes, and a bracket
is published only by `Located`. The structural form of the bracket (whole ticks of a declared grid, where "outside"
has no value) is deferred to stage 5a, where a bracket is ticks.

A schema-2 run equals the schema-1 run of the same world and seed in every reported number, with exactly two
exceptions:

1. **A step that is not evaluated is terminal.** v1 sends no further `measure`; v0 sent all N. The v1 steps equal
   v0's first rounds up to and including the first unevaluated one. The outcome is `REFUSE`/`budget` in both.
2. **A run that is not `Located` carries no bracket.** Every evaluated step's `scan` equals v0's round. v0 reported
   `Located` with a bracket; v1 reports `PAST-LO`, `PAST-HI` or `UNDECIDED` with `bracket`, `A_hull`, `B_hull` and
   `agree` null.

For a run whose steps are all `narrow` there is no exception: the fold (section 9) equals v0's report exactly.

## 7. The orchestrator `environment.run_blind2`

`python -m environment.run_blind2 --env E.toml --at at-blind.toml --needle recover2.toml --score score-1533.toml`

The needle's stdout is written straight to `<run_dir>/report.jsonl`, line by line as the needle writes it. After the
needle exits the orchestrator reads it with `needlestream.read`, scores it against `<run_dir>/edge.json`, and writes:

- `score.json` — `truth_K_c, a, w_max, contains, width, narrow_enough, cell, run_id, plan, searched, truth_side`;
- `verdict.json` — the schema-1 shape: the seven keys of the fold (section 9) plus the first nine keys of `score.json`.

`plan` is a **declared field of the score file** (`a`, `w_max`, `plan`; strict). It is not a literal in the
orchestrator. `environment/run_blind.py` and its literal are not edited; runs made by it keep their stamp.

A stream that is unreadable, or has no outcome, is refused (`field=needle_stdout parse=B`), as in SCHEMA-1525.

## 8. The score table

`searched` is `settings.bracket`. `truth_side` is the position of the true K_c against its two ends: `below-range` if
`K_c < searched[0]`, `above-range` if `K_c > searched[1]`, `inside` otherwise.

| outcome kind | cell |
|---|---|
| `Located` | the SCHEMA-1525 cell: `HIT` iff the bracket holds K_c within `a` and its width is `<= w_max`, else `MISS` |
| `PAST-LO` | `LEAN-TRUE` iff `truth_side` is `below-range`, else `LEAN-FALSE` |
| `PAST-HI` | `LEAN-TRUE` iff `truth_side` is `above-range`, else `LEAN-FALSE` |
| `UNDECIDED` | `NO-CALL` |
| `REFUSE` | `REFUSED` |

`contains`, `width` and `narrow_enough` are those of SCHEMA-1525 for `Located` and null otherwise. Total: an outcome
kind outside the alphabet has no cell. Each cell has one meaning: `HIT` and `MISS` are the two cells of a `Located`
outcome and of nothing else (owner ruling OQ-E, applied to both).

## 9. Reading both schemas: `needlestream.read`

`read(text) -> Stream | Unreadable`. It never raises and opens nothing.

- A text that is one JSON object with no `rec` key is a **schema-1** report. It is validated by the only schema-1
  reader, `needleview.report.parse`, and lifted: `Stream.schema == 1`, its start is `NOT_REPORTED`, every step's
  verdict is `NOT_REPORTED`. Scored (16-key) and bare (7-key) reports are both read.
- Anything else is read as a **schema-2** stream and held to every rule of sections 1 to 5: exact keys, the order,
  the numbering, the continuity of the grids, the 13 round keys (checked by the schema-1 reader), each verdict equal
  to the step table's verdict for that step's own numbers, the outcome equal to the fold, the belief shape, `feedback`
  equal to the mode of `ops`, the sigma types, the dials. A stream that fails any of them is `Unreadable`: a viewer never draws a
  verdict the needle's own table does not give.

`fold_v1(stream)` gives the seven schema-1 keys (`kind, reason, bracket, A_hull, B_hull, agree, rounds`, with `rounds`
= the steps' `scan` objects), or `PENDING` while the stream has no outcome.

**What keeps working.** `verdict.json` is still written, in the schema-1 shape. The viewer of plan 1529 and the player
of plan 1531 read a `Located` or `REFUSE` run unchanged. Given any other kind they refuse the file by name
(`kind 'PAST-HI' is not read by this viewer`); they never draw it as something else. Their files are not edited.

## 10. One stream with plan 1531, and where the two differ

The needle's stream is the one shape. The event stream of SCHEMA-1531 is the same three records with a viewer's
labels around them:

| this schema | SCHEMA-1531 | the shared payload |
|---|---|---|
| `start` | `{"ev": "run", ...}` | none in schema 1; the `start` record fills the player's `belief` slot |
| `step` | `{"ev": "round", "nav": ...}` | `nav` is `step.scan`, key for key; `step.verdict` fills the player's `verdict` slot |
| `outcome` | `{"ev": "outcome", "nav": ...}` | `nav` is the outcome's six keys `kind, reason, bracket, A_hull, B_hull, agree` |

They differ in exactly this:

1. the discriminator key is `rec` here and `ev` there, and the names are `start`/`step` here, `run`/`round` there;
2. `run`, `world`, `label`, `system` and `score` are assigned by the viewer or the orchestrator; a needle does not
   know them, so they are not in its stream;
3. SCHEMA-1531's `unreadable` event has no record here: unreadable is a value of the reader, not something a needle says;
4. the outcome record has `steps`; the 1531 event has none.
 5. a step has `phase`; a 1531 `round` event has none (every schema-1 round is a `bracketing` step);
6. `system` is a belief slot here (what the wire declared about itself); in SCHEMA-1531 it is the viewer's truth key.
   They are different things and neither is copied into the other;
7. an unfinished stream is a value of the reader here (`outcome is PENDING`); 1531 has no record for it either.

No test of this plan pins this mapping: SCHEMA-1531 is not in this tree (plan 1531 is unmerged and unaccepted). The
contract of plan 1b pins it, against whatever 1531 is when it merges.

Both are append-only and per-run. A player that shows the stage-2 slots reads `report.jsonl` through
`needlestream.read` and is a **new sibling package** with its own pinned files (plan 1b). `needleview/` and
`needleview/player/` read schema 1 and are never edited; where they print `not reported (stage 2)` they keep
printing it.

Names this schema avoided, because a shipped schema uses them with another meaning: `ABSENT`, `LINE` (plan 1511
verdict kinds), `edge` and `Edge` (the truth file and its type), `EDGE lo` / `EDGE hi` and `absent` (working names in
the roadmap, replaced by `PAST-LO`, `PAST-HI` and `UNDECIDED`).

## 11. What a later stage may and may not do

**Frozen here, for every later stage:** the three record types and their order; the six common step keys; the
verdict envelope `{kind, reason, dial, ticks}`; the `start` keys; the outcome keys; every token of section 2 with its
meaning; the `bracketing` step table and its fold; the score table.

**Not frozen, because it belongs to a needle or a phase that does not exist yet:** the payload of a step in another
phase, and the settings of another needle.

May, each in a new schema file with new tokens only: add a phase, with its payload key, its step table, its step kinds
and their fold rows; add a needle, with its settings keys; add outcome kinds, belief slots, a `sigma.measured` token,
wire ops, further sign cells of `cc/sign.py` for a reading with a margin.

**How a later stage reads.** `needlestream.read` of this stage refuses, by name, a phase, a needle setting or a token
it does not know, as the schema-1 reader refuses a kind it does not know. A later stage ships its reader as a new
module beside `needlestream/read.py`, built on it; `read.py` and this stage's tests are never edited. The schema
string stays `compass-report/2`: it names the frozen part.

May not: change the keys of the three records or of the verdict envelope; change a token's meaning; change a cell of
the step table, the fold or the score table; make `feedback` anything but a function of `ops`; fill a belief slot the
wire did not declare.
