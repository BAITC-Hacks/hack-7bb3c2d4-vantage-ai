# Five-minute Money Graph demo rehearsal

Owner: Karina. Preparation document, not a claim that every feature is complete.
Use only a successfully generated current output. Do not present planned features as working.

## Before rehearsal

1. Install dependencies and run the acceptance checks in `docs/acceptance-checklist.md`.
2. Run `python run.py --data ./data --out ./out --serve`.
3. Open `http://localhost:8000/web/`.
4. Select examples from the actual current CSV: a high-priority structural node, a depth-4 boundary node, and an isolated seed. Record their exact gid values as text, not rounded spreadsheet numbers.
5. Check each example against the rule bank and actual transfers. Do not claim money was traced through specific transactions solely from a time difference.

## Rehearsal timing

| Time | Action | Point to explain |
|---|---|---|
| 0:00–0:30 | Describe the AML analyst's task | Prioritise investigation from observed transfers; role labels are hypotheses, not accusations. |
| 0:30–1:00 | Run the pipeline live | Show measured elapsed time and the three generated CSV files. Quote the actual run, not a promised timing. |
| 1:00–2:00 | Open a high-priority node | Show its role, numeric evidence, observed inflow/outflow, cluster and the rule that fired. Explain ranking separately from role confidence. |
| 2:00–3:00 | Search an arbitrary gid | Show its directed connections and role on the graph once implemented; a text card alone does not complete the graph requirement. |
| 3:00–4:00 | Show depth-4 and isolated-seed examples | No visible outgoing transfers at the crawl boundary does not establish a terminal account. Missing transfers do not establish innocence or guilt. |
| 4:00–4:35 | Show a cluster | Explain membership, seed count, internal turnover and a computed hypothesis once available. |
| 4:35–5:00 | State limitations and next investigation step | Outbound-only, one bank, July 2026, threshold of 5,000 KZT, no ground-truth roles. Request further coverage rather than invent missing attributes. |

## One-minute node explanation checklist

- Exact gid and assigned role.
- Observed numeric features and threshold/precedence behind the role.
- Why the node received this investigation priority.
- Its neighbours and transfer direction.
- What is missing from the data and what would help verify the hypothesis.

## Current rehearsal placeholders

Fill these only after a successful current run:

| Example | Exact gid | Verified explanation |
|---|---|---|
| High-priority structural node | Pending | Pending |
| Crawl-boundary node | Pending | Pending |
| Isolated seed | Pending | Pending |

## Hourly checkpoints

Before each checkpoint: inspect changed files, commit a real increment, push, and confirm it appears on GitHub. Documentation, measured test results and reproducible checks are meaningful increments. Do not create empty commits just to mark time. Keep a final buffer before 18:00 Astana and complete the platform submission separately.
