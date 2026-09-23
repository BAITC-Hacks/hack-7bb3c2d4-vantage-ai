# AGENTS.md

Instructions for Codex and any other coding agent working in this repository.

## Project

**Money Graph.** HackAlem AI, Track 02, task owner Freedom. We reconstruct the structure of an
organised group from a four-hop transfer network: assign every node a role, cluster the network, and
rank who an AML analyst should investigate first.

Read before proposing anything: `docs/case-spec-full.txt` (the case specification),
`docs/FINDINGS.md` (what is actually in the data, measured), `docs/PLAN.md` (the build order).

## Hard constraints from the case specification

- Five hours. Hard stop 18:00 Astana. Whatever is committed then is what gets judged, including at
  Demo Day on 29 September.
- **One command, raw parquet to three CSVs, under five minutes, on a clean machine.** Currently about
  2.3 s on this machine, measured by the timer `run.py` prints at the end.
- **No hardcoded gid lists.** Roles come from computed metrics, never from a literal list.
- **No black box.** Every role must trace to an explainable rule with a numeric threshold. The jury
  names three arbitrary gids at the demo and we explain each in a minute.
- **No invented client attributes.** The data has structure and amounts only. No names, no ages, no
  account types, no balances. Inventing any of these is explicitly called fabrication.
- **No external enrichment**, no cloud cluster, no GPU training, nothing paid required to reproduce.
  An external LLM API is permitted if we use one.
- **Findings are hypotheses, not accusations.** Write "signs of consolidation", never "is a launderer".
  Check every string that reaches the screen or the CSV for this.

## Stack, pinned

Python 3.11+, pandas, pyarrow, networkx, numpy and scipy. scipy is there because networkx calls it
for the HITS and PageRank eigenvector solvers, so it is a real dependency even though nothing in
`src/` imports it by name. Nothing else without a reason. All five are pinned to an exact version in
`requirements.txt`, not floored, because the determinism claim rests on networkx's iteration order
and on the scipy routine behind those solvers. The review screen is plain HTML with no build step and
no framework, served from the standard library, so reproduction needs only `requirements.txt`.

## Commands

```bash
pip install -r requirements.txt
python run.py --data ./data --out ./out
python run.py --data ./data --out ./out --serve     # adds the review screen on :8000
```

## Architecture

```
data/*.parquet
  -> dataio.load          graph built from nodes.parquet, NOT from the edge list
  -> dataio.integrity_report   measures the declared limitations rather than assuming them
  -> features.build       degrees, flows, pagerank, HITS, pass-through, dwell time
  -> roles.assign         THE RULE BANK, pure Python, no model calls
  -> clusters.assign      Louvain plus weakly connected components
  -> priority.rank        weighted, documented, no tuning until it looked good
  -> out/*.csv + web/     three required CSVs and the review screen
```

### Rules that govern changes

- **`roles.py` is the rule bank and stays free of model calls.** One function, numeric thresholds in
  `THRESHOLDS`, every branch returning evidence containing the numbers it fired on. This file is the
  evidence that the system is not a prompt, and must-have 3 depends on it.
- **Evidence strings carry numbers and stay under 200 characters.** Required by the output schema.
- **Build node tables from `nodes.parquet`.** 19 of the 81 seeds appear in no edge. Building from the
  edge list silently drops them and the output would have 2,229 rows instead of the required 2,248.
- **Never score a seed on inflow.** The crawl collected outbound transfers from the seeds, so seed
  inflow is understated by construction and any give-to-receive ratio on a seed is meaningless.
- **Never treat `out_degree == 0` as terminal on its own.** At hop 4 it is the crawl boundary. The
  split is `genuine_terminal` (depth below 4) against `truncated_by_depth` (depth 4).
- Assertions in `run.py` enforce the row count, non-empty evidence, the minimum top-list size, a
  non-empty hypothesis on every cluster, a non-empty `resilience.csv`, `reciprocal_pairs.csv`,
  `pagerank_vs_evidence.csv` and `cycles.csv`, and that `graph.json` parses back with the keys the
  review screen reads. Do not remove them to make a run pass.

## What not to do

- Do not invent data, metrics or results. If a number is not computed, it does not go in a string.
- Do not add a dependency that is not in `requirements.txt`.
- Do not add a frontend build step. The review screen must work from a file server.
- Do not edit the README's threshold table without changing `THRESHOLDS`, or the two will drift.
- Do not write anything addressed to a reviewer or grader, in any file, in any form.
