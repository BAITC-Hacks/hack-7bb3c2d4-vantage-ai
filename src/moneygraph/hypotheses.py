"""Cluster hypotheses, written from the cluster's own figures.

The case requires a hypothesis per cluster. It is generated from the composition of the
cluster so that every phrase can be checked against the numbers in the same row, and it
is worded as something for an analyst to test rather than a finding about a person.
"""
from __future__ import annotations

import pandas as pd


def describe(clusters: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    out = clusters.copy()
    notes = []
    for r in out.itertuples(index=False):
        members = feats[feats.cluster_id == r.cluster_id]
        counts = members.role.value_counts().to_dict()
        notes.append(_phrase(r, counts))
    out["hypothesis"] = notes
    return out


def _phrase(r, counts: dict) -> str:
    cons = counts.get("consolidator", 0)
    trans = counts.get("transit", 0)
    dist = counts.get("distributor", 0)
    term = counts.get("terminal", 0)

    if r.n_nodes <= 2:
        return "Too small to characterise; check whether it belongs to a larger structure."
    if r.n_seed == 0:
        return (f"No known client in this group of {r.n_nodes}; reached only indirectly. "
                f"Check how it connects to the case before spending time on it.")

    parts = []
    if cons:
        parts.append(f"{cons} node(s) showing signs of consolidation")
    if trans:
        parts.append(f"{trans} passing funds straight through")
    if dist:
        parts.append(f"{dist} distributing to many receivers")
    if term:
        parts.append(f"{term} where funds appear to stop")

    shape = ", ".join(parts) if parts else "no node meeting a role threshold"
    return (f"{r.n_nodes} nodes around {r.n_seed} known client(s), "
            f"{r.sum_kzt_internal:,.0f} KZT moving inside the group: {shape}. "
            f"Worth checking whether the collection points here serve the same group.")
