"""The rule bank.

Every role is a named rule with numeric thresholds. Nothing here is a model call: a
role can be traced to a line in this file and re-checked by hand, which is what the
case specification requires under must have 3.

Thresholds live in THRESHOLDS so the README table and the code cannot drift apart.
"""
from __future__ import annotations

import pandas as pd

ROLES = ["consolidator", "transit", "distributor", "terminal",
         "coordinator", "peripheral", "unclassified"]

# TODO tune against the data. The case notes state the set contains nodes receiving
# from 8 to 24 distinct payers, nodes fanning out to 60 to 116 receivers, and 72
# nodes with pass-through between 0.8 and 1.2.
THRESHOLDS = {
    "consolidator_min_in_deg": 8,
    "consolidator_max_pass_through": 0.5,
    "distributor_min_out_deg": 20,
    "transit_pass_through_lo": 0.8,
    "transit_pass_through_hi": 1.2,
    "transit_max_dwell_days": 2,
    "coordinator_min_in_deg": 4,
    "coordinator_min_out_deg": 4,
    "min_tx_for_stable_ratio": 3,
}


def assign(df: pd.DataFrame) -> pd.DataFrame:
    """Returns df with role, role_score and evidence. Order of rules is the precedence order."""
    out = df.copy()
    out["role"] = ""
    out["role_score"] = 0.0
    out["evidence"] = ""

    for i, r in out.iterrows():
        role, score, ev = _classify(r)
        out.at[i, "role"] = role
        out.at[i, "role_score"] = round(score, 3)
        out.at[i, "evidence"] = ev[:200]
    return out


def _classify(r) -> tuple[str, float, str]:
    T = THRESHOLDS

    if r.isolated:
        return ("peripheral", 0.9,
                f"no transfers in window; depth={int(r.depth)}, seed={bool(r.is_seed)}")

    # Declared limitation: seed inflow is understated by the crawl design, so any rule
    # that reads in_kzt for a seed is unsound. Seeds are judged on outbound only.
    if r.is_seed and r.in_deg == 0 and r.out_deg > 0:
        return ("peripheral", 0.5,
                f"seed, outbound only: out_deg={int(r.out_deg)}, out={r.out_kzt:,.0f} KZT; "
                f"inflow not observable by collection design")

    if r.truncated_by_depth:
        return ("unclassified", 0.0,
                f"hop 4 with no outgoing: crawl boundary, not a terminal; "
                f"in={r.in_kzt:,.0f} KZT from {int(r.in_deg)} payers")

    if r.genuine_terminal:
        return ("terminal", 0.8,
                f"depth={int(r.depth)} < 4 and no outgoing: money arrives and stays; "
                f"in={r.in_kzt:,.0f} KZT over {int(r.in_tx)} transfers from {int(r.in_deg)} payers")

    # TODO the four structural roles below are first-cut rules. Tune, then update the
    # threshold table in the README so the two stay in step.
    if r.in_deg >= T["consolidator_min_in_deg"] and (
            pd.isna(r.pass_through) or r.pass_through <= T["consolidator_max_pass_through"]):
        return ("consolidator", 0.7,
                f"in_deg={int(r.in_deg)} payers, in={r.in_kzt:,.0f} KZT, "
                f"pass_through={r.pass_through:.2f}" if pd.notna(r.pass_through) else "")

    if r.out_deg >= T["distributor_min_out_deg"]:
        return ("distributor", 0.7,
                f"out_deg={int(r.out_deg)} receivers, out={r.out_kzt:,.0f} KZT "
                f"over {int(r.out_tx)} transfers")

    if pd.notna(r.pass_through) and T["transit_pass_through_lo"] <= r.pass_through <= T["transit_pass_through_hi"]:
        dwell = "" if pd.isna(r.dwell_days) else f", dwell={int(r.dwell_days)}d"
        return ("transit", 0.7,
                f"pass_through={r.pass_through:.2f}: in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT{dwell}")

    if r.in_deg >= T["coordinator_min_in_deg"] and r.out_deg >= T["coordinator_min_out_deg"]:
        return ("coordinator", 0.5,
                f"both sides active: in_deg={int(r.in_deg)}, out_deg={int(r.out_deg)}, "
                f"in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT")

    if (r.in_tx + r.out_tx) < T["min_tx_for_stable_ratio"]:
        return ("unclassified", 0.0,
                f"too few transfers for a stable ratio: in_tx={int(r.in_tx)}, out_tx={int(r.out_tx)}")

    return ("peripheral", 0.4,
            f"no rule threshold met: in_deg={int(r.in_deg)}, out_deg={int(r.out_deg)}, "
            f"in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT")
