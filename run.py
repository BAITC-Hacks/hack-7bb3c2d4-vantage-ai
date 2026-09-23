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

from moneygraph import (dataio, features, roles, clusters, priority,  # noqa: E402
                        flows, hypotheses, exhibits, viewdata)

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
    cluster_table = hypotheses.describe(cluster_table, feats)

    # Optional scoring items from the case specification, each an exact computation.
    ranked_ids = top.gid.tolist()
    recips = flows.reciprocal_pairs(d)
    loops = flows.cycles(d)
    resil = flows.resilience(d, ranked_ids)
    demoted = exhibits.pagerank_vs_evidence(feats)
    lead = int(top.iloc[0].gid)
    lead_chains = flows.chains_from_seeds(d, lead)

    nodes_roles = feats[REQUIRED_NODE_COLUMNS + [
        "in_deg", "out_deg", "in_kzt", "out_kzt", "in_tx", "out_tx",
        "pagerank", "authority_score", "hub_score", "pass_through", "dwell_days",
        "depth", "is_seed", "truncated_by_depth", "genuine_terminal", "component_id",
    ]]
    nodes_roles.to_csv(out_dir / "nodes_roles.csv", index=False)
    cluster_table.to_csv(out_dir / "clusters.csv", index=False)
    top.to_csv(out_dir / "top_nodes.csv", index=False)
    (out_dir / "integrity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    recips.to_csv(out_dir / "reciprocal_pairs.csv", index=False)
    loops.to_csv(out_dir / "cycles.csv", index=False)
    resil.to_csv(out_dir / "resilience.csv", index=False)
    demoted.to_csv(out_dir / "pagerank_vs_evidence.csv", index=False)

    viewdata.write(d, feats, top, cluster_table, {
        "resilience": resil.to_dict(orient="records"),
        "demoted": demoted.head(8).to_dict(orient="records"),
        "reciprocal": recips.head(20).to_dict(orient="records"),
        "cycles": loops.head(20).to_dict(orient="records"),
        "leadChains": [[int(x) for x in p] for p in lead_chains],
        "integrity": report,
    }, out_dir)

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
    print(f"\nreciprocal pairs   {len(recips):>6}")
    print(f"cycles <= 6 hops   {len(loops):>6}")
    print("\nnetwork after removing the top ranked nodes:")
    print(resil.to_string(index=False))
    print(f"\ncompleted in {elapsed:.2f} s")

    if a.serve:
        from moneygraph.serve import serve
        serve(out_dir, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
