# Money Graph independent QA

This is a standalone QA project stored under `qa/independent/`. It is not imported by the app and is not part of application startup, deployment, or GitHub Actions. Its dependencies and runner are separate from the application.

Run the commands below from this directory (`cd qa/independent`). Saved results describe commit `27532440`, not necessarily the current application revision.

## Run everything

Python 3.11+ and Git are required. The first run needs internet to install dependencies and an isolated Chromium browser.

```bash
python3 run_suite.py \
  --repo /absolute/path/to/hack-7bb3c2d4-vantage-ai \
  --ref origin/main
```

The runner uses the specified **existing local Git ref**. It does not fetch, checkout, merge, commit, or push. Fetch the team repository first if you want the latest remote commit. Uncommitted changes are deliberately excluded.

1. Resolves the ref to an exact commit.
2. Exports a temporary snapshot outside the working checkout.
3. Creates this QA project's own `.venv` and installs the snapshot's pinned dependencies plus QA tools.
4. Generates all outputs in temporary folders. Committed output files remain untouched.
5. Starts a temporary HTTP server on loopback with an OS-assigned port for browser checks.
6. Runs the tests and saves reports under `reports/<UTC timestamp>-<commit>/`.
7. Shuts down its server and browser and removes the temporary snapshot.

The test browser uses a fresh profile, not your personal browser or logged-in accounts. No API keys are needed. The runner strips common API credentials from its child-process environment.

## Options

- `--skip-browser`: intentionally skip Chromium tests; skips remain visible in the report.
- `--no-install`: reuse the already prepared QA environment. Use only when dependencies have not changed.
- `--ref <commit>`: reproduce a report against that exact revision.

A nonzero exit status means a test failed or a fixture could not run. Failures are not hidden with expected-failure markers.

## Coverage

| Area | What is checked |
|---|---|
| End-to-end pipeline | Fresh output folder, spaces in paths, CLI errors, source immutability, timing, repeatability |
| Supplied dataset | All identifiers preserved; independently aggregated degrees, amounts, transaction counts |
| Exports | Schemas, uniqueness, score ranges, evidence lengths, ranks and cross-file consistency |
| Roles | Threshold boundaries, precedence, insufficient observations, seed-inflow invariants |
| Clusters and formations | Membership, counts, internal/touching turnover, duplicate groups, breaking points, known synthetic structures |
| Completeness | State precedence, confidence caps, reachability on cycles, data-request outputs |
| Flows | Valid cycles, reciprocal amounts, seed paths, independent node-removal calculations |
| Timeline and echoes | Daily conservation, empty days, exact/tolerance boundaries, timing, splits, repeated recipients and transaction reuse |
| JSON payload | Strict JSON, 18-digit IDs, nested references, counts, layout bounds and coordinates |
| HTTP server | Public assets, redirects, custom output folder, cache headers, traversal and symlink protection |
| Browser | Seven screens, navigation, full-ID search, unknown IDs, themes, languages, replay, matching amounts, mobile widths, offline assets, missing-data message |
| Auxiliary artifacts | Required docs, local image paths, PNG metadata, source syntax and deployment independence |

Synthetic data is generated in memory or temporary directories. It does not replace the organizer dataset. Expected answers are based on the task contract, documented behaviour, or small independently calculable examples.

`robustness` tests deliberately probe inputs beyond the supplied dataset. A failure there is reported as a hardening gap, not automatically as a failure of the hackathon's fixed-data requirement. Seed-inflow tests follow the explicit project instruction that a seed must not be scored using incomplete inflow.

## Reports

- `console.txt`: test results, failure details and line coverage.
- `junit.xml`: machine-readable outcomes, suitable for a separate QA process if desired.
- `coverage.json` and `coverage-html/`: Python line coverage, not proof of analytical correctness or browser coverage.
- `pipeline.log`: real pipeline stdout/stderr.
- `metadata.json`: exact tested Git commit and scope.
- `environment.txt`: installed versions.
- PNG screenshots for browser assertion failures where capture is possible.

## Scope limits

No finite suite proves every possible input or every line of reasoning correct. These checks do not certify AML conclusions, independently validate all modelled assumptions, perform million-node load tests, test every browser/OS, or prove visual accessibility. Screenshot figures are checked as artifacts, not regenerated. Browser coverage is Chromium at selected widths. Tests do not call paid services or change the application's implementation to make failures pass.
