# Money Graph: the build

Four hours left. Rubric: compliance 25, technical 25, README and reproducibility 25, value 15,
originality 10.

---

## The product in one line

**The analyst sees the bottom of the chain. This shows who is standing above it, and proves why.**

## The five differentiators, in build order

Ranked by points per minute. Items 1 to 5 are the project. Everything after is a bonus.

### 1. Answer the organisers' four traps explicitly. 45 minutes. Pays: compliance 25.

The starter README lists four traps "on which naive solutions break". That is the marking scheme written
down. Give each one a named section in the README and a line of code it maps to.

| Trap | Your answer |
|---|---|
| `out_deg == 0` does not mean the money settled | Split by depth. 1,110 genuine terminals at depth under 4, 444 unknown at depth 4. Separate role for each |
| Seed `in_kzt` is understated by the crawl design | Never score seeds on inflow. Seed roles use outflow and fan-out only. Say so |
| Sums and transaction counts are different signals | Every role rule uses both. A single 4M transfer and forty 100k transfers get different roles |
| The graph is directed and weighted | All metrics directed and weighted. Louvain runs on the undirected projection, and the README says explicitly what that loses |

No other team will structure their README around the organisers' own trap list.

### 2. All 2,248 rows, including the 19 isolated nodes. 10 minutes. Pays: compliance 25.

Build from `nodes.parquet`, left-join metrics. The 19 with no edges get their own role. A mechanical
check on row count is the easiest way to lose points today.

### 3. Evidence as numbers, and an abstention class. 45 minutes. Pays: compliance, originality.

The spec says `evidence` must contain numbers, not "high score". So every row carries the actual
figures the rule fired on: in_kzt, out_kzt, in_deg, out_deg, pass_through, dwell_days, depth.

Then add a sixth outcome the taxonomy does not require: **insufficient evidence**. Nodes with
conflicting signals, or too few transactions for a stable ratio, get no role and a stated reason. Report
the count.

You are scored on justification, not accuracy, because there is no ground truth. A system that knows
what it cannot tell you is the strongest possible answer to that.

### 4. The false positive exhibit. 40 minutes. Pays: technical 25, value 15, originality 10.

PageRank and HITS have zero overlap in their top five. Pick a node that ranks near the top on weighted
PageRank, show that it is a legitimate high-volume hub (regular small payments, low pass-through, long
dwell), and show your evidence score correctly demoting it.

One screen, two columns, "what centrality says" and "what the evidence says". This is the single most
persuasive thing you can build today, and it directly answers the jury question about whether the tool
is doing real work.

### 5. Dwell time instead of pass-through. 45 minutes. Pays: technical 25.

The naive transit rule, pass-through near 1, returns zero nodes on this data. Dwell time returns 448
nodes that move money within a day. Open `transactions.parquet`, compute the lag between first inbound
and first outbound per node, and use it as the primary transit evidence.

Document that you tried the obvious rule, that it found nothing, and why. That paragraph is worth more
than the feature.

### Then, if time allows, in this order

**6. The split screen. 30 minutes.** One seed client. Left: what the analyst sees today, hop 1 only,
dead end. Right: the four-hop reconstruction with the ranked target above it. This is the demo.

**7. Triage ranking with a cost model. 40 minutes.** Rank by structural importance times money reachable
downstream, and show score-per-investigator-hour next to raw score. Investigators have finite hours.

**8. Clustering shown two ways. 40 minutes.** The 16 weakly connected components are a hard structural
split you get for free. Louvain gives 91 soft communities. Show both, explain why they differ, and put
the honest one in `cluster_id`.

**9. Reciprocity and cycles. 30 minutes.** 177 pairs send money both ways, 1,541 cycles under length 6.
`simple_cycles` with a length bound finds them instantly.

**Cut first if behind:** anything temporal beyond dwell time, any animation, any structural embedding.

---

## Stack, settled and tested

Stay in TypeScript, keep the scaffold. Verified against the real files: parquet read, graph build,
weighted PageRank and Louvain all run in **186 ms** total.

```bash
npm i hyparquet hyparquet-compressors graphology graphology-metrics graphology-communities-louvain
```

- `parquetReadObjects({ file, compressors })`. Without `compressors` it throws on the codec.
- `gid` is a **BigInt**. `String(r.gid)` everywhere, never `JSON.stringify` a raw row.
- HITS is not in graphology. Fifteen lines of power iteration, or derive collector and distributor
  scores from weighted in and out flow, which is more explainable anyway.

One runtime, one `npm ci`, one command. The must-have is raw parquet to three CSVs in under five
minutes, and you will do it in under a second.

---

## The README, which is 25 points

Structure it around the organisers' eleven headings, and put these in:

1. **Measured timing at the top.** Run it, paste the literal stdout with the wall-clock time and the
   three row counts. Judges who do not re-run still see it.
2. **A threshold table.** Every role, its rule, its numeric cutoff, and why that cutoff. Not in code
   comments, in the README.
3. **The four traps section.** Each trap, your answer, the code path.
4. **What we tried that did not work.** Pass-through near 1 finds zero nodes. Almost nobody writes this
   section and it reads as competence.
5. **Blind spots, stated plainly.** Outbound-only collection means anything upstream of the 81 seeds is
   invisible by construction. No KYC, no beneficial ownership, no account-type data. The 5,000 KZT floor
   makes small structuring undetectable.
6. **Evaluation philosophy.** There is no ground truth, so state how you justify a role rather than
   claiming accuracy.

---

## Demo, ninety seconds

Load. The ranked list appears with roles and evidence. Click the top node: the evidence numbers, the
rule that fired, the path the money took to reach it. Then the split screen, what the analyst sees
against what you reconstructed. Then the false positive: the PageRank favourite, demoted, with the
reason. Then a node the tool refuses to classify, and why.

Never say the word accuracy.

## Repo repointing, do this first

The scaffold is described as Track 11. Change `package.json` description, drop `mammoth`, add the five
packages above, and update `AGENTS.md` to say Money Graph. Five minutes, and it stops Codex writing
document-diff code.
