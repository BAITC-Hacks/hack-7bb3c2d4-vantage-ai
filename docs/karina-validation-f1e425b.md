# Validation checkpoint — f1e425b

Date: 23 September 2026. Checkpoint owner: Karina.

## Scope

Checked a separate snapshot of team GitHub main at `f1e425b`.
The application source, interface and committed output files were not changed during this check.

## Environment and command

Python 3.11 on macOS. Installed the exact versions from this snapshot's requirements.txt:
pandas 3.0.2, pyarrow 25.0.1, networkx 3.6.1, numpy 2.4.4, scipy 1.17.1.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p test_outputs.py -v
```

The tests generate fresh outputs in a temporary directory, rather than checking only previously committed CSVs.

## Results

**8 checks passed, 0 failed.** Pipeline subprocess elapsed: **1.99 seconds**.
Dependency installation is excluded from this measurement. Timing is machine-specific.

Passed checks:

- Required columns in all three mandatory CSV files.
- Every input node appears once, with exact gid preservation.
- Supported roles, finite scores in [0,1], non-empty evidence of at most 200 characters.
- Cluster membership and node/seed counts.
- Non-empty cluster hypotheses.
- At least 20 unique ranked nodes with consistent roles and scores.
- Depth-4 nodes without outgoing transfers are not labelled terminal.
- Pipeline runtime below five minutes.

## Limits of this checkpoint

This verifies the existing acceptance suite, not every analytical claim.
Browser interactions, visual clarity, formation ranking, completeness recommendations,
correctness of every role threshold, and the platform submission were not independently
validated in this checkpoint. A live demonstration and final clean-environment check remain necessary.

The earlier acceptance-checklist.md records an older baseline; its missing-cluster-hypothesis
failure does not apply to this tested snapshot. Later commits require their own verification.
