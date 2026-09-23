"""Node metrics. Every number a role rule can fire on is computed here and kept in the output."""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from .dataio import Dataset


def build(d: Dataset) -> pd.DataFrame:
    g = d.graph
    df = d.nodes[["gid", "depth", "is_seed"]].copy()

    def m(mapping, default=0):
        return df.gid.map(mapping).fillna(default)

    df["in_deg"] = m(dict(g.in_degree())).astype(int)
    df["out_deg"] = m(dict(g.out_degree())).astype(int)
    df["in_kzt"] = m(dict(g.in_degree(weight="sum_kzt")), 0.0)
    df["out_kzt"] = m(dict(g.out_degree(weight="sum_kzt")), 0.0)
    df["in_tx"] = m(dict(g.in_degree(weight="n_tx"))).astype(int)
    df["out_tx"] = m(dict(g.out_degree(weight="n_tx"))).astype(int)
    df["pagerank"] = m(nx.pagerank(g, weight="sum_kzt"), 0.0)

    # HITS separates who collects from who distributes. PageRank does not, and on this
    # data the two disagree completely in their top ranks.
    hubs, auth = nx.hits(g, max_iter=1000, normalized=True)
    df["hub_score"] = m(hubs, 0.0)
    df["authority_score"] = m(auth, 0.0)

    df["pass_through"] = np.where(df.in_kzt > 0, df.out_kzt / df.in_kzt.replace(0, np.nan), np.nan)

    # Declared limitation: a node at hop 4 with no outgoing edges is where the crawl
    # stopped, not necessarily where the money stopped.
    df["truncated_by_depth"] = (df.depth == 4) & (df.out_deg == 0)
    df["genuine_terminal"] = (df.depth < 4) & (df.out_deg == 0)
    df["isolated"] = (df.in_deg == 0) & (df.out_deg == 0)

    df = df.merge(_dwell(d), on="gid", how="left")
    return df


def _dwell(d: Dataset) -> pd.DataFrame:
    """Days between first money in and first money out. Short dwell is the transit signature."""
    tx = d.tx
    first_in = tx.groupby("dst").date.min().rename("first_in")
    first_out = tx.groupby("src").date.min().rename("first_out")
    j = pd.concat([first_in, first_out], axis=1)
    j["dwell_days"] = (j.first_out - j.first_in).dt.days
    return j.reset_index().rename(columns={"index": "gid"})[["gid", "dwell_days"]]
