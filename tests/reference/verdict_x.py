"""verdict_x.py - the declared per-point verdict tables of [X2]/[X3] (plumbing: tables only; totality checked by checks.py C6).
Each stage is a TOTAL table; a terminal verdict passes through every later stage unchanged (downgrade-only: a later
stage can only move CAND to a terminal verdict, never revive a terminal one). Keys are sign-cell strings (sign.py values)."""
SIGNS = ("SIG-", "NEG", "SLOW-", "ZERO!", "SLOW+", "POS", "SIG+", "UNRES")
FLOW_CODE = {"SIG-": "FLOWING", "NEG": "FLOWING", "SLOW-": "SLOW", "ZERO!": "STOPPED", "SLOW+": "SLOW",
             "POS": "FLOWING", "SIG+": "FLOWING", "UNRES": "UNRES"}
GROWTH_CODE = {"SIG-": "IRRELEVANT", "NEG": "IRRELEVANT", "SLOW-": "WEAK", "ZERO!": "MARGINAL", "SLOW+": "WEAK",
               "POS": "RELEVANT", "SIG+": "RELEVANT", "UNRES": "UNRES", "NOT-EVALUATED": "UNRES"}
STAB_CODE = {"SIG-": "OFF", "NEG": "OFF", "SLOW-": "STABLE", "ZERO!": "STABLE", "SLOW+": "STABLE",
             "POS": "CROSSING", "SIG+": "CROSSING", "UNRES": "UNRES", "NOT-EVALUATED": "UNRES"}
START_CODE = {"SIG-": "FLUCT", "NEG": "FLUCT", "SLOW-": "INDEP", "ZERO!": "INDEP", "SLOW+": "INDEP",
              "POS": "COEXIST", "SIG+": "COEXIST", "UNRES": "UNRES"}
START_RANK = {"COEXIST": 0, "FLUCT": 1, "UNRES": 2, "INDEP": 3}       # declared combine order over L (lowest wins)

STAGE1 = {"DIS": "NOT", "ORD": "NOT", "MID": "CAND"}
T1 = ("NOT",)
STAGE2 = {**{(v, s): v for v in T1 for s in START_RANK},
          ("CAND", "COEXIST"): "FIRST-ORDER", ("CAND", "FLUCT"): "REFUSE-EQUIL",
          ("CAND", "UNRES"): "REFUSE-EQUIL", ("CAND", "INDEP"): "CAND"}
T2 = ("NOT", "FIRST-ORDER", "REFUSE-EQUIL")
FLOWS = ("STOPPED", "SLOW", "FLOWING", "UNRES")
STAGE3 = {**{(v, f): v for v in T2 for f in FLOWS},
          ("CAND", "STOPPED"): "CAND", ("CAND", "SLOW"): "REFUSE-SLOW",
          ("CAND", "FLOWING"): "NOT", ("CAND", "UNRES"): "REFUSE-FLOW"}
T3 = T2 + ("REFUSE-SLOW", "REFUSE-FLOW")
GROWTHS = ("RELEVANT", "MARGINAL", "WEAK", "IRRELEVANT", "UNRES")
STABS = ("STABLE", "CROSSING", "OFF", "UNRES")
CAND_GS = {("RELEVANT", "STABLE"): "POINT", ("RELEVANT", "CROSSING"): "WALKING",
           ("RELEVANT", "OFF"): "REFUSE-OFF", ("RELEVANT", "UNRES"): "REFUSE-UNRES",
           ("MARGINAL", "STABLE"): "LINE", ("MARGINAL", "CROSSING"): "WALKING",
           ("MARGINAL", "OFF"): "REFUSE-OFF", ("MARGINAL", "UNRES"): "REFUSE-UNRES",
           **{("WEAK", s): "REFUSE-WEAK" for s in STABS},
           **{("IRRELEVANT", s): "REFUSE-IRRELEVANT" for s in STABS},
           **{("UNRES", s): "REFUSE-UNRES" for s in STABS}}
STAGE4 = {**{(v, g, s): v for v in T3 for g in GROWTHS for s in STABS},
          **{("CAND", g, s): CAND_GS[(g, s)] for g in GROWTHS for s in STABS}}
VERDICTS = ("POINT", "LINE", "WALKING", "FIRST-ORDER", "NOT", "REFUSE-EQUIL", "REFUSE-SLOW", "REFUSE-FLOW",
            "REFUSE-WEAK", "REFUSE-OFF", "REFUSE-IRRELEVANT", "REFUSE-UNRES")
SCORE_CLASS = {v: v for v in VERDICTS[:5]} | {v: "REFUSE" for v in VERDICTS[5:]}


def verdict(side, start, flow, growth, stab):
    return STAGE4[(STAGE3[(STAGE2[(STAGE1[side], start)], flow)], growth, stab)]

# [X4] decoy cell: (pipeline scoring class, h-crossing code) -> cell
CLASSES = ("POINT", "LINE", "WALKING", "FIRST-ORDER", "NOT", "REFUSE")
X4_CELL = {**{("NOT", c): "NOT" for c in START_RANK}, ("NOT", "COEXIST"): "FIRST-ORDER-LINE",
           **{("FIRST-ORDER", c): "FIRST-ORDER-LINE" for c in START_RANK},
           **{(v, c): v for v in ("POINT", "LINE", "WALKING", "REFUSE") for c in START_RANK}}
