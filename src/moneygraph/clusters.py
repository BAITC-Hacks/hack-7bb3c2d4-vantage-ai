"""Clustering.

Two views. Weakly connected components are a hard structural split that needs no
algorithm. Louvain on the undirected projection gives soft communities, and the
projection discards direction, which is stated rather than hidden.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .dataio import Dataset


def assign(d: Dataset, feats: pd.DataFrame, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    g = d.graph
    u = nx.Graph()
    u.add_nodes_from(g.nodes)
    for a, b, at in g.edges(data=True):
        if u.has_edge(a, b):
            u[a][b]["w"] += at["sum_kzt"]
        else:
            u.add_edge(a, b, w=at["sum_kzt"])

    communities = nx.community.louvain_communities(u, weight="w", seed=seed)
    cid = {n: i for i, c in enumerate(communities) for n in c}
    feats = feats.copy()
    feats["cluster_id"] = feats.gid.map(cid).fillna(-1).astype(int)

    wcc = {n: i for i, c in enumerate(
        sorted(nx.weakly_connected_components(g), key=len, reverse=True)) for n in c}
    feats["component_id"] = feats.gid.map(wcc).fillna(-1).astype(int)

    rows = []
    for c, grp in feats.groupby("cluster_id"):
        gids = set(grp.gid)
        internal = sum(at["sum_kzt"] for a, b, at in g.edges(data=True)
                       if a in gids and b in gids)
        top = grp.nlargest(5, "in_kzt").gid.tolist()
        rows.append({
            "cluster_id": c,
            "n_nodes": len(grp),
            "n_seed": int(grp.is_seed.sum()),
            "sum_kzt_internal": round(internal, 2),
            "top_gids": " ".join(str(x) for x in top),
            # Declared here so the column exists in a fixed position and left empty on
            # purpose: a hypothesis needs the role mix of the cluster, which is not known
            # until roles and communities have both been assigned. hypotheses.describe
            # fills every row from that cluster's own figures once run.py has both.
            "hypothesis": "",
        })
    clusters = pd.DataFrame(rows).sort_values(
        ["n_seed", "sum_kzt_internal"], ascending=False).reset_index(drop=True)
    return feats, clusters
