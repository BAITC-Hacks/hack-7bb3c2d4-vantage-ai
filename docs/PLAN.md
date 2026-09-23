# Money Graph: the build

Rubric, confirmed from the case doc: compliance 25, technical implementation 25, README and
reproducibility 25, value 15, originality 10.

---

## The pipeline as it was actually built

`python3 run.py` is the whole thing. Raw parquet in, thirteen files out, 2.3 seconds measured on
the build machine, against a five-minute budget. The plan that follows this section is the plan; this
section is what came of it.

```
data/*.parquet
  -> dataio.load             graph built from nodes.parquet, never from the edge list
  -> dataio.integrity_report the declared limitations measured rather than assumed
  -> features.build          degrees, flows, pagerank, HITS, pass-through, dwell time
  -> roles.assign            the rule bank, pure Python, no model calls
  -> clusters.assign         Louvain seeded at 42, plus weakly connected components
  -> priority.rank           weighted and documented, gives every node a priority_score
  -> hypotheses.describe     one testable sentence per cluster, from that cluster's figures
  -> flows / exhibits        reciprocal pairs, cycles, resilience, centrality disagreement
  -> formations.build        needs roles and communities, so it runs after clusters.assign
  -> completeness.build      needs priority_score, so it runs after priority.rank
  -> viewdata.write          one graph.json for the review screen
```

The ordering constraint is the only thing that is not free: formations reads the Louvain communities
for its bridge rule, and completeness audits the real priority list rather than a second one it
computes for itself. Both take `feats` as their roles frame, because by that point `feats` carries
the role, the community and the priority score and there is no separate roles table to pass.

### What lands in out/

| File | Rows | What it is |
|---|---:|---|
| `nodes_roles.csv` | 2,248 | Required. One row per declared node, a role and the numbers it fired on. |
| `clusters.csv` | 91 | Required. Communities with a plain-language hypothesis. |
| `top_nodes.csv` | 25 | Required, minimum 20. Ranked priority targets. |
| `formations.csv` | 653 | Ranked structures with their breaking points. See `docs/FORMATIONS.md`. |
| `formation_members.csv` | 4,752 | Who is in each formation and what they do in it. |
| `completeness.csv` | 2,248 | Per-node observation state and confidence. See `docs/COMPLETENESS.md`. |
| `next_data_request.csv` | 5 | What to ask the data owner for next, ranked by what it would resolve. |
| `integrity.json` | - | The measured limitation figures printed at run time. |
| `reciprocal_pairs.csv` | 177 | Optional scoring item. |
| `cycles.csv` | 1,541 | Optional scoring item. |
| `resilience.csv` | 6 | Optional scoring item, the removal test. |
| `pagerank_vs_evidence.csv` | 15 | The false positive exhibit. |
| `graph.json` | - | 2.95 MB, everything the review screen reads. |

`run.py` asserts the row count, the non-empty evidence and the minimum top-list size, and now also
asserts that every formation has members, that every breaking point is a node in the crawl, that
completeness covers all 2,248 nodes and that confidence lies in 0..1. The assertions exist to fail
the run rather than to let a blank panel reach the screen.

### graph.json

The review screen finds two of its tables by record shape rather than by key name, because the
stages that produce them were written separately. `formation_members` is the only top level array
carrying both `formation_id` and `gid`; `node_completeness` is the only one carrying `gid` alongside
`confidence` and `knowledge_state`. Nothing else may be given either shape.

Every client id leaves as a string, including `breaking_point_gid` inside the formations array and
the ids inside `leadChains`. An 18-digit id exceeds `Number.MAX_SAFE_INTEGER`, so two different
accounts compare equal the moment either one is parsed as a number. `viewdata._pyify` casts every
numpy scalar to a Python type on the way out, because `json.dumps` will not, and its `default=`
hook would quietly turn a numpy integer into a JSON string.

### Determinism

The case requires the same input to give the same output. Five consecutive runs now produce
byte-identical files in `out/`, and a copy of the repo with `out/` and every `__pycache__` removed
produces the same thirteen files with the same checksums.

One thing had to be settled to get there. `networkx.hits` computes the two HITS columns with a
sparse SVD, and scipy seeds that solver's starting vector from a fresh generator when the caller
supplies none, so `authority_score` and `hub_score` differed in their last digits between runs and
`nodes_roles.csv` was never the same file twice. The spread was measured at up to 1.4e-15 in
absolute terms. This was first handled downstream, by quantising both columns in `run.py` before
any rule, rank or evidence string read them. That workaround has since been removed in favour of
the tidier fix it pointed at: `features.py` now passes an explicit `nstart` into `nx.hits`, so the
solver starts from a fixed vector and the noise never enters the pipeline at all. Nothing
downstream has to compensate for it any more.

### Open against the real data

Nothing outstanding. Two defects in `tools/figures.py` were recorded here and have since been
fixed: the closing caption on `docs/img/formations.png` was one unwrapped `fig.text` line that
overran the canvas, and the longest row label on that figure reached almost to the left edge.
Both are wrapped and inside the margins now.

---

## Stack: switch to Python. I am reversing my earlier advice.

I told you to stay in TypeScript, on the basis of keeping your scaffold and one runtime. Having read
the full spec, that was the wrong call. Four reasons.

1. **The optional scoring list maps one-to-one onto networkx one-liners.** Cycles and return flows,
   network resilience under removal of the top N nodes, repeated routes, temporal transit. That is
   `simple_cycles`, `articulation_points`, `all_simple_paths`, `immediate_dominators`. In graphology I
   would be hand-rolling most of them, including HITS, which is the single metric that separates
   collectors from distributors on this data.
2. **The starter does the boilerplate and the sanity checks**, including printing the orphan-node
   warning. That is 45 minutes you do not spend.
3. **The organisers recommend Python** and the jury expects it. The technical criterion checks that the
   implementation matches the claimed logic, which is easier to demonstrate in the idiom they read fluently.
4. **The viewer can be anything.** "Веб-страница, ноутбук или desktop, на усмотрение команды." A
   notebook counts. A Flask or FastAPI page counts.

Reproducibility stays one runtime and one command: `pip install -r requirements.txt && python run.py`.

The Node scaffold was built for Track 11 and is one commit of boilerplate. Let it go. Keep the repo,
keep the git history, add a Python tree alongside and delete the Track 11 pieces.

---

## The five things that decide this

### 1. Answer the seven declared limitations by name. 45 minutes. Pays: compliance 25.

The spec says accounting for the declared data defects **is scored**. Give each one a named README
section and the code path that handles it. Nobody structures their README around the organisers' own
defect list.

The headline one: **1,110 genuine terminals versus 444 truncated by crawl depth.** Depth under 4 with no
outgoing means the crawl would have followed them and found nothing, so they are real. Depth 4 means
unknown. A naive rule produces 444 false terminals and the spec says so in advance.

### 2. All 2,248 rows, evidence with numbers, under 200 characters. 20 minutes. Pays: compliance 25.

Build from `nodes.parquet`, left-join metrics. The 19 isolated nodes are seeds with no transfers in the
window: give them their own honest classification. The starter prints this warning, so it is a
correctness check rather than a secret, but it is still the fastest way to fail a row count.

### 3. The gid card, because must-have 3 is a live oral exam. 45 minutes. Pays: compliance, demo.

The jury names three arbitrary gids and you have a minute each to justify the role from your metrics.
Build a screen where Karina types a gid and gets: the role, the rule that fired, the numbers it fired
on, the neighbours, and the path back to a seed. She reads it off the screen rather than reasoning live.

Same component satisfies must-have 5: search by gid, highlight on the diagram, show connections.

### 4. The false positive exhibit. 40 minutes. Pays: technical 25, value 15, originality 10.

PageRank and HITS have zero overlap in their top five. Show a node that ranks top on weighted PageRank,
demonstrate it is a legitimate high-volume hub, and show your evidence score demoting it. Two columns:
what centrality says, what the evidence says.

This is also your answer to "is this a black box", which the spec forbids.

### 5. An abstention class. 30 minutes. Pays: originality, compliance.

The six-role dictionary is a stated minimum and teams may extend it if documented. Add a seventh
outcome for nodes whose signals conflict or that have too few transactions for a stable ratio. Report
the count and the reason.

With no ground truth and scoring on soundness of criteria, a system that states what it cannot tell you
is the strongest available position. It also fits the spec's demand that findings be framed as
hypotheses rather than accusations.

### Then, in order

**6. Clusters that mean something. 30 min.** Raw Louvain gives 70 communities, mostly noise. The 9 with
more than one seed, sizes 142 down to 5, are the story. The 16 weakly connected components are a free
hard structural split. Show both, explain the difference, write a real `hypothesis` per cluster.

**7. Dwell time. 40 min.** 448 of 671 two-way nodes move money within a day. Listed as an optional
scoring item. Needs `transactions.parquet`, which most teams will not open.

**8. Cycles and reciprocity. 25 min.** 177 reciprocal pairs, 1,541 cycles under length 6. Another
optional item, one call.

**9. Network resilience. 30 min.** "Что произойдёт с сетью при изъятии топ-N узлов." Remove your top 10
and report how the giant component fragments. Optional item, and it turns a ranking into an operational
recommendation.

**10. Triage with a cost model. 30 min.** Rank by structural importance times money reachable downstream,
and show score per investigator hour beside raw score.

**Cut first:** anything animated, any embedding method, any ML model.

---

## Two mandatory artefacts people forget

**The solution schema.** One slide or diagram: data to metrics to roles to interface. It is on the
required artefact list. Make it at hour four, export a PNG, commit it.

**The scaling section in the README.** What changes at roughly 1 million nodes. Text only. Say it
honestly: pandas and networkx stop fitting in memory, you move to a columnar store and a graph engine,
PageRank and Louvain become distributed, the per-node LLM explanation becomes a batch job over the top
N rather than all nodes, and the rules themselves do not change because they are thresholds on local
metrics. Four sentences, and almost nobody will write it.

---

## The README, which is 25 points

Organisers' eleven headings, plus these:

1. **Measured timing at the top**, literal stdout from a real run with the three row counts.
2. **A threshold table**: every role, its rule, its numeric cutoff, why that cutoff. In the README, not
   in code comments. Must-have 3 depends on it.
3. **The seven declared limitations**, each with your handling.
4. **What we tried that did not work**, with numbers.
5. **Scaling to 1 million nodes.**
6. **Evaluation philosophy**: no ground truth, so justification rather than accuracy.
7. **Wording**: hypotheses for checking, never assertions of guilt. Check the whole README for this.

---

## Demo, 5 minutes

Live run from raw parquet, timed on screen. The ranked list. Then two or three nodes in substance, which
is what the spec asks for. Then hand Karina the gid box and let the jury pick. Then the false positive.
Then a node the tool refuses to classify.

Open with the line that is actually true and slightly startling: **31 of the 81 clients law enforcement
gave us are dead ends in this data. The network is 2,248 nodes and the people who matter are not on
their list.**

Never say accuracy. Never say guilty.
