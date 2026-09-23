#!/usr/bin/env python3
"""One command, raw parquet to the three required CSVs.

    python run.py --data ./data --out ./out

Add --serve to open the review screen on http://localhost:8000 afterwards.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from moneygraph import dataio, features, roles, clusters, priority  # noqa: E402

REQUIRED_NODE_COLUMNS = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./data")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--serve", action="store_true", help="serve the review screen when finished")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()

    t0 = time.time()
    data_dir, out_dir = Path(a.data), Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    d = dataio.load(data_dir)
    report = dataio.integrity_report(d)
    print("=" * 68)
    print("DATA INTEGRITY")
    print("=" * 68)
    for k, v in report.items():
        print(f"  {k:<32} {v}")
    print("=" * 68)

    feats = features.build(d)
    feats = roles.assign(feats)
    feats, cluster_table = clusters.assign(d, feats)
    feats, top = priority.rank(feats)

    nodes_roles = feats[REQUIRED_NODE_COLUMNS + [
        "in_deg", "out_deg", "in_kzt", "out_kzt", "in_tx", "out_tx",
        "pagerank", "authority_score", "hub_score", "pass_through", "dwell_days",
        "depth", "is_seed", "truncated_by_depth", "genuine_terminal", "component_id",
    ]]
    nodes_roles.to_csv(out_dir / "nodes_roles.csv", index=False)
    cluster_table.to_csv(out_dir / "clusters.csv", index=False)
    top.to_csv(out_dir / "top_nodes.csv", index=False)
    (out_dir / "integrity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # The case requires exactly one row per declared node. Fail loudly, not silently.
    assert len(nodes_roles) == report["nodes_declared"], (
        f"nodes_roles.csv has {len(nodes_roles)} rows, expected {report['nodes_declared']}")
    assert nodes_roles.evidence.str.len().gt(0).all(), "every node needs non-empty evidence"
    assert len(top) >= 20, "top_nodes.csv needs at least 20 rows"

    elapsed = time.time() - t0
    print(f"\nnodes_roles.csv  {len(nodes_roles):>6} rows")
    print(f"clusters.csv     {len(cluster_table):>6} rows")
    print(f"top_nodes.csv    {len(top):>6} rows")
    print(f"\nrole distribution:\n{nodes_roles.role.value_counts().to_string()}")
    print(f"\ncompleted in {elapsed:.2f} s")

    if a.serve:
        from moneygraph.serve import serve
        serve(out_dir, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
