# Money Graph

Reconstructing the financial structure of an organised group from a four-hop transfer network.

HackAlem AI 2026, Track 02. Task owner: Freedom.

> Status: work in progress during the competitive window. Role thresholds are first-cut and are being
> tuned against the data. The pipeline, the output schemas and the integrity checks are complete.

---

## 1. Project name

Money Graph.

## 2. Short description

An AML analyst at a second-tier bank receives a list of clients from law enforcement. Those clients are
the bottom of the chain: the couriers who received the money. Who collects it, who passes it on and who
ends up controlling it has to be reconstructed by hand, at hours of work per node.

This takes the outbound-transfer crawl from those clients, assigns every node in the resulting network a
role with the numbers behind it, groups the network into clusters, and ranks who to investigate first.

**Built for:** an analyst in a bank's financial monitoring unit.

**What changes:** the focus of an investigation moves off the 81 known couriers and onto the points of
consolidation above them, in seconds rather than weeks.

## 3. What has been implemented

_Updated at each commit. Only what runs is listed here._

**Working end to end**
- One-command pipeline from raw parquet to the three required CSVs, currently **1.1 s** against the
  5-minute limit.
- All **2,248** declared nodes receive a role, a role score and evidence containing numbers.
- Integrity report measuring every declared data limitation, written to `out/integrity.json`.
- Clustering, with a cluster id on every node, plus weakly connected components as a second view.
- Ranked priority list of 25 nodes with written justification.
- Review screen with search by gid and a per-node card.

**Not yet implemented**
- Network diagram with flow direction and role highlighting.
- Cluster hypotheses (`clusters.csv` `hypothesis` column is currently empty).
- Cycle and reciprocity detection, network resilience under node removal.

## 4. How the solution works

1. Load `edges`, `nodes` and `transactions` parquet. The graph is built from `nodes.parquet`, so nodes
   with no transfers are not silently lost.
2. Measure the declared limitations and print them.
3. Compute per-node metrics: degrees, flows, transfer counts, weighted PageRank, HITS hub and authority
   scores, pass-through ratio, dwell time.
4. Apply the rule bank in precedence order. Each rule is a numeric threshold and returns the figures it
   fired on as the node's evidence.
5. Cluster, rank, write three CSVs.

## 5. Technologies

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Data | pandas, pyarrow |
| Graph | networkx |
| Review screen | plain HTML and ES modules, no build step, served from the standard library |

No model is called in the classification path. Roles come from the rule bank in `src/moneygraph/roles.py`.

## 6. Project architecture

```
data/*.parquet
  -> dataio.load             graph from nodes.parquet, not the edge list
  -> dataio.integrity_report declared limitations, measured
  -> features.build          degrees, flows, pagerank, HITS, pass-through, dwell
  -> roles.assign            rule bank, pure Python
  -> clusters.assign         Louvain + weakly connected components
  -> priority.rank           weighted and documented
  -> out/*.csv, web/         three CSVs and the review screen
```

## 7. Installation and launch

```bash
git clone https://github.com/BAITC-Hacks/hack-7bb3c2d4-vantage-ai
cd hack-7bb3c2d4-vantage-ai
pip install -r requirements.txt
python run.py --data ./data --out ./out
```

Add `--serve` to open the review screen on `http://localhost:8000/web/`.

No environment variables are required. No network access is required.

## 8. How to test the solution

```bash
python run.py --data ./data --out ./out
```

Expected: three files in `out/`, `nodes_roles.csv` with exactly 2,248 rows, `top_nodes.csv` with at
least 20, and a completion time well under five minutes. The run asserts all three and fails loudly
otherwise.

_A worked example for two or three specific gids will be added here._

## 9. Data and integrations

Organiser-provided dataset only: 2,248 nodes, 3,119 edges, 4,840 transactions, July 2026, 365,890,012
KZT of turnover in the graph. Anonymised; `gid` is a synthetic identifier with no link to a person. No
external sources, no third-party data, no enrichment.

Third-party libraries: pandas, pyarrow, networkx, numpy, all open source and listed in
`requirements.txt`. `docs/starter-reference.py` is the organisers' starter code, kept for reference.

## 10. Limitations

The case specification declares these, and the pipeline measures each one rather than assuming it.

| Limitation | Measured | How it is handled |
|---|---|---|
| Crawl stops at hop 4 | 444 nodes | Classified `unclassified`, never `terminal`. Genuine terminals at depth below 4: **1,110** |
| Outbound transfers only | | A node's true balance is not computable and is not claimed |
| Seed inflow understated | 19 seeds in no edge, 31 with no outgoing | Seeds are never scored on inflow |
| 5,000 KZT collection floor | | Structuring below the floor is undetectable and is not claimed |
| Network is not monolithic | 16 components in the edge graph, 35 including isolated nodes | Component id retained alongside cluster id |
| No client attributes | | Structure and amounts only |
| No ground truth | | Roles are justified by stated rules, not measured against labels |

Findings are signals for an analyst to check, not conclusions about any person.

## 11. Link to the deployed version

Runs locally. See section 7.

---

## Role rules and thresholds

_Kept in step with `THRESHOLDS` in `src/moneygraph/roles.py`. First-cut values, being tuned._

| Role | Rule | Threshold |
|---|---|---|
| terminal | no outgoing transfers and depth below 4 | crawl would have continued and found nothing |
| unclassified | depth 4 with no outgoing, or fewer than 3 transfers total | crawl boundary, or too little to judge |
| consolidator | receives from many distinct payers and retains most of it | in_deg >= 8, pass_through <= 0.5 |
| distributor | fans out to many receivers | out_deg >= 20 |
| transit | passes on what it receives, quickly | pass_through 0.8 to 1.2 |
| coordinator | active on both sides | in_deg >= 4 and out_deg >= 4 |
| peripheral | no threshold met | |

## Scaling to roughly 1 million nodes

The rules do not change, because they are thresholds on local metrics. What changes is the substrate.
pandas and an in-memory networkx graph stop fitting, so the edge and transaction tables move to a
columnar store and the graph to an engine that keeps it off-heap. PageRank, HITS and community
detection become distributed or approximate. Dwell time and pass-through stay cheap because they are
per-node aggregations. Any natural-language explanation becomes a batch job over the ranked top N
rather than every node.
