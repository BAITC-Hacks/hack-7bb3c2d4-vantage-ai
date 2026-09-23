"""The payload the review screen reads.

Laid out by hop rather than by force. The case is about how far money travelled from the
clients law enforcement already knew, so hop 0 sits on the left and hop 4 on the right and
every arrow points the way the money moved. A force-directed layout of 2,248 nodes is a
hairball that tells an analyst nothing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .dataio import Dataset

ROLE_ORDER = ["consolidator", "coordinator", "transit", "distributor",
              "terminal", "peripheral", "unclassified"]


def _stringify_gids(df: pd.DataFrame) -> pd.DataFrame:
    """Client ids are 18 digits. JavaScript parses those as floats and loses the last
    digits, which makes two different clients compare equal. They travel as strings."""
    out = df.copy()
    for c in out.columns:
        if c == "gid" or c.startswith("gid_"):
            out[c] = out[c].astype("int64").astype(str)
    return out


def write(d: Dataset, feats: pd.DataFrame, top: pd.DataFrame,
          clusters: pd.DataFrame, extras: dict, out_dir: Path) -> None:
    g = d.graph
    f = feats.set_index("gid")

    # Vertical position inside a hop: group by cluster so related accounts sit together,
    # then by priority so the nodes that matter are near the top of the band.
    order = (feats.sort_values(["depth", "cluster_id", "priority_score"],
                               ascending=[True, True, False])
                  .groupby("depth").cumcount())
    feats = feats.assign(slot=order.values)
    depth_counts = feats.groupby("depth").size().to_dict()

    nodes = []
    for r in feats.itertuples(index=False):
        nodes.append({
            "id": str(r.gid),  # 18-digit ids exceed JS safe integers; keep them strings
            "hop": int(r.depth),
            "y": (r.slot + 0.5) / max(depth_counts[r.depth], 1),
            "role": r.role,
            "cluster": int(r.cluster_id),
            "component": int(r.component_id),
            "seed": bool(r.is_seed),
            "priority": round(float(r.priority_score), 4),
            "inKzt": float(r.in_kzt), "outKzt": float(r.out_kzt),
            "inDeg": int(r.in_deg), "outDeg": int(r.out_deg),
            "evidence": r.evidence,
            "roleScore": float(r.role_score),
        })

    edges = [{"s": str(a), "t": str(b), "kzt": float(at["sum_kzt"]), "n": int(at["n_tx"])}
             for a, b, at in g.edges(data=True)]

    payload = {
        "meta": {
            "nodes": len(nodes), "edges": len(edges),
            "turnover": float(d.edges.sum_kzt.sum()),
            "seeds": len(d.seeds),
            "roleOrder": ROLE_ORDER,
            "roleCounts": feats.role.value_counts().to_dict(),
        },
        "nodes": nodes,
        "edges": edges,
        "top": _stringify_gids(top).to_dict(orient="records"),
        "clusters": clusters.head(30).to_dict(orient="records"),
        **{k: (_stringify_gids(pd.DataFrame(v)).to_dict(orient="records")
               if isinstance(v, list) and v and isinstance(v[0], dict) else v)
           for k, v in extras.items()},
    }
    (out_dir / "graph.json").write_text(
        json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")
