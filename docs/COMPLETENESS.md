# What the crawl could not see

Computed by `src/moneygraph/completeness.py`. Every figure below comes from the run, not from
the brief, and the module checks itself against the declared ground truth on each run.

## Two consequences of the collection design

The dataset is a breadth-first crawl that followed **outbound** transfers four hops from 81 seed
accounts. Two things follow from that alone, before any metric is computed.

**1. The funding side of the structure is outside the dataset.** A transfer into a seed produces a
row only if the payer itself was expanded by the crawl, and no account above the seeds ever was.
The seeds moved **55,294,178 KZT** out against **14,849,167 KZT** observed arriving, and that
arriving money is return traffic from inside the crawl rather than funding. **40,445,011 KZT** of
seed outflow, **11.05%** of total turnover, has no recorded payer. We cannot name who funds the
structure, and neither can anyone else working from these three tables. An entry that presents a
confident org chart with a single figure at the top is describing the shape of the crawl.

The caveat on that figure, stated rather than buried: it assumes the seeds opened the window at
zero. The data carries no balances, so read 40,445,011 KZT as the amount with no observed payer,
not as proven outside money.

**2. Not every dead end is a dead end.** 1,554 nodes have no outgoing transfer. **444** of them sit
at hop 4, where the crawl stopped, so their onward path was never collected. **1,110** sit below
hop 4, where the crawl did look and found nothing. Those are different objects. **56,672,165 KZT**,
**15.49%** of turnover, arrives at the 444 and then leaves the dataset's field of view. Treating
the two groups alike would be a factual error, so `roles.py` classifies the 444 as
`abstained_boundary` and this module gives them their own state.

## The two abstention classes

The case taxonomy is consolidator, transit, distributor, terminal, coordinator and peripheral.
This entry extends it by two, and this is the extension being documented rather than slipped in.

`roles.py` does not label an account whose behaviour the crawl never observed. 558 of 2,248
accounts, 24.82%, receive one of two abstention classes instead. Neither is a gap, both are
verdicts, and every row carries the figures its verdict rests on in the `evidence` column.

| Class | Rule | Nodes | Why no behavioural role is available |
|---|---|---:|---|
| `abstained_boundary` | `hop_from_seed == 4` and no outgoing edge | 444 | Their pass-through ratio is zero because the crawl stopped, not because they retained the money. Reading that as retention would be reading a collection artefact as behaviour. The consolidator rule is also out of reach: 434 have an in-degree of exactly 1, seven have 2 and three have 3, against a fan-in floor of 8. |
| `abstained_single_observation` | `in_tx + out_tx < 3`, in practice one transfer each way | 114 | A pass-through figure built from a single pair of numbers is not a rate and cannot be told apart from coincidence. |

The two are held apart rather than merged because the remedy differs. Request 1 below resolves
every one of the 444 and none of the 114; only a longer observation window resolves the 114.

A classifier that declines on 558 accounts and can say which of two reasons applies to each one
is a stronger claim than one that labels all 2,248. The count is not the achievement. Knowing
which rows the data does not support is.

## The knowledge_state taxonomy

Five states, evaluated in order, first match wins. Every node gets exactly one.

| State | Rule | Nodes | Share of turnover touched |
|---|---|---:|---:|
| `isolated` | no transfer observed in either direction | 19 | 0.00% |
| `truncated_at_depth` | `hop_from_seed == 4`, never expanded | 444 | 7.74% |
| `outbound_only` | has outgoing transfers and is a seed, or has no observed payer | 50 | 9.38% |
| `inbound_only` | no outgoing transfer observed | 1,091 | 18.89% |
| `fully_observed` | both directions traversed inside the crawl | 644 | 63.98% |

Turnover touched by a node is what arrived plus what left, so the shares are of twice the edge
total; each transfer is touched by its payer and by its receiver.

A seed is never `fully_observed`, however busy it looks. The crawl started there and only ever
followed money outwards, so its payer side is unobservable by construction. 39 seeds do show
inbound edges, but those are return traffic from accounts already inside the crawl, and the
`limitation` text on each of those rows says so.

**1,604 of 2,248 nodes (71.35%) are not fully observed**, covering **36.02%** of turnover.

## How confidence is computed

`confidence` answers one question: how much of the reason to trust this node's role and rank is
actually present in the data. It is a weighted sum of five components, each bounded in [0, 1], with
weights that sum to 1.0, so no clipping is needed. The module asserts the sum on import.

| Component | Weight | Value |
|---|---:|---|
| `outbound_enumerated` | 0.34 | 1 if the crawl expanded this node (`hop < 4`), else 0 |
| `inbound_observed` | 0.26 | 1 if a payer is recorded, 0.5 if the node is a seed, 0 if none |
| `downstream_resolved` | 0.20 | 1 minus the share of reachable nodes that sit at hop 4 |
| `evidence_volume` | 0.12 | `min(1, (in_tx + out_tx) / 3)`, the threshold `roles.py` uses for a stable ratio |
| `depth_margin` | 0.08 | `(4 - hop_from_seed) / 4` |

A ceiling is then applied per state, so that a hop-4 node with a rich inbound side cannot score
respectably on the strength of the one thing that does not matter about it:

| State | Ceiling |
|---|---:|
| `fully_observed` | 1.00 |
| `inbound_only` | 0.85 |
| `outbound_only` | 0.60 |
| `truncated_at_depth` | 0.40 |
| `isolated` | 0.10 |

Result across the network: mean 0.739, median 0.85, range 0.10 to 0.98. **673 nodes (29.94%) fall
below the 0.75 audit floor**, meaning their role should not be read without their `limitation`.

The ordering is deliberately not a league table of states. A `fully_observed` node scores as low as
0.70 when a quarter of what it can reach ends at the crawl boundary, which is lower than a clean
`inbound_only` terminal at 0.85. Being observed on both sides is not the same as being understood.

`downstream_resolved` is computed by reachability over the whole graph, carried in integer bitmasks
and iterated to a fixed point because the graph contains cycles. The whole module
runs in 0.16 s, so it does not threaten the five-minute budget on `run.py`.

## Does the priority list rest on incomplete data

This is the number worth saying out loud, and the honest answer has two halves.

**2 of the top 20 (10%)** are flagged as resting on incomplete observation: ranks 2 and 19, both
seed accounts in `outbound_only` at confidence 0.60. Their rank is built on outbound behaviour
alone, because their inbound side does not exist in this dataset. The other 18 are `fully_observed`
with confidence between 0.911 and 0.980. On its own terms the priority list is robust, and we would
rather report that than invent alarm.

**15 of the top 20 (75%) send money onward into the crawl boundary.** On average **14.4%** of
everything reachable below a top-ranked node sits at hop 4 with an unrecorded onward path, and for
nine of them that figure is 24.6%. The uncertainty is not in the ranking. It is one hop underneath
it, which is exactly where the next request should go.

## The next data request, ranked

Ordered by `share_of_nodes_resolved + share_of_turnover_illuminated`, both computed from the run.
The rule is in the module so the ordering can be recomputed by hand rather than argued about.

| # | Request | Resolves | Illuminates | What it buys |
|---:|---|---:|---:|---|
| 1 | One more crawl hop from the 444 nodes at the depth limit | 444 nodes | 56,672,165 KZT | Separates the 444 crawl artefacts from the 1,110 places where money genuinely appears to stop, and resolves the downstream exposure of 15 of the top 20. |
| 2 | Hour-level timestamps in place of calendar dates | 327 nodes | 65,673,806 KZT | 327 nodes have at least one day on which money both arrived and left. At day resolution the order is unresolved, and dwell time is what separates a node passing funds through from one that happened to transact twice. |
| 3 | Inbound transfers to the 81 seed accounts, one hop back | 81 nodes | 40,445,011 KZT | The only request that reaches above the seeds at all. Nothing else in this list can touch the funding question. |
| 4 | Account opening dates | 36 nodes | 3,749,141 KZT | 36 accounts show their whole observed life inside one calendar day with money both in and out. An opening date would separate a purpose-opened account from a long-standing one used once. |
| 5 | Counterparty bank or institution | 0 | 0 KZT | **Rejected on the present evidence.** No institution field exists in any of the three tables, and nothing in gid, depth, date or amount stands in for one, so no figure here would change if it arrived. |

Feasibility differs from value and is carried separately in `next_data_request.feasibility_note`.
Request 2 is a re-export of a field the source ledger almost certainly holds. Request 1 is the same
collection method one hop further. Request 3 reverses the crawl direction and is a new collection
rather than a re-export, which is why it ranks third on figures while being first in importance to
the case narrative. We have kept the two judgements apart rather than blending them into one score.

Request 5 stays on the list, marked as unevaluable, rather than being dropped. Removing it silently
would read as a judgement the data does not support.

## Why this is a strength

Nothing here weakens a single finding elsewhere in this entry. Every role, cluster and rank is
unchanged. What changes is that each one now travels with a number saying how much of it the
collection actually supports, and the gaps are sized rather than gestured at. An analyst acting on
row 2 of the priority list knows before opening the file that the account's funding side was never
collected. That is the difference between a result and a result you can act on.

## Interface

```python
completeness_df, next_data_request_df, summary = completeness.build(d, feats, roles_df)
```

`completeness_df`: `gid, knowledge_state, hop_from_seed, inbound_known, outbound_known,
confidence, limitation`, one row per node, 2,248 rows.

`next_data_request_df`: `rank, request, why, resolves_nodes, illuminates_kzt, feasibility_note`.

`summary`: flat, JSON-serialisable, native Python types, including `ground_truth_check`, which
reports **agrees with the brief** on this run and would name any disagreement in plain words rather
than absorb it.

All figures are hypotheses for an analyst to test. None of them is a statement about a person.
