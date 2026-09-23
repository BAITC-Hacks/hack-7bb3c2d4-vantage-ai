"""The rule bank.

Every role is a named rule with numeric thresholds. Nothing here is a model call: a
role can be traced to a line in this file and re-checked by hand, which is what the
case specification requires under must have 3.

Thresholds live in THRESHOLDS so the README table and the code cannot drift apart.

Two of the eight roles are abstentions rather than behavioural claims, and they are named
so that a reader cannot mistake either one for a gap.

`abstained_boundary` is the outcome for the 444 nodes that sit at hop 4 with no outgoing
edge. Their pass-through ratio is zero because the crawl stopped there, not because they
retained the money, so applying the consolidator rule to them would read a collection
artefact as behaviour. None of them reaches the consolidator fan-in floor of 8 in any case:
434 have an in-degree of exactly 1, seven have 2 and three have 3. There is no defensible
rule left to write about them, so the system declines to write one.

`abstained_single_observation` is the outcome for the 114 nodes with exactly one transfer in
and one out. A pass-through figure built from a single pair of numbers is not a rate, and
cannot be told apart from coincidence.

That abstention sits below the transit rule in the precedence order rather than above it,
so 27 of the 72 transit nodes are themselves built on one transfer each way. Those 27 say
so in their own evidence. The reasoning for keeping the order this way is written above the
transit branch.

Both are deliberate and both can say why for every row they cover, which the evidence column
carries with the figures the abstention rests on. The two names are also the keys shared with
the review screen's palette, docs/COMPLETENESS.md and the role figure, so they are changed in
all four places together or not at all.
"""
from __future__ import annotations

import pandas as pd

ROLES = ["consolidator", "transit", "distributor", "terminal",
         "coordinator", "peripheral",
         "abstained_boundary", "abstained_single_observation"]

# Each cutoff is placed against the observed distribution rather than picked for being a
# round number. Shares below are measured over the 2,229 nodes that appear in at least one
# edge; the remaining 19 are seeds with no transfers in the window.
THRESHOLDS = {
    # The case notes declare a fan-in band of 8 to 24 distinct payers, and the data agrees:
    # the observed maximum is exactly 24, and 17 nodes (0.76%, the 99.5th percentile) reach
    # 8 against 5 more sitting at 7. The cutoff is the case's own floor, confirmed here.
    "consolidator_min_in_deg": 8,
    # Retention rather than relay. 0.5 sits well clear of the 0.8 floor of the transit band,
    # so no node can satisfy both rules and the precedence order cannot hide a near miss.
    "consolidator_max_pass_through": 0.5,
    # 20 falls in an empty bin: no node has out_deg of exactly 20, the observed values run
    # 19, 19, 19, then 21, 21, 21. The cut is therefore a real gap rather than a round
    # number. 28 nodes (1.26%) sit above it, and the 60 to 116 fan-out band the case notes
    # describe is the top 8 of those.
    "distributor_min_out_deg": 20,
    # The band that reproduces the 72 pass-through nodes the case declares, exactly.
    # Tightening it to 0.9 to 1.1 leaves 51 and would contradict that declared figure.
    "transit_pass_through_lo": 0.8,
    "transit_pass_through_hi": 1.2,
    # The weakest cutoff here, and stated as such: 4 sits on a smooth decay rather than on a
    # gap, with 90 nodes active on both sides at 3, 36 at 4 and 18 at 5. It is the 97.5th
    # percentile of in-degree and the 93rd of out-degree, so it selects nodes well above the
    # typical one without claiming the data shows a natural break.
    "coordinator_min_in_deg": 4,
    "coordinator_min_out_deg": 4,
    # One transfer in and one out is a single observation, not a rate: a pass-through figure
    # built from it cannot be told apart from coincidence. 114 nodes reach this rule.
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


def _payers(n: int) -> str:
    return f"{n} payer" if n == 1 else f"{n} payers"


def _classify(r) -> tuple[str, float, str]:
    T = THRESHOLDS

    # Scored at the bottom of the bank rather than the top. Nothing was observed moving in
    # either direction, so the peripheral label rests on an absence and not on a measurement.
    # 0.0 is reserved for the two abstention classes, where a rule was declined outright;
    # here a rule did fire, but on no transfer evidence at all, so it sits just above them
    # and below the 0.4 a peripheral account with observed transfers earns.
    if r.isolated:
        known = "already known to the investigation" if bool(r.is_seed) else "not a known client"
        return ("peripheral", 0.1,
                f"no transfer observed in either direction in the window, so nothing about this "
                f"account's behaviour is measurable here; depth={int(r.depth)}, {known}")

    # Declared limitation: seed inflow is understated by the crawl design, so any rule
    # that reads in_kzt for a seed is unsound. Seeds are judged on outbound only.
    if r.is_seed and r.in_deg == 0 and r.out_deg > 0:
        return ("peripheral", 0.5,
                f"seed, outbound only: out_deg={int(r.out_deg)}, out={r.out_kzt:,.0f} KZT; "
                f"inflow not observable by collection design")

    if r.truncated_by_depth:
        return ("abstained_boundary", 0.0,
                f"abstained at the crawl boundary: hop 4 with no outgoing edge, so nothing "
                f"downstream was collected; in={r.in_kzt:,.0f} KZT from {_payers(int(r.in_deg))}")

    if r.genuine_terminal:
        return ("terminal", 0.8,
                f"depth={int(r.depth)} < 4 and no outgoing: money arrives and stays; "
                f"in={r.in_kzt:,.0f} KZT over {int(r.in_tx)} transfers from {_payers(int(r.in_deg))}")

    # The four structural rules. Precedence runs widest fan-in first, then widest fan-out,
    # then relay ratio, then two-sided activity, because a node can satisfy more than one and
    # the earlier rule is the stronger claim about it. Each cutoff is justified in THRESHOLDS.
    if r.in_deg >= T["consolidator_min_in_deg"] and (
            pd.isna(r.pass_through) or r.pass_through <= T["consolidator_max_pass_through"]):
        ratio = ("inflow only, no outgoing ratio" if pd.isna(r.pass_through)
                 else f"pass_through={r.pass_through:.2f}")
        return ("consolidator", 0.7,
                f"in_deg={_payers(int(r.in_deg))}, in={r.in_kzt:,.0f} KZT, {ratio}")

    if r.out_deg >= T["distributor_min_out_deg"]:
        return ("distributor", 0.7,
                f"out_deg={int(r.out_deg)} receivers, out={r.out_kzt:,.0f} KZT "
                f"over {int(r.out_tx)} transfers")

    # Dwell time is reported beside the ratio but is not a gate. Only 60 of these 72 nodes
    # move money on within two days, so gating on it would contradict the 72 pass-through
    # nodes the case declares, and 28 of the 72 show a negative dwell because outflow was
    # observed before any inflow was, which is the outbound-only crawl rather than a real
    # ordering. The figure is left in the evidence for an analyst to weigh.
    # Precedence, decided deliberately: `min_tx_for_stable_ratio` sits below this branch
    # rather than above it. The case declares 72 pass-through accounts and this band
    # reproduces that figure exactly; gating transit on the transfer count first would drop
    # it to 45 and contradict a figure the case itself states. 27 of the 72 have one
    # transfer in and one out, so their ratio is a single observation rather than a rate.
    # Those 27 are neither silently promoted nor silently dropped: they keep the role and
    # the evidence below says on its face what the ratio rests on, so an analyst reading
    # the row can discount it without having to re-derive the transfer counts.
    if pd.notna(r.pass_through) and T["transit_pass_through_lo"] <= r.pass_through <= T["transit_pass_through_hi"]:
        dwell = "" if pd.isna(r.dwell_days) else f", dwell={int(r.dwell_days)}d"
        if (r.in_tx + r.out_tx) < T["min_tx_for_stable_ratio"]:
            return ("transit", 0.7,
                    f"pass-through {r.pass_through:.2f} from a single transfer each way, so the "
                    f"ratio is one observation rather than a rate: in={r.in_kzt:,.0f}, "
                    f"out={r.out_kzt:,.0f} KZT{dwell}")
        return ("transit", 0.7,
                f"pass_through={r.pass_through:.2f}: in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT{dwell}")

    if r.in_deg >= T["coordinator_min_in_deg"] and r.out_deg >= T["coordinator_min_out_deg"]:
        return ("coordinator", 0.5,
                f"both sides active: in_deg={int(r.in_deg)}, out_deg={int(r.out_deg)}, "
                f"in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT")

    if (r.in_tx + r.out_tx) < T["min_tx_for_stable_ratio"]:
        return ("abstained_single_observation", 0.0,
                f"abstained on a single observation: in_tx={int(r.in_tx)}, out_tx={int(r.out_tx)}, "
                f"fewer than {T['min_tx_for_stable_ratio']} transfers is not a stable ratio")

    return ("peripheral", 0.4,
            f"no rule threshold met: in_deg={int(r.in_deg)}, out_deg={int(r.out_deg)}, "
            f"in={r.in_kzt:,.0f}, out={r.out_kzt:,.0f} KZT")
