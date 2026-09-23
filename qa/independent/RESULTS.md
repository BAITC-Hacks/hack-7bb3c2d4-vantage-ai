# Independent QA results

Tested commit: `27532440638d5b2c28300083e43fd4e2b2c303fb` of `BAITC-Hacks/hack-7bb3c2d4-vantage-ai`.

**353 cases: 333 passed, 20 failed, 0 skipped, 0 fixture errors.** Final run: 2026-09-23 12:33 UTC. Pytest runtime: 37.97 seconds, excluding installation. Python package line coverage: **96.92%** (1070/1104 statements). This metric excludes browser JavaScript and does not establish analytical correctness.

The suite is a separate project. The application working tree, deployment configuration and startup commands were not changed. The pre-existing staged `init.md` remains untouched. No application changes were committed during the original validation run. The QA suite and this historical report are published separately afterward. The frozen snapshot excludes uncommitted work and later team commits.

## Results by area

| Module | Passed | Failed |
|---|---:|---:|
| test_analytics | 97 | 13 |
| test_artifacts | 19 | 0 |
| test_browser | 39 | 1 |
| test_payload_http | 55 | 0 |
| test_pipeline | 98 | 0 |
| test_robustness | 25 | 6 |

The supplied dataset completes the pipeline, required exports and independent aggregate checks. Browser navigation across all seven screens, account search, languages, theme, replay controls and local asset checks pass. The single browser failure is tablet overflow. Checks cover all 2,248 nodes, 3,119 edges and 4,840 transaction rows, plus synthetic examples.

## Findings to review

These are **8 groups of findings**, not 20 distinct defects. Parameterized cases test several boundaries of the same behaviour. The application was not patched or weakened to make tests pass.

| Priority / classification | Finding | Failing cases | Evidence and implication |
|---|---|---:|---|
| High — project contract | Seed classifications and priority depend on incomplete inflow | 5 | Four role cases produce transit/consolidator from inflow-dependent ratios; changing a seed's inbound amount changes priority. Project instructions say seed roles/scoring must avoid incomplete inflow. Review `roles.py` and `priority.py`. |
| Review — analytical design | Outbound-only seeds are always peripheral | 3 | Fan-outs of 20, 60 and 116 remain peripheral because the seed early-return precedes distributor detection. These tests propose treating observed high fan-out as distributor evidence; confirm intended policy before changing the classifier. |
| Medium — robustness | No reciprocal pairs causes an exception | 1 | A simple one-way edge produces `KeyError: returned_share` instead of an empty table with stable columns in `flows.reciprocal_pairs`. The supplied dataset contains reciprocal pairs, so its normal run succeeds. |
| Medium — amount consistency | Fan-split total omits repeated recipients | 1 | Four transfers of 5,000 to three distinct recipients report 15,000 instead of 20,000. Clarify whether the event intentionally selects only one transfer per recipient; if so, expose that selection in evidence rather than presenting it as the full grouped total. |
| Medium — fallback correctness | Reconstructed echo legs include unrelated dates | 1 | Removing in-memory DataFrame attributes (as happens after CSV reload) pulls a July 20 transaction into a July 1 event. Normal in-memory generation passes; the fallback is affected. |
| Medium — integrity guarantee | Edge/transaction consistency checks ignore totals and counts | 2 | Altering a transaction amount or duplicating a transaction leaves `edges_match_transactions` true when pair presence is unchanged. The integrity flag is narrower than its name suggests. |
| Hardening — malformed input | Invalid parquet values are accepted | 6 | Duplicate node IDs, undeclared endpoints, negative edge amounts, negative depth, duplicate edges and string-valued seed flags are not rejected at load time. These are adversarial inputs, not observed corruption in the organizer dataset. |
| Low — layout | Structures page overflows at 768px | 1 | Document width reaches 787px for a 768px viewport. A screenshot is saved with the report. Other tested pages and widths pass. |

## Reproduce

From this QA directory:

```bash
python3 run_suite.py --repo /absolute/path/to/hack-7bb3c2d4-vantage-ai --ref 27532440638d5b2c28300083e43fd4e2b2c303fb
```

For a new committed version, supply its ref instead. The runner never fetches or changes the working checkout. Exit code **1 is expected for this tested revision**, because the suite preserves failing assertions. See [README](README.md) for prerequisites, environment reuse and browser options.

## Evidence

- [Full failure traces](reports/20260923T123340Z-27532440/console.txt)
- [JUnit results](reports/20260923T123340Z-27532440/junit.xml)
- [Python coverage](reports/20260923T123340Z-27532440/coverage-html/index.html)
- [Pipeline log](reports/20260923T123340Z-27532440/pipeline.log)
- [Tested revision and scope](reports/20260923T123340Z-27532440/metadata.json)

Synthetic checks and independent arithmetic complement real-data tests; they do not certify money-laundering conclusions. This run does not measure branch coverage, execute every JavaScript branch, regenerate presentation figures, test every platform, or prove every possible input correct.
