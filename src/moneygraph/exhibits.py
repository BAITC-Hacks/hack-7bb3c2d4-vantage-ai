"""Where a plain centrality ranking and an evidence-based ranking disagree.

PageRank answers "which node does flow concentrate on". It does not distinguish a node
collecting from many payers from a node paying many suppliers. On this data the two
rankings share nothing at the top, so the disagreement is worth showing rather than
hiding behind a single number.
"""
from __future__ import annotations

import pandas as pd


def pagerank_vs_evidence(feats: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    df = feats.copy()
    df["rank_pagerank"] = df.pagerank.rank(ascending=False, method="min").astype(int)
    df["rank_priority"] = df.priority_score.rank(ascending=False, method="min").astype(int)
    df["rank_gap"] = df.rank_pagerank - df.rank_priority

    # Nodes a pure centrality ranking would put near the top that the rules demote.
    demoted = df[df.rank_pagerank <= top_n].nsmallest(top_n, "rank_gap")
    cols = ["gid", "role", "rank_pagerank", "rank_priority", "rank_gap",
            "in_deg", "out_deg", "in_kzt", "out_kzt", "pass_through", "evidence"]
    return demoted[cols].sort_values("rank_pagerank").reset_index(drop=True)
