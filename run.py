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
                        flows, hypotheses, exhibits, viewdata,
                        formations, completeness)

REQUIRED_NODE_COLUMNS = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]

FORMATION_COLUMNS = ["formation_id", "kind", "n_members", "n_seeds", "kzt_through",
                     "breaking_point_gid", "breaking_point_method", "breaking_point_effect",
                     "score", "rank", "hypothesis", "evidence"]
COMPLETENESS_COLUMNS = ["gid", "knowledge_state", "confidence", "limitation"]

# What web/index.html reads before it can draw anything at all: the header counts, the
# chart, its edges, the priority list and the community table.
GRAPH_JSON_KEYS = ["meta", "nodes", "edges", "top", "clusters"]


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

    # feats carries the role, the community and the priority score by this point, so it is
    # the roles frame and the features frame both. Formations need the communities, which
    # clusters.assign wrote; completeness needs the priority score, which priority.rank did.
    formations_df, membership_df = formations.build(d, feats, feats, cluster_table)
    completeness_df, next_request_df, completeness_summary = completeness.build(d, feats, feats)

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
    formations_df.to_csv(out_dir / "formations.csv", index=False)
    membership_df.to_csv(out_dir / "formation_members.csv", index=False)
    completeness_df.to_csv(out_dir / "completeness.csv", index=False)
    next_request_df.to_csv(out_dir / "next_data_request.csv", index=False)

    viewdata.write(d, feats, top, cluster_table, {
        "resilience": resil.to_dict(orient="records"),
        "demoted": demoted.head(8).to_dict(orient="records"),
        "reciprocal": recips.head(20).to_dict(orient="records"),
        "cycles": loops.head(20).to_dict(orient="records"),
        # Strings, not integers: an 18-digit id loses its last digits in JavaScript.
        "leadChains": [[str(x) for x in p] for p in lead_chains],
        "integrity": report,
    }, out_dir,
        formations=formations_df,
        membership=membership_df,
        completeness=completeness_df,
        next_data_request=next_request_df,
        completeness_summary=completeness_summary)

    # The case requires exactly one row per declared node. Fail loudly, not silently.
    assert len(nodes_roles) == report["nodes_declared"], (
        f"nodes_roles.csv has {len(nodes_roles)} rows, expected {report['nodes_declared']}")
    assert nodes_roles.evidence.str.len().gt(0).all(), "every node needs non-empty evidence"
    assert len(top) >= 20, "top_nodes.csv needs at least 20 rows"
    assert len(cluster_table) > 0, "clusters.csv has no rows"
    assert cluster_table.hypothesis.str.len().gt(0).all(), (
        "every cluster needs a non-empty hypothesis")

    # The optional scoring items from the case specification. An empty file here would still
    # satisfy every check above, and the review screen would draw the panel as absent rather
    # than as broken, so each one is required to exist and to carry rows.
    for name, frame in (("resilience.csv", resil), ("reciprocal_pairs.csv", recips),
                        ("pagerank_vs_evidence.csv", demoted), ("cycles.csv", loops)):
        assert (out_dir / name).exists(), f"{name} was not written"
        assert len(frame) > 0, f"{name} has no rows"

    # graph.json is the only input the review screen has. Malformed or short a key, the page
    # fails in the browser at the demo rather than here, so it is parsed back and checked.
    graph_json = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
    assert not set(GRAPH_JSON_KEYS) - set(graph_json), (
        f"graph.json is missing {sorted(set(GRAPH_JSON_KEYS) - set(graph_json))}")

    # The same contract for the two stages added after the three required outputs. A
    # formation with no members, or a node with no observation state, would reach the
    # review screen as a blank panel rather than as a failure, so it is caught here.
    assert len(formations_df) > 0, "formations.csv has no rows"
    assert not set(FORMATION_COLUMNS) - set(formations_df.columns), (
        f"formations.csv is missing {sorted(set(FORMATION_COLUMNS) - set(formations_df.columns))}")
    assert formations_df.formation_id.is_unique, "formation_id must identify one formation"
    assert len(membership_df) > 0, "formation_members.csv has no rows"
    assert set(membership_df.formation_id) == set(formations_df.formation_id), (
        "every formation needs members and every member row needs a formation")
    assert formations_df.breaking_point_gid.isin(set(d.nodes.gid)).all(), (
        "a breaking point must be a node in the crawl")
    assert len(completeness_df) == report["nodes_declared"], (
        f"completeness.csv has {len(completeness_df)} rows, expected {report['nodes_declared']}")
    assert not set(COMPLETENESS_COLUMNS) - set(completeness_df.columns), (
        f"completeness.csv is missing "
        f"{sorted(set(COMPLETENESS_COLUMNS) - set(completeness_df.columns))}")
    assert completeness_df.confidence.between(0, 1).all(), "confidence must lie in 0..1"
    assert completeness_df.limitation.str.len().gt(0).all(), "every node needs a limitation"
    assert len(next_request_df) > 0, "next_data_request.csv has no rows"

    elapsed = time.time() - t0
    print(f"\nnodes_roles.csv       {len(nodes_roles):>6} rows")
    print(f"clusters.csv          {len(cluster_table):>6} rows")
    print(f"top_nodes.csv         {len(top):>6} rows")
    print(f"formations.csv        {len(formations_df):>6} rows")
    print(f"formation_members.csv {len(membership_df):>6} rows")
    print(f"completeness.csv      {len(completeness_df):>6} rows")
    print(f"next_data_request.csv {len(next_request_df):>6} rows")
    print(f"\nrole distribution:\n{nodes_roles.role.value_counts().to_string()}")
    print(f"\nformations by kind:\n{formations_df.kind.value_counts().to_string()}")
    print(f"\nreciprocal pairs   {len(recips):>6}")
    print(f"cycles <= 6 hops   {len(loops):>6}")
    print("\nnetwork after removing the top ranked nodes:")
    print(resil.to_string(index=False))
    print("\nwhat the crawl could not see:")
    print(f"  nodes not fully observed         "
          f"{completeness_summary['nodes_incompletely_observed']} "
          f"({completeness_summary['nodes_incompletely_observed_share']:.2%})")
    print(f"  seed funding with no payer       "
          f"{completeness_summary['seed_funding_unattributed_kzt']:,.0f} KZT "
          f"({completeness_summary['seed_funding_unattributed_share_of_turnover']:.2%} of turnover)")
    print(f"  top {completeness_summary['top_list_size']} resting on incomplete data    "
          f"{completeness_summary['top_nodes_resting_on_incomplete_observation']}")
    print(f"  ground truth check               {completeness_summary['ground_truth_check']}")
    print(f"\ncompleted in {elapsed:.2f} s")

    if a.serve:
        from moneygraph.serve import serve
        serve(out_dir, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
