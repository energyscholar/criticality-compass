"""linenav.py v2.1-T (= v2.0.1 + the TERMINAL TYPES of plan 1095, built by plan 1109: every side oracle DECLARES its evidence class, `evidence = Sharp()` or `Finite(...)`; the class owns the terminal enum (SharpTerm = the v2.0.1 Term; FiniteTerm has NO END and NO LOST member and one h_min constructor CONTOUR_EDGE carrying the failing window's own reads). No default: an undeclared oracle has no `evidence` attribute and navigate raises before its first read. No READ key, PARAMS key or number is added; SHARP behaviour is v2.0.1 line for line.) v2.0.1 (= v2.0, no behaviour change: the terminal / corridor / no-acquisition if-chains are total tables checked by C6; plan 1105) v2.0 (= v1.9 + K, the followed-orientation crossing filter; plans 1081 design, 1085 exit trace, 1088 build; v1.9 = plans 1071 rule C, 1074 al, 1078 build; v1.8 = plan 1057; header below dates from v1.6, plan 1052) - plan 1038 (+ AMENDMENT 1) and plan 1040 (+ AMENDMENT 1): the LINE NAVIGATOR, hybrid. GEOMETRY over a typed, injected
side oracle. It knows nothing of physics or of any map. Continuous mode: plane units u. Grid mode: INDEX coordinates (row, col) as
floats, nodes at integers (1040 A1 G).
Declared readings of plan 1038 (ADOPTED as declarations by plan 1040):
  - checkpoint order: the polyline vertices, then the A3 subdivision points in segment order;
  - the 'last bracket' that sets pref is the last bracket read IN THE CURRENT DIRECTION (every bracket, accepted or not), starting from
    the acquisition bracket. Plan 1040 C4: until a bracket has been read in the current direction, pref = -1.
Plan 1040 A1 R3 ADOPTED: on a failure at h_min the turn search runs FIRST; only if it accepts nothing is the terminal typed (C2 rule).
Plan 1040 literal applications (each checked for result-sensitivity, studies/LINENAV/sens1040.py; key in READ_DEFAULT):
  - h_cut_persists (continuous): C2 'h is cut' - h itself takes the cut value. Grid: h stays an integer (G2 'h >= 1 is an integer');
  - edge_window: C2 'its window reached the domain boundary' = some window node q_j, |j| <= W, lies outside or ON the boundary;
  - star_trace: C3 'every located point already in the trace' = X_0 and both directions' located points so far;
  - star_closed: CLOSED is checked on an accepted star point as on any located point (an accepted star point is appended);
  - a star CROSS whose centre lies outside the domain reads no node there: A2 rule 2 (OUT) applies to j = 0 as to every q_j;
  - closed_t: R2 't_k' = the tangent of the step that produced the located point (the predictor's t_k; for a star point, d);
  - pref_perp: A2 pref is read as the sign of v . n_k with n_k = R90(t_k) (the declared normal), the search vector being oriented along
    n_k. In grid mode the search vector is an axis, and after an axis switch v . e_a = 0 exactly; the alternative reads v . e_a there.
    v . n_k = 0 (the last bracket parallel to the line) gives pref -1, as an UNRES side does (C4);
  - edge_strict (grid, G3): 'no b_next strictly between b and the exit side' = no b_next strictly beyond b; a cut landing ON the
    b-boundary is read (C2: 'b = 0 or b = n_b - 1'). The alternative also refuses a cut landing on the b-boundary itself;
  - G3 gap: when X + h t is inside the hull but the G2 node line b_next = floor(b + h) lies past the hull, the cut is applied (the same
    b_next the cut gives whenever G3 applies literally);
  - acq_j0 (grid, G6): j = 0 is round(a_pred), a_pred the suspect-tangent extrapolation of the checkpoint to the line b (G2 with h = 0);
  - G5 'minus the one with the smallest d . t_k': on a tie, the last of the declared order (d . t_k descending, + before -, rows before
    columns) is dropped. Ties are counted in the output.
Plan 1057 (v1.8, rule L'; spec research/compass-linenav-unres-band-DESIGN-DRAFT-2026-10-15.md sec 3 + REVIEW GATE): END needs, besides L's evidence run, that the run
  is NOT closed by the same supported side at both ends (same_flank). Such a window does not straddle the separator, so it carries no evidence that the field
  stops being two-sided; the direction is typed LOST. Only END -> LOST; EDGE, brackets, reads are untouched. READ['end_flank']: 'lprime' (default) | 'v17'
  (v1.7: seen-red and baseline only). RECORDED LIMIT: OPEN oblique windows (a flank is OUT or beyond the limit) are unreached; the live reader's SINGLE is
  not sole END evidence (125 SINGLE reads beside the line), recorded in plan 1046's scoring note.
Plan 1054 (v1.7, remedy Fu): the turn search's forward clause is follow's own forward test, on follow's axis t, at the located resolution of the crossing itself:
  an accepted star crossing X needs (X - X_k) . t > -unc (unc = the half-bracket the crossing reports; no new number). The v1.6 clause (X - X_k) . d > 0 held
  for every node by construction (each window sits h0 ahead along d) and could never fail. Strict > 0 is refused: 10 C7 float ties. READ['turn']: 'forward'
  (default, Fu) | 'v16' (the vacuous clause: seen-red only).
Plan 1045 (v1.2) REVISIT terminal: once a turn-search point has been ACCEPTED in a direction, every later located point of that direction
that lies within h0/2 (<=, the complement of the C3 acceptance test) of ANY earlier located point Y of the whole trace (X_0, both directions) AND whose step tangent t_X satisfies t_X . t_Y < -1/2 (Y's stored tangent, mapped
into the path's +t sense: -t-direction tangents negated; plan 1045 Amendment 1) ends the direction as REVISIT; that point is NOT appended. READ['revisit']: 'after_turn' (default, this reading), 'next' (only the first
located point after the accept), 'off' (the check deleted - seen-red only).
G1-G7 are implemented as declared; grid h in {1, 2, 4}.
Plan 1046 (v1.3) SINGLE side value (REVIEW RULING on 1044 OPEN-1 (ii)): a RESOLVED side meaning "one state here, no line". It never forms a
bracket: the resolved readings (NEG, POS, SINGLE) are listed in j order (1038 A2 rule 4) and only an adjacent NEG|POS pair is a bracket, so
SINGLE-NEG, SINGLE-POS, SINGLE-SINGLE are not, and a SINGLE between a NEG and a POS separates them. With no bracket, CLEAR keeps the A2 rule 7
outermost-resolved test with SINGLE counted as resolved (a resolved window with no bracket is CLEAR, whatever its sides); an UNRES outermost
read still makes it UNREAD. Expansion still stops on a NEG and a POS (rule 3 ii, unchanged). Bisection stops at a SINGLE midpoint, as at
UNRES. Declared reading (plan 1046 phase 0): a SINGLE carries no orientation, so pref of a SINGLE read is -1, as for UNRES (C4).
SINGLE is never OUT; the C2 END->EDGE rule is unchanged. READ['single']: 'resolved' (default), 'as_unres' (seen-red only: every SINGLE
read is replaced by UNRES).
Plan 1048 (v1.4) RUN-SUPPORTED bracket (flip robustness; spec research/compass-linenav-flip-robustness-DESIGN-DRAFT-2026-10-15.md 2(d) + REVIEW GATE):
the A2 expansion stop 'a NEG and a POS both read' and the adjacent-pair choice are replaced. The resolved reads (NEG, POS, SINGLE) in j order form
maximal RUNS of equal sides (UNRES skipped, as A2 rule 4). A run is SUPPORTED if its length >= e (PARAMS 'e' = E_SUPPORT = 2: the number of flips
tolerated plus one) or it is a BOUNDARY run: the first run when the node just below it is OUT or below -W, the last run when the node just above
it is OUT or above +W. A BRACKET is a NEG run and a POS run consecutive among the supported runs (a supported SINGLE run separates them); its pair is
the two inner ends. Expansion stops after the first READ that leaves a bracket. Among brackets (REVIEW OPEN-4) those with no boundary-only run (a
run supported by the boundary clause alone) rank first, then A2's nearest to j = 0, then pref. The pair may span several cells (an unsupported run
or an UNRES read between the runs); bisection is unchanged. Declared reading (no planted-bank effect, SINGLE is never planted): an unsupported
SINGLE run is skipped like any unsupported run. READ['bracket']: 'run' (default), 'adjacent' (the v1.3 rule: seen-red and baseline only),
'run_noboundary' (the boundary clause deleted: seen-red only).
Plan 1050 (v1.5; spec research/compass-linenav-false-end-DESIGN-DRAFT-2026-10-15.md sec 3-4 + REVIEW GATE), three changes, all type/representation:
  (1) EDGE-ONLY boundary clause (W): a run is supported by the boundary clause only when the node just beyond it was examined and found OUT.
      The window limit +-W is a declared search horizon, not evidence ("no read beyond +W" is absence of a read), so it cannot vouch for a
      one-read run. READ['bracket']: 'run' (default, OUT-only), 'run_v14' (the v1.4 clause incl. +-W: seen-red and baseline only),
      'adjacent', 'run_noboundary' unchanged.
  (2) END needs evidence (L): END claims 'the line ends here'. A NEG|POS interface cannot end inside a field that is two-sided all round it; it
      ends only where the field stops being two-sided (UNRES or SINGLE) or at the domain edge (EDGE, unchanged). In the h_min window (the
      failing FOLLOW CROSS that took h below h_min) the read at j = 0 must be UNRES or SINGLE and the maximal run of consecutive j of
      UNRES/SINGLE reads containing j = 0 must have length >= e; otherwise the direction is typed SharpTerm.LOST (CONTOUR_EDGE under a FINITE oracle) ('could not be followed
      further'). DECLARED ASSUMPTION ABOUT THE READER (REVIEW GATE): the reader never emits a false UNRES or SINGLE; flips only swap NEG/POS,
      so no flip can fabricate END evidence. READ['end']: 'evidence' (default) | 'any' (v1.4: every non-EDGE failure is END; seen-red and
      baseline only). Grid mode uses the same rule on its h_min window.
  (3) Verdict.PARTIAL_IN_CORRIDOR: a deviating checkpoint is UNREACHED iff some direction is LOST and the nearest point of the path to the
      checkpoint is that direction's final path vertex (path[-1] for +t, path[0] for -t; floating equality 1e-12). dev' = dev minus UNREACHED:
      dev empty -> FOLLOWED; dev non-empty and dev' empty -> PARTIAL_IN_CORRIDOR; dev' non-empty -> FOUND_DEVIATES. rec['unreached'] = sorted k.
Plan 1052 (v1.6; spec research/compass-linenav-if-lost-DIAGNOSIS-2026-10-15.md remedy H + its REVIEW GATE): the window LIMIT is never evidence (H, both modes).
  v1.4 read the limit +-W as evidence that a run continues; v1.5 read it as evidence that it does not; the window read neither. Under H, when the
  expansion to +-W (+-Wacq at acquisition) leaves no bracket and a terminal run is cut by the limit with length m < e, it is READ ON: nodes
  j = +-(W+1) .. +-(W+e-m), in order. Stop at: a bracket, an opposite resolved read (the run is closed and stays unsupported), or OUT (the v1.5
  OUT-only clause then applies). Runs of length >= e and windows with a bracket are untouched. No new number (e - m is the run's own deficit).
  Recorded in PARAMS as H = 'reads'. READ['limit']: 'reads' (default) | 'off' (H deleted = v1.5 behaviour: seen-red only).
  Scoring (studies/LINENAV/maps.py): a map direction with 0 located points scores UNSCORED, never pass (all([]) is True); a verdict-level HELD may not rest on it alone.
Plans 1071 + 1074 + 1078 (v1.9 = rule C + al, unconditional; spec research/compass-linenav-oblique-exit-DESIGN-DRAFT-2026-10-15.md sec 6): rule C (1071): the
candidates of a window are its pairs and its edge interfaces (OUT o, >= 1 non-supported read, the supported run's near end r), ranked by v1.8's key
(exact tie -> pair); an interface strictly nearer than the chosen pair locates nothing (UNREAD). al (1074): in a follow window centred on the step's boundary
landing (the comparison cut() makes) the interface IS the read: CROSS returns E, follow types EDGE with dirs[s]["exit"] = (q_r, B), the interval of the exit;
no point is appended, no star runs, h is not halved. No new number, no interpolation.
"""
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Optional, Tuple
import numpy as np


class Side(Enum):
    NEG = "NEG"; POS = "POS"; MID = "MID"; UNRES = "UNRES"; SINGLE = "SINGLE"


RESOLVED = (Side.NEG, Side.POS, Side.SINGLE)    # plan 1046: the resolved side values; only NEG|POS pairs


class Corr(Enum):
    CROSS = "CROSS"; CLEAR = "CLEAR"; UNREAD = "UNREAD"


class Verdict(Enum):
    FOLLOWED_IN_CORRIDOR = "FOLLOWED_IN_CORRIDOR"; FOUND_DEVIATES = "FOUND_DEVIATES"
    ABSENT_IN_CORRIDOR = "ABSENT_IN_CORRIDOR"; INDETERMINATE = "INDETERMINATE"
    PARTIAL_IN_CORRIDOR = "PARTIAL_IN_CORRIDOR"


# plan 1105 (v2.0.1): the three v2.0 if-chains as TOTAL TABLES, checked by C6 (checks.toml [tables]). Values are enum member NAMES, read by
# Enum[name]: a later change of enum (plan 1095) is a change of codomain, not of code shape. Every cell is v2.0's value (SITEMAP-1105.md).
# #43 terminal of an h_min failure, key (edge?, evidence?, same_flank?), one table per declared reading (READ end, end_flank):
TERM_LPRIME = {(1, 0, 0): "EDGE", (1, 0, 1): "EDGE", (1, 1, 0): "EDGE", (1, 1, 1): "EDGE",
               (0, 1, 0): "END", (0, 1, 1): "LOST", (0, 0, 0): "LOST", (0, 0, 1): "LOST"}
TERM_V17 = {(1, 0, 0): "EDGE", (1, 0, 1): "EDGE", (1, 1, 0): "EDGE", (1, 1, 1): "EDGE",
            (0, 1, 0): "END", (0, 1, 1): "END", (0, 0, 0): "LOST", (0, 0, 1): "LOST"}
TERM_ANY = {(1, 0, 0): "EDGE", (1, 0, 1): "EDGE", (1, 1, 0): "EDGE", (1, 1, 1): "EDGE",
            (0, 1, 0): "END", (0, 1, 1): "END", (0, 0, 0): "END", (0, 0, 1): "END"}
TERM_READING = {("evidence", "lprime"): "TERM_LPRIME", ("evidence", "v17"): "TERM_V17",
                ("any", "lprime"): "TERM_ANY", ("any", "v17"): "TERM_ANY"}
TERM_TABLES = {"TERM_LPRIME": TERM_LPRIME, "TERM_V17": TERM_V17, "TERM_ANY": TERM_ANY}
# plan 1109 (spec 1095): the FINITE class's #43 table, same key. EDGE first (the edge = 1 rows); every other failed h_min is CONTOUR_EDGE: a FINITE oracle
# can never claim the line ends, so no cell names END or LOST. The evidence / same_flank bits only choose the band label of the payload.
TERM_FINITE = {(1, 0, 0): "EDGE", (1, 0, 1): "EDGE", (1, 1, 0): "EDGE", (1, 1, 1): "EDGE",
               (0, 1, 0): "CONTOUR_EDGE", (0, 1, 1): "CONTOUR_EDGE", (0, 0, 0): "CONTOUR_EDGE", (0, 0, 1): "CONTOUR_EDGE"}
# #18 a window with no pair, key (outermost read on +j, outermost read on -j, the K filter removed a pair?); OUT = the side has no read
CORR_NOPAIR = {
    ("NEG", "NEG", 0): "CLEAR", ("NEG", "POS", 0): "CLEAR", ("NEG", "SINGLE", 0): "CLEAR", ("NEG", "UNRES", 0): "UNREAD", ("NEG", "MID", 0): "UNREAD", ("NEG", "OUT", 0): "UNREAD",
    ("POS", "NEG", 0): "CLEAR", ("POS", "POS", 0): "CLEAR", ("POS", "SINGLE", 0): "CLEAR", ("POS", "UNRES", 0): "UNREAD", ("POS", "MID", 0): "UNREAD", ("POS", "OUT", 0): "UNREAD",
    ("SINGLE", "NEG", 0): "CLEAR", ("SINGLE", "POS", 0): "CLEAR", ("SINGLE", "SINGLE", 0): "CLEAR", ("SINGLE", "UNRES", 0): "UNREAD", ("SINGLE", "MID", 0): "UNREAD", ("SINGLE", "OUT", 0): "UNREAD",
    ("UNRES", "NEG", 0): "UNREAD", ("UNRES", "POS", 0): "UNREAD", ("UNRES", "SINGLE", 0): "UNREAD", ("UNRES", "UNRES", 0): "UNREAD", ("UNRES", "MID", 0): "UNREAD", ("UNRES", "OUT", 0): "UNREAD",
    ("MID", "NEG", 0): "UNREAD", ("MID", "POS", 0): "UNREAD", ("MID", "SINGLE", 0): "UNREAD", ("MID", "UNRES", 0): "UNREAD", ("MID", "MID", 0): "UNREAD", ("MID", "OUT", 0): "UNREAD",
    ("OUT", "NEG", 0): "UNREAD", ("OUT", "POS", 0): "UNREAD", ("OUT", "SINGLE", 0): "UNREAD", ("OUT", "UNRES", 0): "UNREAD", ("OUT", "MID", 0): "UNREAD", ("OUT", "OUT", 0): "UNREAD",
    ("NEG", "NEG", 1): "UNREAD", ("NEG", "POS", 1): "UNREAD", ("NEG", "SINGLE", 1): "UNREAD", ("NEG", "UNRES", 1): "UNREAD", ("NEG", "MID", 1): "UNREAD", ("NEG", "OUT", 1): "UNREAD",
    ("POS", "NEG", 1): "UNREAD", ("POS", "POS", 1): "UNREAD", ("POS", "SINGLE", 1): "UNREAD", ("POS", "UNRES", 1): "UNREAD", ("POS", "MID", 1): "UNREAD", ("POS", "OUT", 1): "UNREAD",
    ("SINGLE", "NEG", 1): "UNREAD", ("SINGLE", "POS", 1): "UNREAD", ("SINGLE", "SINGLE", 1): "UNREAD", ("SINGLE", "UNRES", 1): "UNREAD", ("SINGLE", "MID", 1): "UNREAD", ("SINGLE", "OUT", 1): "UNREAD",
    ("UNRES", "NEG", 1): "UNREAD", ("UNRES", "POS", 1): "UNREAD", ("UNRES", "SINGLE", 1): "UNREAD", ("UNRES", "UNRES", 1): "UNREAD", ("UNRES", "MID", 1): "UNREAD", ("UNRES", "OUT", 1): "UNREAD",
    ("MID", "NEG", 1): "UNREAD", ("MID", "POS", 1): "UNREAD", ("MID", "SINGLE", 1): "UNREAD", ("MID", "UNRES", 1): "UNREAD", ("MID", "MID", 1): "UNREAD", ("MID", "OUT", 1): "UNREAD",
    ("OUT", "NEG", 1): "UNREAD", ("OUT", "POS", 1): "UNREAD", ("OUT", "SINGLE", 1): "UNREAD", ("OUT", "UNRES", 1): "UNREAD", ("OUT", "MID", 1): "UNREAD", ("OUT", "OUT", 1): "UNREAD"}
# #47 no acquisition, key (CROSS occurs in corr?, CLEAR occurs?, UNREAD occurs?): ABSENT iff only CLEAR occurs (all() over corr)
VERDICT_NOACQ = {(0, 0, 0): "ABSENT_IN_CORRIDOR", (0, 1, 0): "ABSENT_IN_CORRIDOR", (0, 0, 1): "INDETERMINATE", (0, 1, 1): "INDETERMINATE",
                 (1, 0, 0): "INDETERMINATE", (1, 1, 0): "INDETERMINATE", (1, 0, 1): "INDETERMINATE", (1, 1, 1): "INDETERMINATE"}


def outer_read(reads, sd):
    """plan 1105: the value of the read at the largest |j| on side sd; the slot |j| = 0 (never on a side) holds 'OUT' and is the outermost only
    when side sd has no read (SITEMAP-1105.md 2.2: then its first node was OUT)."""
    m = {0: "OUT", **{abs(j): s.value for j, s in reads.items() if j * sd > 0}}
    return m[max(m)]


# plan 1109 (spec 1095 sec 1): the terminal types. An oracle's `evidence` attribute is its declared class; the class owns its terminal enum.
class SharpTerm(Enum):
    """the terminals of an oracle whose line has a true end by construction (v2.0.1's Term, member for member)."""
    EDGE = "EDGE"; END = "END"; CLOSED = "CLOSED"; BUDGET = "BUDGET"; REVISIT = "REVISIT"; LOST = "LOST"


class FiniteTerm(Enum):
    """the terminals of a finite-size reader: no END member and no LOST member; the h_min failure has exactly one constructor, CONTOUR_EDGE."""
    EDGE = "EDGE"; CLOSED = "CLOSED"; BUDGET = "BUDGET"; REVISIT = "REVISIT"; CONTOUR_EDGE = "CONTOUR_EDGE"


class Band(Enum):
    """which rule L / L' outcome the failing window shows. A label, never a terminal."""
    RUN = "RUN"; NO_RUN = "NO_RUN"


class Strand(Enum):
    """a reader's code as a statement about the two starts at one read."""
    TWO = "TWO"; ONE = "ONE"; UNDECIDED = "UNDECIDED"


@dataclass(frozen=True)
class ReadAt:
    j: int                      # node index along the window normal (node = centre + j * ht * n)
    u: Tuple[float, ...]        # the node, in the plane's units
    side: str


@dataclass(frozen=True)
class WindowRead(ReadAt):
    K: float
    h: float
    D: str
    S: str
    key: Tuple[int, int]        # the oracle's cache key
    rc: int                     # read-count slot of the seed stream
    source: str                 # cache file


@dataclass(frozen=True)
class SideEdge:
    """one side of the window (sd = sign of j). lo = the TWO read with the largest |j| below hi (j = 0 included); hi = the first ONE read walking
    out from j = 0 (None: none seen); undecided = the UNDECIDED reads below hi (all, when hi is None); fail = the first |j| >= 1 whose side is not NEG/POS."""
    sd: int
    lo: Optional[WindowRead]
    hi: Optional[WindowRead]
    undecided: Tuple[WindowRead, ...]
    fail: Optional[WindowRead]


@dataclass(frozen=True)
class ContourEdge:
    """FiniteTerm.CONTOUR_EDGE with its payload: the failing h_min window's own reads, nothing estimated between them. fail_at / last_at are the
    window centre and the last located point in the oracle's own coordinates. h0 and sides are None for a reader with no strand alphabet (FiniteStored)."""
    fail_at: Tuple[float, ...]
    last_at: Tuple[float, ...]
    band: Band
    h0: Optional[WindowRead]
    sides: Optional[Tuple[SideEdge, SideEdge]]
    resolution: Tuple[Tuple[str, object], ...]
    reads: Tuple[ReadAt, ...]


def side_edge(reads, sd, strand):
    by = {r.j: r for r in reads}
    out = [by[j] for j in sorted(by, key=abs) if j * sd >= 0]               # j = 0 first, then outward on side sd
    ones = [r for r in out if strand[r.D] is Strand.ONE]
    hi = ones[0] if ones else None
    below = [r for r in out if hi is None or abs(r.j) < abs(hi.j)]
    twos = [r for r in below if strand[r.D] is Strand.TWO]
    fails = [r for r in out if r.j != 0 and Side(r.side) not in (Side.NEG, Side.POS)]
    return SideEdge(sd=sd, lo=twos[-1] if twos else None, hi=hi, undecided=tuple(r for r in below if strand[r.D] is Strand.UNDECIDED),
                    fail=fails[0] if fails else None)


@dataclass(frozen=True)
class Sharp:
    """an oracle whose line has a true end by construction (the planted banks). Rules L and L' type END or LOST: the v2.0.1 tables."""
    terminals: ClassVar[type] = SharpTerm
    unreached: ClassVar[frozenset] = frozenset({SharpTerm.LOST})

    def table(self, read):
        return TERM_TABLES[TERM_READING[(read["end"], read["end_flank"])]]

    def end_bracket(self, term, x, hmin, t):
        return (x.copy(), x + hmin * t) if term is SharpTerm.END else None

    def contour(self, term, band_run, reads, node_of, x_last, oracle, prm):
        return None

    def fields(self, endbr, contour):
        return dict(end=endbr)


@dataclass(frozen=True)
class Finite:
    """a reader at one finite size and one observation time. No field has a default. strand: the reader's own D alphabet -> Strand, total."""
    L: int
    burn: int
    n: int
    strand: Tuple[Tuple[str, Strand], ...]
    terminals: ClassVar[type] = FiniteTerm
    unreached: ClassVar[frozenset] = frozenset({FiniteTerm.CONTOUR_EDGE})

    def table(self, read):
        return TERM_FINITE

    def end_bracket(self, term, x, hmin, t):
        return None

    def contour(self, term, band_run, reads, node_of, x_last, oracle, prm):
        if term is not FiniteTerm.CONTOUR_EDGE:
            return None
        recs = {j: oracle.record(node_of(j)) for j in reads}
        w = tuple(WindowRead(j=j, u=tuple(float(x) for x in node_of(j)), side=reads[j].value, **recs[j]) for j in sorted(reads))
        strand = dict(self.strand)
        h0 = next(r for r in w if r.j == 0)
        return ContourEdge(fail_at=(h0.K, h0.h), last_at=tuple(oracle.coord(x_last)), band=Band.RUN if band_run else Band.NO_RUN, h0=h0,
                           sides=(side_edge(w, -1, strand), side_edge(w, +1, strand)),
                           resolution=(("ht", prm["ht"]), ("e", prm["e"]), ("L", self.L), ("BURN", self.burn), ("N", self.n)), reads=w)

    def fields(self, endbr, contour):
        return dict(contour=contour)


@dataclass(frozen=True)
class FiniteStored:
    """a finite-size reader of STORED maps (plan 1109, OPEN-A ruling): FINITE, with a CONTOUR_EDGE payload that OMITS the strand edges, because the
    reader's alphabet (DIS, ORD, MID) has no two-start strand table. source names the stored object."""
    source: str
    terminals: ClassVar[type] = FiniteTerm
    unreached: ClassVar[frozenset] = frozenset({FiniteTerm.CONTOUR_EDGE})

    def table(self, read):
        return TERM_FINITE

    def end_bracket(self, term, x, hmin, t):
        return None

    def contour(self, term, band_run, reads, node_of, x_last, oracle, prm):
        if term is not FiniteTerm.CONTOUR_EDGE:
            return None
        w = tuple(ReadAt(j=j, u=tuple(float(x) for x in node_of(j)), side=reads[j].value) for j in sorted(reads))
        return ContourEdge(fail_at=tuple(float(x) for x in node_of(0)), last_at=tuple(float(x) for x in x_last), band=Band.RUN if band_run else Band.NO_RUN,
                           h0=None, sides=None, resolution=(("ht", prm["ht"]), ("e", prm["e"]), ("source", self.source)), reads=w)

    def fields(self, endbr, contour):
        return dict(contour=contour)


UNREACHED = Sharp.unreached | Finite.unreached | FiniteStored.unreached   # PARTIAL: `term in ev.unreached`; the members of the two enums are disjoint objects, so one set serves both


class Budget(Exception):
    pass


class PrefUndefined(Exception):
    pass


# declared: plan 1038 sec 2 table, in u units (s = 1 for the planted bank; one cell in grid mode)
E_SUPPORT = 2       # plan 1048: a run of >= e equal resolved reads is SUPPORTED (one flip tolerated); e = 3 is the declared sensitivity arm
PARAMS = {"continuous": dict(h0=0.04, hmin=0.005, hmax=0.08, ht=0.01, W=10, r=0.002, wc=0.15, budget=3000, e=E_SUPPORT, H="reads"),
          "grid": dict(h0=2, hmin=1, hmax=4, ht=1, W=6, r=1, wc=5, budget=400, e=E_SUPPORT, H="reads")}
TOL = 1e-9          # floating tolerance on domain membership only (P + j*ht*n accumulates rounding); not a science threshold


def R90(t):
    return np.array([-t[1], t[0]])


def unit(v):
    return np.asarray(v, float) / np.linalg.norm(v)


def snap(u):
    """per axis to the nearest integer, a .5 to the lower index (A5)."""
    return tuple(int(np.ceil(x - 0.5)) for x in u)


class Plane:
    def __init__(self, lo, hi, grid):
        self.lo, self.hi, self.grid = np.asarray(lo, float), np.asarray(hi, float), grid

    def inside(self, u):
        return bool(np.all(u >= self.lo - TOL) and np.all(u <= self.hi + TOL))


class Probe:
    """the oracle, memoised by snapped (grid) or exact (continuous) query point; calls = distinct reads, against the budget (A4)."""
    def __init__(self, side_fn, plane, budget):
        self.f, self.plane, self.budget, self.memo, self.calls = side_fn, plane, budget, {}, 0

    def key(self, u):
        return snap(u) if self.plane.grid else (float(u[0]), float(u[1]))

    def node(self, u):
        return np.array(self.key(u), float)

    def __call__(self, u):
        assert self.plane.inside(u), "a query outside the domain is never made"
        k = self.key(u)
        if k not in self.memo:
            if self.calls >= self.budget:
                raise Budget
            s = self.f(np.array(k, float))
            assert isinstance(s, Side), "the side oracle is a total type"
            self.memo[k] = s; self.calls += 1
        s = self.memo[k]
        return Side.UNRES if (s is Side.SINGLE and READ["single"] == "as_unres") else s


def brackets(reads, outs, W, e):
    """plan 1048 (v1.4) / plan 1050 (v1.5, boundary clause OUT-only): the RUN-SUPPORTED brackets over the reads so far. Returns [(ja, jb, boundary_only)], ja/jb the j of the inner ends of the
    two runs, in j order (ja < jb); the caller orients NEG|POS. outs = the j examined and found OUT (not read)."""
    rj = sorted(j for j, s in reads.items() if s in RESOLVED)
    runs = []
    for j in rj:
        if runs and runs[-1][0] is reads[j]:
            runs[-1][1].append(j)
        else:
            runs.append((reads[j], [j]))
    sup = []
    for i, (side, js) in enumerate(runs):
        by_len = len(js) >= e
        if READ["bracket"] == "run_noboundary":
            edge = False
        elif READ["bracket"] == "run_v14":              # v1.4 clause (seen-red / baseline only): the window limit also vouches
            edge = (i == 0 and (js[0] - 1 in outs or js[0] - 1 < -W)) or (i == len(runs) - 1 and (js[-1] + 1 in outs or js[-1] + 1 > W))
        else:                                           # v1.5: the node beyond was examined and found OUT
            edge = (i == 0 and js[0] - 1 in outs) or (i == len(runs) - 1 and js[-1] + 1 in outs)
        if by_len or edge:
            sup.append((side, js, not by_len))
    return [(x[1][-1], y[1][0], x[2] or y[2]) for x, y in zip(sup, sup[1:]) if {x[0], y[0]} == {Side.NEG, Side.POS}]


def end_evidence(reads, e):
    """plan 1050 (L): positive evidence that the line ENDS here: the read at j = 0 is UNRES or SINGLE and the maximal run of consecutive j of
    UNRES/SINGLE reads containing j = 0 has length >= e. (Flips only swap NEG/POS; they cannot produce this.)"""
    ends = (Side.UNRES, Side.SINGLE)
    if reads.get(0) not in ends:
        return False
    n, j = 1, 1
    while reads.get(j) in ends:
        n += 1; j += 1
    j = -1
    while reads.get(j) in ends:
        n += 1; j -= 1
    return n >= e


def same_flank(reads, e):
    """plan 1057 (rule L'): True iff the evidence run (maximal UNRES/SINGLE run containing j = 0) is closed by the SAME supported side at both
    ends. Each flank side is the side of the nearest SUPPORTED run (>= e equal consecutive resolved reads) walking outward from the run; an
    unsupported run is skipped; the walk ends with 'no flank' at the first UNRES, SINGLE, OUT, unread or beyond-limit node (absence is never
    evidence, H). e is the declared support; no number is added. A window that straddles a true end cannot show SAME flanks."""
    ends, res = (Side.UNRES, Side.SINGLE), (Side.NEG, Side.POS)
    lo = hi = 0
    while reads.get(hi + 1) in ends:
        hi += 1
    while reads.get(lo - 1) in ends:
        lo -= 1

    def flank(j, sd):
        side, m = None, 0
        while reads.get(j) in res:
            m = m + 1 if reads[j] is side else 1
            side = reads[j]
            if m >= e:
                return side
            j += sd
        return None
    a, z = flank(lo - 1, -1), flank(hi + 1, +1)
    return a is not None and a is z


def _cut_run(reads, jlim, sd):
    """plan 1052: the terminal run of resolved reads (UNRES skipped) on side sd whose outermost read is at jlim: (side, length), else None."""
    rj = sorted((j for j, s in reads.items() if s in RESOLVED and j * sd > 0), key=lambda j: -abs(j))
    if not rj or rj[0] != jlim:
        return None
    side, m = reads[jlim], 0
    for j in rj:
        if reads[j] is side:
            m += 1
        else:
            break
    return side, m


def _sup_spans(reads, outs, e):
    """plan 1071: the supported runs of brackets() (READ['bracket'] == 'run'), as (lo, hi, side, boundary_only) spans in j order."""
    rj = sorted(j for j, s in reads.items() if s in RESOLVED)
    runs = []
    for j in rj:
        if runs and runs[-1][0] is reads[j]:
            runs[-1][1].append(j)
        else:
            runs.append((reads[j], [j]))
    sup = []
    for i, (side, js) in enumerate(runs):
        by_len = len(js) >= e
        edge = (i == 0 and js[0] - 1 in outs) or (i == len(runs) - 1 and js[-1] + 1 in outs)
        if by_len or edge:
            sup.append((js[0], js[-1], side, not by_len))
    return sup


def _interfaces(reads, outs, e, pref):
    """plan 1071 rule C: the edge interfaces of a window, as (key, o, r, sd) in sd = +1, -1 order. o = the nearest OUT node on that side, r = the near end
    of the supported run that follows >= 1 non-supported read inward from o (|r - o| >= 2). key is v1.8's ranking key."""
    sp = _sup_spans(reads, outs, e)
    inspan = lambda j: any(a <= j <= b for a, b, _, _ in sp)
    out = []
    for sd in (+1, -1):
        os_ = [j for j in outs if j * sd >= 0]
        if not os_:
            continue
        o = min(os_, key=abs)
        j, r = o - sd, None
        while j in reads and j not in outs:
            if inspan(j):
                r = j; break
            j -= sd
        if r is None or abs(r - o) < 2:
            continue
        bo = [x for x in sp if x[0] <= r <= x[1]][0][3]
        out.append(((bo, abs(o + r), 0 if (o + r) * pref > 0 else 1), o, r, sd))
    return out


def _edge_result(P, n, plane, ht, o, r, sd):
    """plan 1074 al: the edge interface IS the read. The exit is the interval [q_r, B]: q_r = P + r ht n, B = the boundary point of the ray from q_(o - sd)."""
    return "E", P + r * ht * n, exit_ray(P + (o - sd) * ht * n, sd * n, plane)[1]


def cross(P, n, W, pref_of, probe, prm, info=None, landing=False, chi=0):
    """A2 CROSS. Returns ('X', X, unc, v) with v = unit NEG->POS of the bracket (None if located by MID),
    or ('NO', Corr.CLEAR | Corr.UNREAD). info (optional dict) receives 'seen': the j examined (read or OUT), in order."""
    plane, ht = probe.plane, prm["ht"]
    q = lambda j: P + j * ht * n
    seen = [] if info is None else info.setdefault("seen", [])
    seen.append(0)
    if plane.inside(P):
        s0 = probe(P)
        reads = {0: s0}
        if info is not None:
            info["reads"] = reads                       # plan 1050: the j -> Side map (the END evidence is read from it)
        if s0 is Side.MID:
            return "X", probe.node(P) if plane.grid else P.copy(), ht / 2, None
    else:
        s0, reads = None, {}                            # A2 rule 2 at j = 0 (a star centre outside the domain): OUT, not read
        if info is not None:
            info["reads"] = reads
    pref = pref_of(s0)
    out = {+1: False, -1: False}
    outs = {0} if s0 is None else set()
    order = [s * k for k in range(1, W + 1) for s in (pref, -pref)]
    e, run = prm["e"], READ["bracket"] != "adjacent"
    for j in order:
        sd = 1 if j > 0 else -1
        if out[sd]:
            continue
        seen.append(j)
        if not plane.inside(q(j)):
            out[sd] = True; outs.add(j); continue       # OUT: not read; expansion continues on the other side
        s = probe(q(j)); reads[j] = s
        if s is Side.MID:
            return "X", probe.node(q(j)) if plane.grid else q(j), ht / 2, None
        if run:
            if brackets(reads, outs, W, e):
                break
        elif len({v for v in reads.values() if v in (Side.NEG, Side.POS)}) == 2:
            break
    Wf = W
    if run and READ["limit"] == "reads" and READ["bracket"] == "run" and not brackets(reads, outs, W, e):
        # plan 1052 (H): the window limit is never evidence. A terminal run cut by +-W and shorter than e is read on, e - m nodes beyond the limit.
        for sd in (pref, -pref):
            r = _cut_run(reads, sd * W, sd)
            if r is None or r[1] >= e:
                continue
            side, m = r
            for k in range(1, e - m + 1):
                j = sd * (W + k)
                seen.append(j)
                if not plane.inside(q(j)):
                    outs.add(j); break                  # OUT reached while reading beyond: the v1.5 OUT-only clause applies
                s = probe(q(j)); reads[j] = s
                if s is Side.MID:
                    return "X", probe.node(q(j)) if plane.grid else q(j), ht / 2, None
                if brackets(reads, outs, W + k, e):
                    break
                if s in RESOLVED and s is not side:
                    break                               # the run is closed (and stays unsupported)
            if brackets(reads, outs, W + e, e):
                break
        Wf = W + e
    if run:
        bk = brackets(reads, outs, Wf, e)
        pairs = [(a, b) for a, b, _ in bk]
        rank = {(a, b): bo for a, b, bo in bk}
    else:
        rj = sorted(j for j, s in reads.items() if s in RESOLVED)
        pairs = [(a, b) for a, b in zip(rj, rj[1:]) if {reads[a], reads[b]} == {Side.NEG, Side.POS}]
        rank = {}
    _kfilt = False
    if run and chi != 0:
        # plan 1088 K (v2.0; plans 1081, 1085): only crossings of the followed orientation chi are candidates
        _n0 = len(pairs)
        pairs = [p for p in pairs if (1 if reads[p[0]] is Side.NEG else -1) == chi]
        _kfilt = len(pairs) < _n0
    if run and pairs:
        # plan 1071 rule C: candidates = pairs U edge interfaces, ranked by v1.8's key (exact tie -> pair). An interface strictly nearer than the
        # chosen pair locates nothing (UNREAD), except in a landing window (plan 1074 al), where the interface IS the read: E.
        _kch = min((rank.get(p, False), abs(p[0] + p[1]), 0 if (p[0] + p[1]) * pref > 0 else 1) for p in pairs)
        _ifs = _interfaces(reads, outs, e, pref)
        if chi != 0:
            _ifs = [c for c in _ifs if c[3] * (1 if reads[c[2]] is Side.NEG else -1) == chi]     # plan 1088 K
        _best = None
        for _c in _ifs:
            if _best is None or _c[0] < _best[0]:
                _best = _c
        if _best is not None and _best[0] < _kch:
            if info is not None:
                info["pair"] = None
            if landing:
                return _edge_result(P, n, plane, ht, *_best[1:])
            return "NO", Corr.UNREAD
    if run and not pairs and landing:
        # plan 1074 al: a landing window with no pair; an edge interface, if one exists, is the only candidate
        _ifs = _interfaces(reads, outs, e, pref)
        if chi != 0:
            _ifs = [c for c in _ifs if c[3] * (1 if reads[c[2]] is Side.NEG else -1) == chi]     # plan 1088 K
        _best = None
        for _c in _ifs:
            if _best is None or _c[0] < _best[0]:
                _best = _c
        if _best is not None:
            return _edge_result(P, n, plane, ht, *_best[1:])
    if not pairs:
        # plan 1105: #18 as the total table CORR_NOPAIR (plan 1088 K: a window that read only the other orientation is not CLEAR = the kfilt 1 cells)
        return "NO", Corr[CORR_NOPAIR[(outer_read(reads, +1), outer_read(reads, -1), int(_kfilt))]]
    ja, jb = min(pairs, key=lambda p: (rank.get(p, False), abs(p[0] + p[1]), 0 if (p[0] + p[1]) * pref > 0 else 1))
    if info is not None:
        info["pair"] = (ja, jb)
    a, b = (q(ja), q(jb)) if reads[ja] is Side.NEG else (q(jb), q(ja))     # a = NEG end, b = POS end
    v = unit(b - a)
    while True:
        if plane.grid:
            sa, sb = snap(a), snap(b)
            if max(abs(sa[0] - sb[0]), abs(sa[1] - sb[1])) <= 1:
                break
        elif np.linalg.norm(b - a) <= prm["r"]:
            break
        m = (a + b) / 2
        s = probe(m)
        if s is Side.MID:
            return "X", probe.node(m) if plane.grid else m, np.linalg.norm(b - a) / 2, v
        if s is Side.UNRES or s is Side.SINGLE:
            break
        a, b = (m, b) if s is Side.NEG else (a, m)
    return "X", (a + b) / 2, np.linalg.norm(b - a) / 2, v


def checkpoints(poly, h0):
    """A3: (point, t) for the vertices, then the points dividing each segment into the fewest equal parts of length <= 2*h0."""
    poly = [np.asarray(p, float) for p in poly]
    assert len(poly) >= 2
    out = []
    for i, c in enumerate(poly):
        if i == 0:
            t = unit(poly[1] - c)
        elif i == len(poly) - 1:
            t = unit(c - poly[i - 1])
        else:
            s = unit(c - poly[i - 1]) + unit(poly[i + 1] - c)
            assert np.linalg.norm(s) > 0, "A3: a zero tangent sum is impossible by declaration"
            t = unit(s)
        out.append((c, t))
    for a, b in zip(poly, poly[1:]):
        L = np.linalg.norm(b - a); k = int(np.ceil(L / (2 * h0) - 1e-12))
        out += [(a + (b - a) * q / k, unit(b - a)) for q in range(1, k)]
    return out


def seg_dist(x, path):
    """distance from point x to a polyline (a single point if it has one vertex)."""
    path = np.asarray(path, float)
    if len(path) == 1:
        return float(np.linalg.norm(x - path[0]))
    a, b = path[:-1], path[1:]; ab = b - a
    tt = np.clip(np.einsum("ij,ij->i", x - a, ab) / np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-300), 0, 1)
    return float(np.min(np.linalg.norm(a + tt[:, None] * ab - x, axis=1)))


# The literal applications declared in the header. ALTERNATIVES exist ONLY so studies/LINENAV/sens1040.py can show whether a reading
# changes any result; the navigator itself always runs with READ_DEFAULT.
READ_DEFAULT = dict(h_cut_persists=True, edge_window="full", star_trace="all", star_closed=True, closed_t="step", pref_perp="normal",
                    edge_strict="b_only", acq_j0="extrap", revisit="after_turn", single="resolved", bracket="run", end="evidence", limit="reads", turn="forward", end_flank="lprime")
READ = dict(READ_DEFAULT)


def rot(t, deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([c * t[0] - s * t[1], s * t[0] + c * t[1]])


def exit_ray(X, t, plane):
    """the ray X + s t: (s_exit to the first hull boundary, the set of axes whose face the exit point lies on)."""
    s = np.inf
    for k in range(2):
        if t[k] != 0:
            s = min(s, ((plane.hi[k] if t[k] > 0 else plane.lo[k]) - X[k]) / t[k])
    s = max(float(s), 0.0)
    Pc = X + s * t
    faces = {k for k in range(2) if t[k] != 0 and abs(Pc[k] - (plane.hi[k] if t[k] > 0 else plane.lo[k])) <= TOL}
    return s, Pc, faces


def cut(X, t, h, plane):
    """C2 (continuous): the largest s in [0, h] with X + s*t inside the domain (the boundary point along t)."""
    return min(h, exit_ray(X, t, plane)[0])


def touches_edge(P, n, W, plane, ht, seen=None):
    """C2: the failing CROSS's window has an OUT node or reaches the boundary (outside or ON it, within TOL)."""
    js = range(-W, W + 1) if seen is None else seen
    lo, hi = plane.lo + TOL, plane.hi - TOL
    return any(not (np.all(P + j * ht * n > lo) and np.all(P + j * ht * n < hi)) for j in js)


def ax(k):
    v = np.zeros(2); v[k] = 1.0
    return v


def axes(t):
    """G1: a = the axis maximising |e_a . R90(t)| (a tie goes to the column axis, 1); b = the other."""
    n = R90(t)
    a = 0 if abs(n[0]) > abs(n[1]) else 1
    return a, 1 - a


def rnd(x):
    """round, a .5 to the lower index (A5)."""
    return int(np.ceil(x - 0.5))


def gpredict(X, t, h, plane):
    """G1-G3 predictor. Returns None (EDGE) or (P node, oriented search axis n, predicted point)."""
    a, b = axes(t)
    sg = 1 if t[b] > 0 else -1
    fl = (lambda x: float(np.floor(x + TOL))) if sg > 0 else (lambda x: float(np.ceil(x - TOL)))
    se, Pc, faces = exit_ray(X, t, plane)
    if se <= TOL:
        return None                                              # G3: X_k already on the boundary the ray exits through
    bu = fl(X[b] + sg * h)                                       # G2
    cutk = h > se + TOL or (bu - X[b]) / t[b] > se + TOL         # G3 (+ the declared gap application)
    bn = fl(Pc[b]) if cutk else bu
    if (bn - X[b]) * sg <= TOL:
        return None                                              # G3: no b_next strictly beyond b
    if cutk and READ["edge_strict"] == "both" and b in faces and abs(bn - Pc[b]) <= TOL:
        return None
    apred = X[a] + (bn - X[b]) * t[a] / t[b]
    P = np.zeros(2); P[b] = bn
    P[a] = (plane.hi[a] if t[a] > 0 else plane.lo[a]) if (cutk and a in faces) else rnd(apred)
    Pp = np.zeros(2); Pp[a], Pp[b] = apred, bn
    return P, ax(a) * np.sign(R90(t)[a]), Pp


STAR_DEG = (0, 45, -45, 90, -90)                 # C3, continuous: base t_k; +-135 and 180 excluded as backward
GSTAR = [(0, +1), (1, +1), (0, -1), (1, -1)]     # G5 declared tie order: + before -, rows before columns


def star(Xk, t, probe, prm, W, trace):
    """C3 / G5 turn search. Returns ((X, unc, v, label, d) | None, reads, tie)."""
    reads, plane, tie = [], probe.plane, False
    if plane.grid:
        order = sorted(GSTAR, key=lambda c: -c[1] * t[c[0]])
        tie = abs(order[-1][1] * t[order[-1][0]] - order[-2][1] * t[order[-2][0]]) <= TOL
        cands = []
        for k, s in order[:3]:
            d = s * ax(k)
            bn = float(np.floor(Xk[k] + 2 + TOL)) if s > 0 else float(np.ceil(Xk[k] - 2 - TOL))
            bound = plane.hi[k] if s > 0 else plane.lo[k]
            cutk = (bn - bound) * s > TOL
            bn = bound if cutk else bn
            if (bn - Xk[k]) * s <= TOL or (cutk and READ["edge_strict"] == "both"):
                cands.append((f"{'+-'[s < 0]}{'rc'[k]}", d, None)); continue
            P = np.zeros(2); P[k] = bn; P[1 - k] = rnd(Xk[1 - k])
            cands.append((f"{'+-'[s < 0]}{'rc'[k]}", d, P))
    else:
        cands = [(deg, rot(t, deg), Xk + prm["h0"] * rot(t, deg)) for deg in STAR_DEG]
    for lab, d, P in cands:
        if P is None:
            reads.append(dict(deg=lab, res="EDGE", X=None, corr=None, accepted=False, v=None)); continue
        c = cross(P, R90(d), W, lambda s: -1, probe, prm)
        ok = (c[0] == "X" and (float(np.dot(c[1] - Xk, d)) > 0 if READ["turn"] == "v16" else float(np.dot(c[1] - Xk, t)) > -c[2])
              and all(np.linalg.norm(c[1] - p) > prm["h0"] / 2 for p in trace))
        reads.append(dict(deg=lab, res=c[0], X=None if c[0] != "X" else np.round(c[1], 4).tolist(),
                          corr=None if c[0] == "X" else c[1].value, accepted=ok, v=c[3] if c[0] == "X" else None))
        if ok:
            return (c[1], c[2], c[3], lab, d), reads, tie
    return None, reads, tie


def follow(X0, t0, v0, probe, prm, forward=True, W=None):
    """FOLLOW both ways from X0 (+t first; a CLOSED +t skips -t, A6). forward=False deletes the forward-progress clause (seen-red only).
    Plan 1040: C2/G3 edge landing and END->EDGE typing, C3/G5 turn search before typing (<= 4 in a row), C4 pref -1 until a bracket is
    read, R2 CLOSED needs t_k . t_0 > 0; grid mode G1/G2 axis search."""
    grid = probe.plane.grid
    ev = probe.f.evidence                                           # plan 1109: the oracle's declared class (navigate read it first, before any read)
    W = prm["W"] if W is None else W
    dirs = {}
    for sgn in (+1, -1):
        if sgn == -1 and dirs[+1]["term"] is ev.terminals.CLOSED:
            break
        X, t, h, cnt, v, turns = [X0], sgn * t0, prm["h0"], 0, v0, 0
        tp = [t0]                                                   # plan 1045 A1: stored tangent per located point, in the path's +t sense
        priort = [t0] + (list(dirs[+1]["tp"]) if sgn == -1 else [])
        turned = False                                              # plan 1045: a turn-search point has been accepted in this direction
        tdir = sgn * t0
        hist, unc, endbr, contour, stars, ties = [h], [], None, None, [], 0
        exitv = None
        prior = [X0] + (list(dirs[+1]["pts"]) if sgn == -1 else [])

        def pref_of(s, n, nk):
            if s is Side.UNRES or s is Side.SINGLE or s is None or v is None:          # C4: no bracket read yet in this direction => pref -1
                return -1
            vn = float(np.dot(v, nk if READ["pref_perp"] == "normal" else n))
            if vn == 0:
                return -1                                          # the last bracket is parallel to the line: no orientation (C4 rule)
            return int(np.sign(vn)) * (1 if s is Side.NEG else -1) * (int(np.sign(np.dot(n, nk))) if READ["pref_perp"] == "normal" else 1)

        def closes(tk):
            return len(X) - 1 >= 4 and float(np.dot(tk, tdir)) > 0
        while True:
            if grid:
                g = gpredict(X[-1], t, h, probe.plane)
                if g is None:
                    term = ev.terminals.EDGE; break
                P, n, Pp = g; hs = h; landing = False
            else:
                hc = cut(X[-1], t, h, probe.plane)
                if hc < prm["hmin"] - TOL:
                    term = ev.terminals.EDGE; break                        # C2: on the boundary in the direction of travel, or cut h < h_min
                hs = hc
                landing = exit_ray(X[-1], t, probe.plane)[0] <= h     # plan 1074 al: the same comparison cut() makes; P is the boundary landing point
                if READ["h_cut_persists"]:
                    h = hc
                P = X[-1] + hs * t; n = R90(t); Pp = P
            nk = R90(t)
            info = {}
            try:
                c = cross(P, n, W, lambda s: pref_of(s, n, nk), probe, prm, info, landing,
                          0 if v is None else int(np.sign(float(np.dot(v, n)))))
            except Budget:
                term = ev.terminals.BUDGET; break
            if c[0] == "E":
                term, exitv = ev.terminals.EDGE, (c[1].copy(), c[2].copy()); break   # plan 1074 al: the edge interface is the read; no point, no star, h not halved
            if c[0] == "X" and c[3] is not None:
                v = c[3]
            if c[0] == "X" and (not forward or float(np.dot(c[1] - X[-1], t)) > 0):
                if turned and READ["revisit"] != "off":
                    if READ["revisit"] == "next":
                        turned = False
                    tx = unit(c[1] - X[-1]) if np.linalg.norm(c[1] - X[-1]) > 0 else t
                    if any(np.linalg.norm(c[1] - p) <= prm["h0"] / 2 and float(np.dot(sgn * tx, ty)) < -0.5
                           for p, ty in zip(prior + X, priort + tp)):
                        term = ev.terminals.REVISIT; break                  # plan 1045 (+A1): proximity AND opposite sense; X is NOT appended
                off = float(np.linalg.norm(c[1] - Pp))
                X.append(c[1]); unc.append(c[2]); turns = 0
                tnew = unit(X[-1] - X[-2]) if np.linalg.norm(X[-1] - X[-2]) > 0 else t
                tp.append(sgn * tnew)
                if np.linalg.norm(X[-1] - X0) <= hs and closes(t if READ["closed_t"] == "step" else tnew):
                    term = ev.terminals.CLOSED; break
                cnt = cnt + 1 if off < hs / 4 else 0
                if cnt == 2:
                    h, cnt = min(2 * hs, prm["hmax"]), 0
                t = tnew
            else:
                cnt, h = 0, hs / 2
                if h < prm["hmin"] - TOL:
                    edge = touches_edge(P, n, W, probe.plane, prm["ht"], None if READ["edge_window"] == "full" else info["seen"])
                    if turns < 4:
                        turns += 1
                        trace = prior + X if READ["star_trace"] == "all" else X
                        try:
                            got, reads, tie = star(X[-1], t, probe, prm, W, trace)
                        except Budget:
                            term = ev.terminals.BUDGET; break
                        ties += tie
                        for r in reads:
                            if r["v"] is not None:
                                v = r["v"]                         # orientation is read from every bracket (A2)
                        stars.append(dict(at=np.round(X[-1], 4).tolist(), accepted=got[3] if got else None,
                                          reads=[{k: r[k] for k in ("deg", "res", "X", "corr", "accepted")} for r in reads]))
                        if got is not None:
                            Xs = got[0]; tn = unit(Xs - X[-1])
                            X.append(Xs); unc.append(got[1]); t, h, cnt = tn, prm["h0"], 0
                            tp.append(sgn * tn)
                            turned = True
                            hist.append(h)
                            if READ["star_closed"] and np.linalg.norm(X[-1] - X0) <= h and closes(got[4] if READ["closed_t"] == "step" else tn):
                                term = ev.terminals.CLOSED; break
                            continue
                    # plan 1105: #43 as one total table per declared reading (EDGE first is the edge = 1 row; LOST = no evidence the line ends, plan 1050)
                    # plan 1109: the table is the declared class's; the FINITE payload is built from the reads the window made, no number is compared
                    key = (int(edge), int(end_evidence(info["reads"], prm["e"])), int(same_flank(info["reads"], prm["e"])))
                    term = ev.terminals[ev.table(READ)[key]]
                    endbr = ev.end_bracket(term, X[-1], prm["hmin"], t)
                    contour = ev.contour(term, bool(key[1] and not key[2]), info["reads"], lambda j: probe.node(P + j * prm["ht"] * n), X[-1], probe.f, prm)
                    break
            hist.append(h)
        dirs[sgn] = dict(term=term, pts=X[1:], tp=tp[1:], unc=unc, h=hist, **ev.fields(endbr, contour), stars=stars, ties=ties, exit=exitv)
    return dirs


def unreached_cps(dev, cps, path, dirs):
    """plan 1050 (PARTIAL): the deviating checkpoints whose nearest path point is the final vertex of an UNREACHED direction (plan 1109: term in ev.unreached; SHARP {LOST}, FINITE {CONTOUR_EDGE})."""
    path = np.asarray(path, float)
    if len(path) < 2:
        return set()
    ends = [path[-1] if sg == +1 else path[0] for sg in (+1, -1) if sg in dirs and dirs[sg]["term"] in UNREACHED]
    return {k for k in dev for en in ends if abs(seg_dist(cps[k][0], path) - float(np.linalg.norm(cps[k][0] - en))) <= 1e-12}


def trace_verdict(cps, path, dirs, wc):
    """the total trace verdict once acquired (plan 1050): (verdict, dev, unreached)."""
    dev = [k for k, (c, _) in enumerate(cps) if seg_dist(c, path) > wc]
    unreached = unreached_cps(dev, cps, path, dirs)
    rest = [k for k in dev if k not in unreached]
    return (Verdict.FOUND_DEVIATES if rest else Verdict.PARTIAL_IN_CORRIDOR if dev else Verdict.FOLLOWED_IN_CORRIDOR), dev, unreached


def navigate(suspect, side_fn, plane, mode, forward=True, W=None):
    """ACQUIRE over the suspect's checkpoints (G6 in grid mode), then FOLLOW, then the total trace verdict."""
    ev = side_fn.evidence                                           # plan 1109: the declared class; no default, so an undeclared oracle raises AttributeError before its first read
    prm = PARAMS[mode]
    assert (mode == "grid") == plane.grid
    probe = Probe(side_fn, plane, prm["budget"])
    cps = checkpoints(suspect, prm["h0"])
    for c, _ in cps:
        assert plane.inside(c), "A1: a checkpoint outside the domain is a declaration error"
    Wacq = int(round(prm["wc"] / prm["ht"]))
    corr, acq = [], None
    for i, (c, t) in enumerate(cps):
        if plane.grid:                                             # G6: the line b = round(b_c); j = 0 = round(a_pred)
            a, b = axes(t); bl = rnd(c[b])
            ap = c[a] + (bl - c[b]) * t[a] / t[b] if READ["acq_j0"] == "extrap" else c[a]
            P = np.zeros(2); P[a], P[b] = rnd(ap), bl
            n = ax(a) * np.sign(R90(t)[a])
        else:
            P, n = c, R90(t)
        r = cross(P, n, Wacq, lambda s: -1, probe, prm)
        if r[0] == "X":
            corr.append(Corr.CROSS); acq = (i, r[1], r[2], r[3], t); break
        corr.append(r[1])
    rec = dict(cps=cps, corr=corr, calls=None, dirs={}, X0=None, path=None, dev=[], evidence=ev)
    if acq is None:
        rec["verdict"] = Verdict[VERDICT_NOACQ[tuple(int(x in corr) for x in (Corr.CROSS, Corr.CLEAR, Corr.UNREAD))]]     # plan 1105: #47
        rec["calls"] = probe.calls
        return rec
    i, X0, u0, v0, t0 = acq
    dirs = follow(X0, t0, v0, probe, prm, forward, W)
    path = [p for p in reversed(dirs[-1]["pts"])] if -1 in dirs else []
    path = path + [X0] + dirs[+1]["pts"]
    if dirs[+1]["term"] is ev.terminals.CLOSED:
        path = path + [X0]
    verdict, dev, unreached = trace_verdict(cps, path, dirs, prm["wc"])
    rec.update(verdict=verdict, dev=dev, unreached=sorted(unreached), acq_cp=i, X0=X0, u0=u0,
               dirs=dirs, path=np.array(path), calls=probe.calls)
    return rec
