# Money Graph acceptance checkpoint

Owner: Karina. Date: 23 September 2026.
Baseline inspected: `be0ae2f`. This checkpoint adds acceptance checks and a missing runtime dependency; it does not certify the project as complete.

## Reproduce

From the repository root, using Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_outputs.py' -v
```

The checks run the actual pipeline against the supplied parquet files in a temporary output directory. They do not replace existing out/ files and do not require API keys.

## Measured result

Fresh isolated Python 3.11 environment, macOS, installed only requirements.txt.

- Initial run failed with `ModuleNotFoundError: No module named 'scipy'` inside NetworkX PageRank.
- Added `scipy>=1.11` to requirements.txt. SciPy is needed by the current graph algorithms.
- Rerun: **8 checks executed, 7 passed, 1 failed**.
- Measured subprocess elapsed: **5.75 seconds**, including interpreter startup, excluding dependency installation.
- Remaining failing check: all **91 clusters** had empty `hypothesis` values.
- This is a checkpoint measurement, not a guarantee for other machines or later commits.

## Mandatory requirements

| Requirement | Status at checkpoint | Evidence / remaining action |
|---|---|---|
| One run from raw parquet to three CSVs in under 5 minutes | Pass on this environment after dependency fix | Actual pipeline completed within the measured time above. |
| Every supplied node has role, scores and evidence | Automated checks pass | Exact source gid set, uniqueness, supported roles, finite scores in [0,1], non-empty evidence <=200 characters. |
| Role criteria explained for arbitrary nodes | Manual verification pending | Rule bank exists. Rehearse three arbitrary gids and check README agrees with actual rule precedence. |
| Clusters with counts, turnover, leading nodes and hypotheses | Incomplete | Membership and node/seed counts pass; hypotheses are empty. Turnover and top_gids semantics still need independent verification. |
| Ranked list >=20 plus directed graph and gid lookup | Partial | Ranked list checks pass; baseline HTML has search/card but no network diagram. Browser interaction not tested in this checkpoint. |

## Before the next checkpoint

- [ ] Sam: implement evidence-based cluster hypotheses and rerun the failing check.
- [ ] Sam: implement directed graph, role/cluster highlighting and gid-to-neighbours navigation.
- [ ] Karina: select three real examples and rehearse the explanation checklist in demo-script.md.
- [ ] Karina: test searching an existing gid, an isolated seed and a nonexistent gid in the browser.
- [ ] Team: independently review seed inflow handling and role precedence.
- [ ] Team: verify amounts/counts between edges and transactions; the existing integrity flag only compares pair presence.
- [ ] Team: make README match final behaviour and verify a final clean-clone launch.
- [ ] Team: submit through the hackathon platform before 18:00 Astana, in addition to pushing GitHub changes.

## Hourly workflow

Commit a meaningful increment and push before each hourly checkpoint. Check its author, timestamp and changed files on GitHub. A local commit alone is not uploaded. Prefer explicit filenames when staging so unrelated work is not included. Keep tests that expose unfinished requirements visible instead of disabling them.
