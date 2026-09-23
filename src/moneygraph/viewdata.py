"""The payload the review screen reads.

Laid out by hop rather than by force. The case is about how far money travelled from the
clients law enforcement already knew, so hop 0 sits on the left and hop 4 on the right and
every arrow points the way the money moved. A force-directed layout of 2,248 nodes is a
hairball that tells an analyst nothing.

Two of the tables on this payload are located by the review screen from their record shape
rather than from their key name, because the stages that produce them are written
separately. The membership table is recognised by carrying both `formation_id` and `gid`,
and the per-node completeness table by carrying `gid` alongside `confidence` or
`knowledge_state`. No other array here may carry either of those shapes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .dataio import Dataset

# Ordered strongest structural claim first, with the two abstentions last, because the
# legend is read top down and an abstention is a statement about the crawl rather than
# about an account's behaviour.
ROLE_ORDER = ["consolidator", "coordinator", "transit", "distributor",
              "terminal", "peripheral",
              "abstained_boundary", "abstained_single_observation"]

# Columns holding a client id that the name-based rule below does not catch. A bare 18-digit
# number is parsed as a float in JavaScript and two different clients then compare equal, so
# every one of these has to leave as a string.
EXTRA_GID_COLUMNS = ("breaking_point_gid",)

# Extras that arrive already JSON-shaped, with nested lists and every client id a string
# (timeline.days and echoes.records). Rebuilding them as a frame would flatten nothing
# and stringify nothing, so they are cast to plain Python types and passed through.
PASSTHROUGH_EXTRAS = ("days", "echoes")


def _stringify_gids(df: pd.DataFrame, extra: tuple[str, ...] = ()) -> pd.DataFrame:
    """Client ids are 18 digits. JavaScript parses those as floats and loses the last
    digits, which makes two different clients compare equal. They travel as strings."""
    out = df.copy()
    for c in out.columns:
        if c == "gid" or c.startswith("gid_") or c in extra:
            out[c] = out[c].astype("int64").astype(str)
    return out


def _pyify(obj):
    """Cast numpy scalars to Python types before serialising.

    json.dumps does not do this, and the `default=` hook would quietly turn a numpy integer
    into a JSON string, which reaches the screen as a broken figure rather than as an error.
    A non-finite float is emitted as null, because json.dumps writes a bare NaN that
    JSON.parse refuses and the whole screen would fail to boot.
    """
    if isinstance(obj, dict):
        return {str(k): _pyify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_pyify(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_pyify(v) for v in obj.tolist()]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        # Rounded to six places because a sum of tenge amounts can land on a different last
        # binary digit depending on the order pandas adds them, which differs between BLAS
        # builds. Six places is far below any figure the screen shows and keeps graph.json
        # byte identical across machines.
        return round(f, 6) if math.isfinite(f) else None
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, np.str_):
        return str(obj)
    if obj is pd.NaT or (not isinstance(obj, (list, dict)) and pd.isna(obj)):
        return None
    return str(obj)


def _records(df: pd.DataFrame | None, extra_gid: tuple[str, ...] = ()) -> list[dict]:
    """A dataframe as JSON-safe records, every client id a string."""
    if df is None or not len(df):
        return []
    return _pyify(_stringify_gids(df, extra_gid).to_dict(orient="records"))


def write(d: Dataset, feats: pd.DataFrame, top: pd.DataFrame,
          clusters: pd.DataFrame, extras: dict, out_dir: Path,
          formations: pd.DataFrame | None = None,
          membership: pd.DataFrame | None = None,
          completeness: pd.DataFrame | None = None,
          next_data_request: pd.DataFrame | None = None,
          completeness_summary: dict | None = None) -> None:
    g = d.graph

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
        "top": _records(top),
        "clusters": _pyify(clusters.head(30).to_dict(orient="records")),
        # Ranked structures, their breaking points and who is in them. The membership rows
        # are the only array here carrying formation_id and gid together, which is how the
        # screen finds them.
        "formations": _records(formations, EXTRA_GID_COLUMNS),
        "formation_members": _records(membership),
        # Per-node observation state. The only array carrying gid with confidence and
        # knowledge_state, which is the other shape the screen scans for.
        "node_completeness": _records(completeness),
        "next_data_request": _records(next_data_request),
        "completeness_summary": _pyify(completeness_summary or {}),
        **{k: (_pyify(v) if k in PASSTHROUGH_EXTRAS else
               _records(pd.DataFrame(v))
               if isinstance(v, list) and v and isinstance(v[0], dict) else _pyify(v))
           for k, v in extras.items()},
    }
    (out_dir / "graph.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
