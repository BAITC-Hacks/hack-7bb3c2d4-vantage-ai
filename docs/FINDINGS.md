# Money Graph: the four source documents, read and verified

All four attachments downloaded and read in full at 14:00 Astana:

| # | Document | Status |
|---|---|---|
| 1 | Main case spec, Google Doc, RU + KZ + EN, 39k chars | **Read in full.** Contains things the other three do not |
| 2 | Dataset README, markdown | Read in full |
| 3 | `data/` zip: edges, nodes, transactions parquet | Downloaded, loaded, analysed |
| 4 | `starter/` zip: README, requirements.txt, starter.py | Read in full, including every line of starter.py |

I then re-ran the spec's own factual claims against the real parquet files. **They check out.**

| Spec claim | Verified |
|---|---|
| 72 nodes with pass-through 0.8 to 1.2 | **72.** Exact |
| 19 of 81 seeds absent from all edges | **19.** Exact |
| 31 seeds have no outgoing transfers | **31.** Exact |
| 16 weakly connected components, largest 1,877 with 46 seeds, second 270 with 1 seed | **Exact** |
| Fan-out distributors, 60 to 116 receivers | 8 such nodes, max out-degree **116.** Exact |
| In-degree 8 to 24 consolidator candidates | 17 such nodes |
| Base Louvain gives ~8 stable communities with more than one seed | **9** at seed 42. Close, and seed-dependent |
| 354 nodes send more than they received | I get **377**. Minor definitional difference, not important |

---

## Corrections to what I told you earlier

Three things I got wrong before reading document 1.

**The 19 isolated nodes are all seeds.** I said 19 nodes appear in no edge, which is right, but they are 19 of the 81 seed clients, and a further 12 seeds appear only as receivers. So 31 of 81 seeds have no outgoing transfers at all. That is a much better story: **a third of the people law enforcement handed you are dead ends in this data.** Say that out loud in the demo.

**The naive pass-through rule does work.** I reported zero transit candidates. That was my filter, not the data: I required inflow above 2 million KZT on top of the ratio. Without it there are exactly 72 nodes in the 0.8 to 1.2 band, which is what the spec says. Use the ratio, and use dwell time as corroboration rather than replacement.

**Target 8 or 9 clusters, not 91.** Raw Louvain gives 70 communities, most of them noise. The meaningful number is the 9 communities containing more than one seed, sizes 142, 127, 81, 65, 47, 41, 26, 7, 5. The spec says the organisers found 8. That is your cluster story.

---

## What document 1 contains that nothing else does

### The declared data limitations are explicitly scored

The spec heading reads: "Качество и ограничения данных (объявлены заранее, **их учёт оценивается**)". The organisers list seven known defects and say accounting for them is marked.

| Declared limitation | What they expect you to do |
|---|---|
| 444 nodes at depth 4 with no outgoing are a crawl artefact | A naive `out_degree == 0` rule gives 444 false terminals |
| Outbound only, incoming flows from outside the sample invisible | You cannot compute a true balance for any node |
| Seed inflows understated | The give/receive ratio is meaningless for seeds |
| 5,000 KZT threshold | Structuring below it is invisible. Do not claim to detect it |
| 19 seeds absent, 12 receive-only, 31 with no outgoing | Handle at traversal time |
| 16 components, 352 nodes outside the largest | The network is not monolithic |
| No client attributes at all | Structure and amounts only |
| No ground truth | **Scored on the soundness of your criteria, not accuracy** |

Answering these seven by name, in the README, is the highest-value writing you will do today.

### Must-have 3 is a live oral exam

> "Жюри называет 3 произвольных gid; команда за минуту объясняет, почему роль именно такая, опираясь на свои метрики."

**The jury will name three random gids and you have one minute each to justify the role from your own
metrics.** That is not a README item, it is a demo skill, and it is Karina's. Build a per-node card view
so she can type a gid and read the answer off the screen.

### Must-have 5 requires gid search on the diagram

> "на демо жюри называет gid, команда находит его на схеме и показывает его связи"

Search by gid, locate on the network diagram, show its connections. That is a stated acceptance test, so
the search box is not optional polish.

### Other requirements not in the other documents

- **Demo is 5 minutes**, a live run plus a substantive walk through 2 or 3 nodes.
- **A solution schema is a mandatory artefact**: one slide or diagram, data to metrics to roles to interface.
- **The README must include a scaling section**: what changes in the approach at roughly 1 million nodes.
  Text only, no implementation required. Almost nobody will write this.
- **External LLM APIs are explicitly permitted.** "Интернет может потребоваться только для внешнего LLM
  API, если команда его использует." The no-paid-services constraint is about reproduction requiring a
  GPU cluster, not about calling an API.
- **The technical criterion explicitly names agentic AI**: "использование AI/agentic AI и других
  технологий". So it is scored here, unlike in the general regulations.
- **Wording discipline is a stated requirement.** Conclusions must be framed as hypotheses for checking,
  "признаки консолидации", never as assertions of guilt.
- **Forbidden**: hardcoding gid lists, black-box roles with no explainable rule, inventing client
  attributes that are not in the data.

### The organisers' note on what is in the data

They state the data contains clear candidates for every role: nodes receiving from 8 to 24 distinct
payers, nodes fanning out to 60 to 116 receivers, 72 nodes with pass-through 0.8 to 1.2, and 8 stable
Louvain communities with more than one seed. All verified above. **You are not hunting blind.**

### Exact output schemas, from starter.py

`nodes_roles.csv`, 2,248 rows: `gid, role, role_score (0-1), cluster_id, priority_score (0-1), evidence`
plus the feature columns. **Evidence must be human-readable, contain numbers, and be at most 200
characters.**

`clusters.csv`: `cluster_id, n_nodes, n_seed, sum_kzt_internal, top_gids, hypothesis`

`top_nodes.csv`, at least 20 rows: `rank, gid, role, priority_score, why`

---

## Findings from the data that still stand

**1,110 genuine terminals against 444 truncated.** Dead ends at depth under 4 are real, because the
crawl would have followed them. They hold 138,221,735 KZT, 37.8 per cent of the 365,890,012 total. This
is the answer to the spec's headline trap and it is worth explicit points under "опционально".

**PageRank and HITS disagree completely.** Zero overlap in the top five. HITS authorities are collectors,
hubs are distributors, which is the actual question. Everyone will rank by PageRank.

**448 of 671 two-way nodes move money within one day**, from `transactions.parquet`. The spec lists
"сквозной транзит, пришло и ушло в течение 1-2 дней" as an optional scoring item. It is sitting there.

**177 reciprocal pairs and 1,541 cycles of length 6 or under.** Also an optional scoring item,
"возвратные потоки", one `simple_cycles` call away.

**Round-number clustering**: 271 of 4,840 transactions are exact multiples of 100,000. Report as
round-number behaviour, and state plainly that structuring below the 5,000 floor is undetectable, which
is a limitation the spec itself declares.
