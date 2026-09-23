"""What the crawl could not see, computed rather than disclaimed.

The dataset is the result of a breadth-first crawl that followed OUTBOUND transfers four
hops from 81 seed accounts. Two consequences follow from that design alone, before any
metric is computed:

1. Money arriving INTO the seeds was never followed. An inbound transfer to a seed only
   produces a row when the payer itself was expanded by the crawl, and no account above
   the seeds ever was. Whoever funds the structure is therefore outside the dataset, and
   any confident org chart with a single figure at the top is describing the shape of the
   crawl rather than the shape of the group.
2. A node at hop 4 looks like a terminal but is only the point at which the crawl stopped.
   Treating it as the same object as a node that genuinely received money and sent none is
   a factual error, and the two groups are different sizes.

This module turns both into per-node fields and aggregate figures so that the uncertainty
travels with the evidence instead of sitting in a footnote. Nothing here writes a file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import priority
from .dataio import Dataset
from .roles import THRESHOLDS

# The crawl followed four hops. A node at this depth was recorded but never expanded.
CRAWL_DEPTH_LIMIT = 4

# The five states a node can be in with respect to what the crawl actually observed.
# Evaluated in this order; the first rule that matches wins.
KNOWLEDGE_STATES = [
    "isolated",            # no transfer observed in either direction
    "truncated_at_depth",  # sits at the crawl boundary, onward transfers never collected
    "outbound_only",       # seed, or any node whose payer side was never followed
    "inbound_only",        # money observed arriving, none observed leaving
    "fully_observed",      # both directions traversed inside the crawl
]

# Confidence is a weighted sum of five observation components, each bounded in [0, 1].
# The weights sum to 1.0, so the result is bounded in [0, 1] without any clipping.
# They say how much of the reason to trust a node's role and rank is present in the data.
CONFIDENCE_WEIGHTS = {
    "outbound_enumerated": 0.34,   # did the crawl expand this node and list where money went
    "inbound_observed": 0.26,      # is any payer recorded, and is the payer side followable
    "downstream_resolved": 0.20,   # how much of what is reachable below ends at the boundary
    "evidence_volume": 0.12,       # enough transfers for a ratio to mean anything
    "depth_margin": 0.08,          # distance from the boundary, as a proxy for how much
                                   # of the neighbourhood the crawl could still have reached
}

# A ceiling per state, applied after the weighted sum. Without it an unexpanded hop-4 node
# with a rich inbound side scores respectably, which would misrepresent the one thing that
# actually matters about it: nobody looked at where its money went.
CONFIDENCE_CAPS = {
    "fully_observed": 1.00,
    "inbound_only": 0.85,
    "outbound_only": 0.60,
    "truncated_at_depth": 0.40,
    "isolated": 0.10,
}

# A seed's recorded inbound edges are incidental return traffic from inside the crawl, not
# its funding side, so they earn partial rather than full credit on the inbound component.
SEED_INBOUND_CREDIT = 0.5

# Below this, a node's role and rank should not be read without reading its limitation too.
CONFIDENCE_AUDIT_FLOOR = 0.75

# The priority list an analyst would actually work through on day one.
TOP_LIST_SIZE = 20

# Ranking rule for the next data request: the share of nodes a field would resolve plus the
# share of turnover it would illuminate. Stated here so the ordering is derived from the
# figures and can be recomputed by hand rather than argued about.
REQUEST_RANK_RULE = "share_of_nodes_resolved plus share_of_turnover_illuminated"

# From docs/AGENT-BRIEF.md, verified against the raw data. If a figure below disagrees the
# summary says so in plain words rather than quietly adopting the computed value.
GROUND_TRUTH = {
    "seeds": 81,
    "seeds_isolated": 19,
    "seeds_without_outgoing": 31,
    "dead_ends": 1554,
    "dead_ends_truncated": 444,
    "dead_ends_genuine": 1110,
}

_WEIGHT_SUM = round(sum(CONFIDENCE_WEIGHTS.values()), 6)
assert _WEIGHT_SUM == 1.0, f"CONFIDENCE_WEIGHTS must sum to 1.0, got {_WEIGHT_SUM}"


def build(d: Dataset, feats: pd.DataFrame, roles_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Per-node observation state, the ranked next data request, and the aggregate figures.

    Returns (completeness_df, next_data_request_df, summary_dict).
    """
    df = _assemble(feats, roles_df)
    df = _reachability(d, df)

    df["hop_from_seed"] = df.depth.astype(int)
    df["inbound_known"] = df.in_deg > 0
    df["outbound_known"] = df.hop_from_seed < CRAWL_DEPTH_LIMIT
    df["knowledge_state"] = [_state(r) for r in df.itertuples(index=False)]
    df["confidence"] = [_confidence(r) for r in df.itertuples(index=False)]
    df["limitation"] = [_limitation(r) for r in df.itertuples(index=False)]

    completeness = df[["gid", "knowledge_state", "hop_from_seed", "inbound_known",
                       "outbound_known", "confidence", "limitation"]].copy()
    completeness = completeness.sort_values("gid").reset_index(drop=True)

    summary = _summary(d, df)
    requests = _next_data_request(d, df, summary)
    return completeness, requests, summary


def _assemble(feats: pd.DataFrame, roles_df: pd.DataFrame) -> pd.DataFrame:
    """One frame per node with whatever the caller has already computed, plus a priority score.

    The caller may pass the roles frame before or after ranking. Where the rank is missing it
    is recomputed here with the same function the pipeline uses, so the audit of the top of
    the list is the audit of the real list and not of a second, different one.
    """
    df = feats.copy()
    if roles_df is not None and id(roles_df) != id(feats):
        extra = [c for c in roles_df.columns if c == "gid" or c not in df.columns]
        if "gid" in roles_df.columns and len(extra) > 1:
            df = df.merge(roles_df[extra], on="gid", how="left")
    if "priority_score" not in df.columns:
        if "role" not in df.columns:
            raise ValueError("completeness.build needs a roles frame carrying a role column")
        df, _ = priority.rank(df)
    for col, default in (("in_tx", 0), ("out_tx", 0), ("in_kzt", 0.0), ("out_kzt", 0.0)):
        if col not in df.columns:
            df[col] = default
    return df


def _reachability(d: Dataset, df: pd.DataFrame) -> pd.DataFrame:
    """For each node, how much of what it can reach sits at the crawl boundary.

    A node whose downstream ends mostly at hop 4 has a role that is only as good as the hop
    the crawl stopped on, however clean its own arithmetic looks. Reachability is carried in
    integer bitmasks and iterated to a fixed point because the graph contains cycles, so a
    single topological pass would be wrong.
    """
    gids = df.gid.tolist()
    index = {g: i for i, g in enumerate(gids)}
    n = len(gids)

    successors: list[list[int]] = [[] for _ in range(n)]
    for r in d.edges.itertuples(index=False):
        src, dst = int(r.src), int(r.dst)
        if src in index and dst in index:
            successors[index[src]].append(index[dst])

    bit = [1 << i for i in range(n)]
    boundary_mask = 0
    for g, hop in zip(df.gid, df.depth):
        if int(hop) == CRAWL_DEPTH_LIMIT:
            boundary_mask |= bit[index[g]]

    reach = [0] * n
    # Deepest first converges fastest: most of this graph flows from hop k to hop k+1.
    order = sorted(range(n), key=lambda i: -int(df.depth.iloc[i]))
    while True:
        changed = False
        for v in order:
            merged = reach[v]
            for u in successors[v]:
                merged |= bit[u] | reach[u]
            if merged != reach[v]:
                reach[v] = merged
                changed = True
        if not changed:
            break

    desc, desc_boundary = [], []
    for i in range(n):
        r = reach[i] & ~bit[i]  # a node on a cycle reaches itself; that is not a descendant
        desc.append(r.bit_count())
        desc_boundary.append((r & boundary_mask).bit_count())

    df = df.copy()
    df["descendants"] = desc
    df["descendants_truncated"] = desc_boundary
    share = np.where(np.array(desc) > 0,
                     np.array(desc_boundary) / np.maximum(np.array(desc), 1), 0.0)
    # A node at the boundary has no observed downstream at all, which is unresolved rather
    # than resolved. Anything else with no successors was looked at and found empty.
    at_boundary = (df.depth == CRAWL_DEPTH_LIMIT).to_numpy()
    df["downstream_unresolved"] = np.where(at_boundary, 1.0, share)
    return df


def _state(r) -> str:
    if r.in_deg == 0 and r.out_deg == 0:
        return "isolated"
    if r.hop_from_seed >= CRAWL_DEPTH_LIMIT:
        return "truncated_at_depth"
    # A seed is never fully observed however busy it looks. The crawl started here and only
    # ever followed money outwards, so its payer side is unobservable by construction.
    if r.out_deg > 0 and (bool(r.is_seed) or r.in_deg == 0):
        return "outbound_only"
    if r.out_deg == 0:
        return "inbound_only"
    return "fully_observed"


def _confidence(r) -> float:
    w = CONFIDENCE_WEIGHTS

    outbound = 1.0 if r.outbound_known else 0.0

    if r.in_deg == 0:
        inbound = 0.0
    elif bool(r.is_seed):
        inbound = SEED_INBOUND_CREDIT
    else:
        inbound = 1.0

    downstream = 1.0 - float(r.downstream_unresolved)

    tx = int(r.in_tx) + int(r.out_tx)
    volume = min(1.0, tx / float(THRESHOLDS["min_tx_for_stable_ratio"]))

    margin = (CRAWL_DEPTH_LIMIT - min(int(r.hop_from_seed), CRAWL_DEPTH_LIMIT)) / CRAWL_DEPTH_LIMIT

    score = (w["outbound_enumerated"] * outbound
             + w["inbound_observed"] * inbound
             + w["downstream_resolved"] * downstream
             + w["evidence_volume"] * volume
             + w["depth_margin"] * margin)
    return round(min(score, CONFIDENCE_CAPS[r.knowledge_state]), 3)


def _payers(n: int) -> str:
    return f"{n} payer" if n == 1 else f"{n} payers"


def _limitation(r) -> str:
    state = r.knowledge_state
    unresolved = int(round(float(r.downstream_unresolved) * 100))

    if state == "isolated":
        s = ("No transfer observed in either direction in the window, so nothing about this "
             "account's behaviour is measurable from this dataset.")
    elif state == "truncated_at_depth":
        s = (f"At the four-hop crawl boundary: {r.in_kzt:,.0f} KZT arrived from "
             f"{_payers(int(r.in_deg))} and where it went next was never collected.")
    elif state == "outbound_only":
        seen = (f"{_payers(int(r.in_deg))} appear only as return traffic from inside the crawl"
                if r.in_deg > 0 else "no payer appears at all")
        s = (f"Seed account: money out was followed, money in was not, so its funding is outside "
             f"the dataset ({seen}).")
    elif state == "inbound_only":
        if bool(r.is_seed):
            s = (f"Seed account with no observed outgoing transfer; the "
                 f"{_payers(int(r.in_deg))} visible are return traffic from inside the crawl, "
                 f"not its funding side.")
        else:
            s = (f"{r.in_kzt:,.0f} KZT arrived and none was observed leaving; any payer outside "
                 f"the crawled set would not appear.")
    elif unresolved > 0:
        s = (f"Both directions observed, but {unresolved}% of what is reachable downstream ends "
             f"at the crawl boundary, so the onward path is unknown.")
    else:
        s = ("Both directions observed within the crawl; a payer outside the crawled set would "
             "still not appear in this dataset.")
    return s[:200]


def _summary(d: Dataset, df: pd.DataFrame) -> dict:
    total_nodes = int(len(df))
    turnover = float(d.edges.sum_kzt.sum())

    # Turnover touched by a node is what arrived plus what left. Summed over all nodes this is
    # twice the edge total, because each transfer is touched by its payer and by its receiver.
    df = df.copy()
    df["touched_kzt"] = df.in_kzt + df.out_kzt
    touched_total = float(df.touched_kzt.sum())

    out: dict = {
        "nodes_total": total_nodes,
        "edges_total": int(len(d.edges)),
        "transactions_total": int(len(d.tx)),
        "turnover_kzt": round(turnover, 2),
        "crawl_depth_limit": CRAWL_DEPTH_LIMIT,
        "crawl_direction": "outbound only from the seeds",
    }

    for state in KNOWLEDGE_STATES:
        m = df.knowledge_state == state
        out[f"state_count_{state}"] = int(m.sum())
        out[f"state_node_share_{state}"] = round(float(m.sum()) / total_nodes, 4)
        out[f"state_turnover_share_{state}"] = round(
            float(df.loc[m, "touched_kzt"].sum()) / touched_total, 4) if touched_total else 0.0

    incomplete = df.knowledge_state != "fully_observed"
    out["nodes_incompletely_observed"] = int(incomplete.sum())
    out["nodes_incompletely_observed_share"] = round(float(incomplete.sum()) / total_nodes, 4)
    out["turnover_share_incompletely_observed"] = round(
        float(df.loc[incomplete, "touched_kzt"].sum()) / touched_total, 4) if touched_total else 0.0

    out["confidence_mean"] = round(float(df.confidence.mean()), 3)
    out["confidence_median"] = round(float(df.confidence.median()), 3)
    out["confidence_audit_floor"] = CONFIDENCE_AUDIT_FLOOR
    out["nodes_below_confidence_floor"] = int((df.confidence < CONFIDENCE_AUDIT_FLOOR).sum())
    out["nodes_below_confidence_floor_share"] = round(
        float((df.confidence < CONFIDENCE_AUDIT_FLOOR).sum()) / total_nodes, 4)

    # The number the demo turns on: how much of the list an analyst would work through first
    # is standing on something the crawl did not observe.
    # gid breaks ties so the audited list is the same list on every run.
    top = df.sort_values(["priority_score", "gid"], ascending=[False, True]).head(TOP_LIST_SIZE)
    resting = (top.knowledge_state != "fully_observed") | (top.confidence < CONFIDENCE_AUDIT_FLOOR)
    out["top_list_size"] = int(len(top))
    out["top_nodes_resting_on_incomplete_observation"] = int(resting.sum())
    out["top_nodes_resting_share"] = round(float(resting.sum()) / max(len(top), 1), 4)
    out["top_nodes_that_are_seeds"] = int(top.is_seed.sum())
    out["top_nodes_with_truncated_descendants"] = int((top.descendants_truncated > 0).sum())
    out["top_nodes_mean_downstream_unresolved_share"] = round(
        float(top.downstream_unresolved.mean()), 4)
    out["top_nodes_confidence_mean"] = round(float(top.confidence.mean()), 3)
    out["top_nodes_confidence_min"] = round(float(top.confidence.min()), 3)

    seeds = df[df.is_seed]
    seed_out = float(seeds.out_kzt.sum())
    seed_in = float(seeds.in_kzt.sum())
    unattributed = seed_out - seed_in
    out["seeds_total"] = int(len(seeds))
    out["seeds_isolated"] = int(seeds.isolated.sum()) if "isolated" in seeds.columns else int(
        ((seeds.in_deg == 0) & (seeds.out_deg == 0)).sum())
    out["seeds_without_outgoing"] = int((seeds.out_deg == 0).sum())
    out["seeds_with_incidental_inbound"] = int((seeds.in_deg > 0).sum())
    out["seed_outbound_kzt"] = round(seed_out, 2)
    out["seed_inbound_observed_kzt"] = round(seed_in, 2)
    out["seed_funding_unattributed_kzt"] = round(unattributed, 2)
    out["seed_funding_unattributed_share_of_turnover"] = round(unattributed / turnover, 4) if turnover else 0.0
    out["seed_inbound_crawled"] = 0
    out["seed_funding_visibility"] = (
        "not observable: a transfer into a seed is recorded only if the payer was expanded by "
        "the crawl, and no account above the seeds ever was")
    # Interpolated, not written in: every figure in a generated string comes from the value
    # computed beside it, so a different extract cannot leave a stale number in the prose.
    out["blind_spot_statement"] = (
        f"Inbound transfers to the {out['seeds_total']} seed accounts were never followed, so the "
        f"funding source of the structure lies outside this dataset")

    boundary = df[df.knowledge_state == "truncated_at_depth"]
    out["truncated_nodes"] = int(len(boundary))
    out["truncated_inbound_kzt"] = round(float(boundary.in_kzt.sum()), 2)
    out["truncated_inbound_share_of_turnover"] = round(
        float(boundary.in_kzt.sum()) / turnover, 4) if turnover else 0.0

    dead_ends = df[df.out_deg == 0]
    out["dead_ends_total"] = int(len(dead_ends))
    out["dead_ends_truncated"] = int((dead_ends.depth == CRAWL_DEPTH_LIMIT).sum())
    out["dead_ends_genuine"] = int((dead_ends.depth < CRAWL_DEPTH_LIMIT).sum())

    out["ground_truth_check"] = _ground_truth_check(out)
    return out


def _ground_truth_check(out: dict) -> str:
    """Compare against the brief. A disagreement is reported, never absorbed."""
    computed = {
        "seeds": out["seeds_total"],
        "seeds_isolated": out["seeds_isolated"],
        "seeds_without_outgoing": out["seeds_without_outgoing"],
        "dead_ends": out["dead_ends_total"],
        "dead_ends_truncated": out["dead_ends_truncated"],
        "dead_ends_genuine": out["dead_ends_genuine"],
    }
    bad = [f"{k}: computed {computed[k]}, brief says {v}"
           for k, v in GROUND_TRUTH.items() if computed[k] != v]
    return "agrees with the brief" if not bad else "DISAGREES WITH THE BRIEF: " + "; ".join(bad)


def _next_data_request(d: Dataset, df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    """What to ask for next, ordered by what the present figures say each would buy.

    Every row carries a count of nodes it would move out of an uncertain state and a KZT figure
    it would put an interpretation on. A request the three tables give no way to evaluate is
    kept in the list and marked as such rather than dropped, because a silent omission would
    read as a judgement the data does not support.
    """
    turnover = float(d.edges.sum_kzt.sum())
    total_nodes = int(len(df))
    tx = d.tx

    # Day-level dates leave the order of arrival and departure unresolved whenever both happen
    # on the same calendar day, which is exactly where the transit reading is decided.
    arrivals = tx.groupby(["dst", "date"], as_index=False).sum_kzt.sum().rename(columns={"dst": "gid"})
    departures = tx.groupby(["src", "date"], as_index=False).size().rename(columns={"src": "gid"})
    ambiguous = arrivals.merge(departures[["gid", "date"]], on=["gid", "date"], how="inner")
    ambiguous_nodes = int(ambiguous.gid.nunique())
    ambiguous_kzt = float(ambiguous.sum_kzt.sum())

    # An account whose entire observed life is one calendar day, with money both in and out, is
    # the shape an opening date would settle: purpose-opened, or long-standing and used once.
    first = pd.concat([tx.groupby("src").date.min().rename("a"),
                       tx.groupby("dst").date.min().rename("b")], axis=1).min(axis=1)
    last = pd.concat([tx.groupby("src").date.max().rename("a"),
                      tx.groupby("dst").date.max().rename("b")], axis=1).max(axis=1)
    span_days = (last - first).dt.days
    single_day = set(span_days[span_days == 0].index)
    short_life = df[df.gid.isin(single_day) & (df.in_deg > 0) & (df.out_deg > 0)]
    short_life_nodes = int(len(short_life))
    short_life_kzt = float(short_life.in_kzt.sum())

    rows = [
        {
            "request": (f"One more crawl hop from the {summary['truncated_nodes']:,} nodes at "
                        f"the depth limit"),
            "why": (f"{summary['truncated_nodes']} nodes are dead ends only because the crawl "
                    f"stopped at hop {CRAWL_DEPTH_LIMIT}. {summary['truncated_inbound_kzt']:,.0f} KZT "
                    f"arrives at them and its onward path is unrecorded, so they cannot be told "
                    f"apart from the {summary['dead_ends_genuine']:,} nodes where money "
                    f"genuinely appears to stop."),
            "resolves_nodes": summary["truncated_nodes"],
            "illuminates_kzt": summary["truncated_inbound_kzt"],
            "feasibility_note": ("Same collection method, one hop further. Node count grows with "
                                 "the fan-out already seen at hop 3, so scope the extraction first."),
        },
        {
            "request": "Hour-level timestamps in place of calendar dates",
            "why": (f"{ambiguous_nodes} nodes have at least one day on which money both arrived and "
                    f"left, covering {ambiguous_kzt:,.0f} KZT. At day resolution the order of those "
                    f"movements is unresolved, and dwell time is what separates a node passing funds "
                    f"through from one that happened to transact twice."),
            "resolves_nodes": ambiguous_nodes,
            "illuminates_kzt": round(ambiguous_kzt, 2),
            "feasibility_note": ("The field almost certainly exists in the source ledger and was "
                                 "reduced on export; a re-export would not need a new crawl."),
        },
        {
            "request": (f"Inbound transfers to the {summary['seeds_total']} seed accounts, "
                        f"one hop back"),
            "why": (f"Seeds moved {summary['seed_outbound_kzt']:,.0f} KZT out against "
                    f"{summary['seed_inbound_observed_kzt']:,.0f} KZT observed arriving, leaving "
                    f"{summary['seed_funding_unattributed_kzt']:,.0f} KZT with no recorded payer. "
                    f"This is the only request that can reach above the seeds at all."),
            "resolves_nodes": int(summary["seeds_total"]),
            "illuminates_kzt": summary["seed_funding_unattributed_kzt"],
            "feasibility_note": ("Reverses the crawl direction, so it is a new collection rather "
                                 "than a re-export. The unattributed figure assumes seeds opened "
                                 "the window at zero; the data carries no balances, so read it as "
                                 "the amount without an observed payer, not as proven outside money."),
        },
        {
            "request": "Account opening dates",
            "why": (f"{short_life_nodes} accounts show their whole observed life inside one calendar "
                    f"day with money both in and out, covering {short_life_kzt:,.0f} KZT. An opening "
                    f"date would separate an account opened for the purpose from a long-standing one "
                    f"used once, which the transfer record on its own cannot."),
            "resolves_nodes": short_life_nodes,
            "illuminates_kzt": round(short_life_kzt, 2),
            "feasibility_note": ("A static attribute, cheap to join, but it changes the reading of a "
                                 "small set of nodes rather than the structure. Worth asking for "
                                 "alongside a higher item, not on its own."),
        },
        {
            "request": "Counterparty bank or institution",
            "why": ("Rejected on the present evidence. None of the three tables carries an "
                    "institution, and nothing in gid, depth, date or amount stands in for one, so "
                    "there is no figure here that would change if it arrived. Asking for it would "
                    "be an opinion about what helps, not a finding."),
            "resolves_nodes": 0,
            "illuminates_kzt": 0.0,
            "feasibility_note": ("Unevaluable from this dataset. Keep the request on the list, but "
                                 "rank it only once something in the data shows what it would buy."),
        },
    ]

    for row in rows:
        row["_score"] = (row["resolves_nodes"] / total_nodes
                         + (row["illuminates_kzt"] / turnover if turnover else 0.0))

    out = pd.DataFrame(rows)
    # Deterministic: score descending, then request text as a stable tiebreak.
    out = out.sort_values(["_score", "request"], ascending=[False, True]).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    out["resolves_nodes"] = out.resolves_nodes.astype(int)
    out["illuminates_kzt"] = out.illuminates_kzt.astype(float).round(2)
    return out[["rank", "request", "why", "resolves_nodes", "illuminates_kzt", "feasibility_note"]]
