"""Loading and integrity checks.

Every declared limitation from the case specification is detected here rather than
assumed, so the numbers in the README come from the data and not from the brief.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import pandas as pd


@dataclass
class Dataset:
    edges: pd.DataFrame
    nodes: pd.DataFrame
    tx: pd.DataFrame
    graph: nx.DiGraph

    @property
    def seeds(self) -> set[int]:
        return set(self.nodes.loc[self.nodes.is_seed, "gid"])


def load(data_dir: Path) -> Dataset:
    edges = pd.read_parquet(data_dir / "edges.parquet")
    nodes = pd.read_parquet(data_dir / "nodes.parquet")
    tx = pd.read_parquet(data_dir / "transactions.parquet")
    tx["date"] = pd.to_datetime(tx["date"])

    g = nx.DiGraph()
    # Nodes come from nodes.parquet, NOT from the edge list. 19 of the 81 seeds
    # appear in no edge at all; building from edges silently drops them and the
    # required output would have 2229 rows instead of 2248.
    for r in nodes.itertuples(index=False):
        g.add_node(int(r.gid), depth=int(r.depth), is_seed=bool(r.is_seed))
    for r in edges.itertuples(index=False):
        g.add_edge(int(r.src), int(r.dst),
                   sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    return Dataset(edges=edges, nodes=nodes, tx=tx, graph=g)


def integrity_report(d: Dataset) -> dict:
    """Measured facts about the declared limitations. Printed at run time and quoted in the README."""
    g, nodes, edges, tx = d.graph, d.nodes, d.edges, d.tx
    in_edges = set(edges.src) | set(edges.dst)
    seeds = d.seeds
    out_deg = dict(g.out_degree())
    depth = dict(zip(nodes.gid, nodes.depth))

    dead_ends = [n for n in g.nodes if out_deg.get(n, 0) == 0]
    truncated = [n for n in dead_ends if depth.get(n) == 4]
    genuine = [n for n in dead_ends if depth.get(n, 9) < 4]

    agg = tx.groupby(["src", "dst"]).sum_kzt.agg(["sum", "size"]).reset_index()
    merged = edges.merge(agg, on=["src", "dst"], how="outer", indicator=True)

    return {
        "nodes_declared": len(nodes),
        "nodes_in_graph": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "transactions": len(tx),
        "turnover_kzt": float(edges.sum_kzt.sum()),
        "period": (str(tx.date.min().date()), str(tx.date.max().date())),
        "seeds": len(seeds),
        "seeds_absent_from_edges": len(seeds - in_edges),
        "seeds_without_outgoing": sum(1 for s in seeds if out_deg.get(s, 0) == 0),
        "dead_ends": len(dead_ends),
        "dead_ends_truncated_depth4": len(truncated),
        "dead_ends_genuine": len(genuine),
        "weakly_connected_components": nx.number_weakly_connected_components(g),
        "edges_match_transactions": bool((merged._merge == "both").all()),
    }
