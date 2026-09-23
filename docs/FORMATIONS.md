# Formations

A ranked account is a name. An investigator cannot act on a name, they act on a structure.

A **formation** is a set of accounts that only makes sense when read together: a collection
point with the payers feeding it, a transit run, a pair recycling funds, a dispersal point,
or one account that an entire part of a community depends on. `src/moneygraph/formations.py`
groups the 2,248 nodes into formations, measures each one, ranks them, and names the single
member whose removal takes the most of the structure with it.

A node may belong to several formations at once. That is expected: an account can be the
collection point of a funnel and the distributor of a fan-out in the same week. Only an
identical pair of (kind, member set) is treated as a duplicate and collapsed.

```python
from moneygraph import formations
formations_df, membership_df = formations.build(d, feats, roles_df, clusters_df)
```

The module returns dataframes and writes nothing. Writing files is `run.py`'s job.

## The five kinds

Every rule is a threshold in `RULES` at the top of the module. Nothing is duplicated in the
code, so changing a number here changes the rule and this table together.

| Kind | Rule, in one sentence | Thresholds |
|---|---|---|
| `funnel` | A collection point and every payer that sends it at least half of everything that payer sends. | `funnel_min_feeders=3`, `funnel_min_feeder_share=0.5` |
| `chain` | Two or more consecutive accounts that each forward at least half of what arrived and are not hubs, extended by the payer before the run and the receiver after it. | `chain_min_forward_share=0.5`, `chain_max_interior_degree=3`, `chain_min_interior=2`, `chain_min_members=3` |
| `reciprocal_loop` | A pair that sends money both ways, or a cycle of up to four accounts that returns funds to where they started. | `loop_max_cycle_len=4`, `loop_min_returned_share=0.05` |
| `fan_out` | A distributor and the eight or more receivers it pays that show no onward transfer in the window. | `fanout_min_terminals=8` |
| `bridge` | A cut vertex of a community of twelve or more, together with the side of that community that reaches the rest only through it. | `bridge_min_community=12`, `bridge_min_detached=3` |

Reciprocal pairs and cycles are taken from `flows.reciprocal_pairs` and `flows.cycles`
rather than recomputed, so the loop formations and `out/reciprocal_pairs.csv` cannot drift.

On the July 2026 crawl the five rules produce **653 formations**: 377 reciprocal loops,
172 bridges, 51 chains, 45 fan-outs and 8 funnels. Membership covers 1,964 of the 2,248
nodes across 4,752 rows, and 1,421 nodes sit in more than one formation.

Funnels being rare is a result, not a gap. Only eight accounts in the whole crawl are paid
by three or more accounts that send them a dominant share of their outflow. The highest
in-degree node in the network receives from 24 payers, but 21 of those send it less than
40% of what they send in total, so it is a busy account rather than a collection point.

## The breaking point

For each formation the module names one member, the method that found it, and the effect as
a number. Three methods, in this order of preference.

1. **`dominator`.** Where the formation is directed and rooted, `networkx.immediate_dominators`
   is run from the entry node and the winner is the member that dominates the most other
   members, meaning it sits on every route from the entry to them. A funnel is rooted at its
   collection point but the money runs the other way, so a funnel is analysed on the reversed
   subgraph. The effect is **how many members become unreachable from the entry**.
2. **`articulation`.** Where no member dominates another, articulation points of the
   undirected projection of the formation are computed, and the winner is the one whose
   removal leaves the most members disconnected from the entry. The effect is again **how
   many members become unreachable from the entry**. For a `bridge` this method is what
   found the formation in the first place, so the cut vertex is its breaking point by
   construction and the effect is the whole detached side.
3. **`flow`.** A loop has neither a dominator nor a cut vertex: remove any member and the
   rest still reach each other. The question then becomes how much money stops rather than
   how many accounts are cut off, so the winner is the member carrying the most KZT on
   internal edges and the effect is **that amount in KZT**.

The `breaking_point_method` column tells you which unit `breaking_point_effect` is in:
members for `dominator` and `articulation`, KZT for `flow`. Across the 653 formations the
methods fire 49, 225 and 379 times respectively.

`fragility` is the unit free version used in the score: the share of the formation the
breaking point takes with it, either `effect / (n_members - 1)` or, for the `flow` method,
the breaking point's internal KZT over the formation's internal KZT. It is always in 0..1.

## The weights

From `WEIGHTS` at the top of the module. Every term is already on 0..1 before weighting.

| Term | Weight | How it is computed |
|---|---|---|
| `kzt_through` | 0.30 | `log1p(kzt_through)`, min-max normalised across all formations |
| `fragility` | 0.25 | as above, already a share |
| `seed_proximity` | 0.15 | `1 / (1 + min_hop_from_seed)` |
| `retained_share` | 0.10 | `kzt_retained_share`, already a share |
| `size` | 0.10 | `log1p(n_members)`, min-max normalised |
| `seed_count` | 0.10 | `n_seeds`, min-max normalised |

`kzt_through` and `n_members` are compressed with `log1p` first because the largest fan-out
moves two orders of magnitude more than the median formation. Without the compression that
one row flattens every other term to zero and the ranking becomes a list of the biggest
payers again, which is the thing this module exists to avoid.

The weighted sum is then multiplied by the formation's kind weight, from `KIND_WEIGHTS`:

| Kind | Weight | Why |
|---|---|---|
| `funnel` | 1.00 | A collection point with its feeders is directly actionable. |
| `chain` | 0.95 | A transit route is actionable but each step still has to be checked. |
| `reciprocal_loop` | 0.85 | Return flow is a strong signal on a small set of accounts. |
| `fan_out` | 0.80 | Partly the shape of the crawl: hop 4 receivers have no onward transfer because the crawl stopped, not necessarily because the money did. |
| `bridge` | 0.70 | A topological observation before it is a finding. |

`rank` is 1 upward on `score` descending, ties broken by `formation_id` ascending.

## Output columns

`formations_df`: `formation_id`, `kind`, `n_members`, `n_seeds`, `min_hop_from_seed`,
`kzt_through`, `kzt_retained_share`, `breaking_point_gid`, `breaking_point_method`,
`breaking_point_effect`, `score`, `rank`, `hypothesis`, `evidence`.

`membership_df`: `formation_id`, `gid`, `role_in_formation`, `member_evidence`.

`kzt_through` is every KZT on an edge touching the formation, counted once: internal edges
plus money arriving from outside plus money leaving to outside. `kzt_retained_share` is the
internal part divided by that total. `min_hop_from_seed` is the smallest `depth` among the
members, and `depth` is by construction the number of hops the crawl took to reach the node
from the nearest seed.

`hypothesis` is one sentence generated from that formation's own figures, in the same voice
as `hypotheses.py`: what the numbers are consistent with and what an analyst should check,
never a statement about a person. `evidence` is at most 220 characters and carries every
figure that produced the score.

## Worked example: FUN-001, rank 1

Four accounts, found by the funnel rule. This is the full arithmetic, recomputable by hand
from `data/edges.parquet`.

**Members** (`membership_df` where `formation_id == "FUN-001"`):

| gid | role in formation | node role | depth | sends into the formation | as a share of its total outflow |
|---|---|---|---|---|---|
| 100000003684369100 | `consolidator` | distributor, seed | 0 | 200,000 KZT | 2% of 8,588,655 KZT |
| 100000003299365100 | `feeder` | transit | 1 | 200,000 KZT | 100% of 200,000 KZT |
| 100000001102676100 | `feeder` | transit | 2 | 50,000 KZT | 100% of 50,000 KZT |
| 100000004450649100 | `feeder` | peripheral | 3 | 41,300 KZT | 89% of 46,527 KZT |

The rule fired because three payers each send 100000003684369100 at least 50% of their
outflow, which is `funnel_min_feeders=3` met at `funnel_min_feeder_share=0.5`.

**The four internal edges**, and the money around them:

```
100000001102676100 -> 100000003684369100      50,000.00
100000004450649100 -> 100000003684369100      41,300.00
100000003299365100 -> 100000003684369100     200,000.00
100000003684369100 -> 100000003299365100     200,000.00
                              internal      491,300.00
                   inbound from outside    3,799,664.00
                     outbound to outside   8,393,882.00
                          kzt_through     12,684,846.00
```

`kzt_retained_share = 491,300 / 12,684,846 = 0.0387`. Almost all of the money touching this
set passes across its boundary rather than staying in it, which is why the hypothesis for
this row calls it a collection point rather than a closed group.

**Breaking point.** No member dominates another on the reversed subgraph rooted at the
collection point, because every feeder's immediate dominator is the collection point itself.
The fallback fires: on the undirected projection, 100000003684369100 is the only articulation
point, and removing it leaves the three feeders with no route to each other or to the entry.
Method `articulation`, effect **3 of 3 members**, `fragility = 3 / 3 = 1.00`.

**Score.** The normalisation constants come from the 653 formations in the same run:
`log1p(kzt_through)` runs from 10.410787 (33,215 KZT) to 17.337808 (33,862,123.08 KZT), and
`log1p(n_members)` from 1.098612 (2 members) to 5.017280 (150 members). `n_seeds` runs 0 to 5.

| Term | Value | Arithmetic | Weighted |
|---|---|---|---|
| `kzt_through` | 0.8583 | (16.355919 − 10.410787) / (17.337808 − 10.410787) | 0.257472 |
| `fragility` | 1.0000 | 3 / 3 | 0.250000 |
| `seed_proximity` | 1.0000 | 1 / (1 + 0) | 0.150000 |
| `retained_share` | 0.0387 | 491,300 / 12,684,846 | 0.003873 |
| `size` | 0.1304 | (1.609438 − 1.098612) / (5.017280 − 1.098612) | 0.013036 |
| `seed_count` | 0.2000 | (1 − 0) / (5 − 0) | 0.020000 |
| | | **raw sum** | **0.694381** |
| | | × `KIND_WEIGHTS["funnel"] = 1.00` | **0.6944** |

That is the highest score of the 653, so `rank = 1`.

**The two strings this row emits.**

> `hypothesis`: The figures suggest 3 accounts sending a dominant share of their outflow into
> 100000003684369100, 12,684,846 KZT touching the set with 4% of it staying inside, which is
> worth checking as one collection point rather than 3 unrelated payers.

> `evidence`: funnel: n=4, seeds=1, hop=0, through=12,684,846 KZT, retained=0.04; break
> 100000003684369100 by articulation cuts 3 of 3 members; fragility=1.00, score=0.6944

Ranks 2 and 3 are the same kind: FUN-004, five accounts moving 18,313,240 KZT with 60%
retained and a breaking point that cuts 4 of 4, and FUN-008, five accounts including four
known clients moving 587,266 KZT with 24% retained.

## Cost and determinism

`formations.build` runs in about 0.46 seconds on the 2,248 node crawl, measured as the
median of five runs, against a whole pipeline that takes roughly 1.2 seconds before it.

Everything is linear or near linear in nodes and edges except one step. Enumerating the
maximal directed paths inside a chain component is factorial in the size of that component,
so `chain_max_component` caps it at 12 and larger components are skipped. The largest chain
component in this data has five nodes, well inside the cap, so nothing is skipped here.
Short cycle enumeration is bounded by `loop_max_cycle_len=4` for the same reason.

The output is deterministic. Every set is sorted before it becomes output, every groupby is
ordered, ties in the ranking break on `formation_id`, and the Louvain communities the bridge
rule reads are already seeded at 42 in `clusters.py`. Three separate processes produced
byte-identical CSVs for both frames.
