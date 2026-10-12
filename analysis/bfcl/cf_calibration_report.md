# Expanded offline calibration of the compounding factor

This report uses synthetic data and the repository metric implementation. It makes no model or API calls. It supersedes the earlier 80-replicate, 200-bootstrap calibration; that output is preserved as `historical_v1` in the summary JSON. These simulations are additional analyses, not a replication of numbers in the author response.

All principal runs use fixed base seed `20261010`, K=10, 200 Monte Carlo replicates, and 5,000 task-cluster bootstrap resamples. The task-count curves use two seed runs per underlying task and preserve both rows together in the bootstrap. Wilson intervals show Monte Carlo uncertainty in the reported rejection and power rates.

## Analytic process checks

The table gives population rates under each stated data-generating process. For every row, CF and Delta are shown under both the common-mean null (`p^K`) and the position-specific null (`prod_k p_k`).

| Process | T_EN | T_TR | Common CF / Delta | Position CF / Delta |
|---|---:|---:|---:|---:|
| Independent steps | 0.349 | 0.221 | 1.000 / 0.000 | 1.000 / 0.000 |
| Shared multiplicative survival (alpha=.70) | 0.244 | 0.155 | 1.000 / 0.000 | 1.000 / 0.000 |
| Extra Turkish multiplicative loss (alpha=.70/.35) | 0.244 | 0.077 | 2.525 / -0.693 | 2.525 / -0.693 |
| Same repair probability (rho=.10) | 0.414 | 0.299 | 0.714 / 0.130 | 0.714 / 0.130 |
| Language-specific repair (rho=.10/.15) | 0.414 | 0.338 | 0.444 / 0.253 | 0.444 / 0.253 |
| Unequal position difficulty, independent steps | 0.314 | 0.209 | 0.892 / 0.049 | 1.000 / 0.000 |
| Shared Beta(9,1) task difficulty, conditional independent steps | 0.474 | 0.301 | 1.000 / -0.000 | 1.000 / 0.000 |

In the shared-survival model, `T = alpha * p^K`; the common alpha cancels from the English-relative ratio, giving expected CF=1 and Delta=0. Repair uses a different rule: `T = p^K + rho * (1 - p^K)`. Because the repair term is additive and its effect depends on baseline `p^K`, even the same rescue probability in both languages does not generally cancel. In the displayed repair cases, the expected values differ from the multiplicative-survival null.

The unequal-position scenario sets EN step rates to eight positions at .96 and two at .66, and TR rates to five at .95 and five at .77. Their means remain .90 and .86. The position-specific null is correctly specified, so expected CF is 1 there; the common-mean `p^K` null is misspecified. Shared task difficulty draws one `q ~ Beta(9,1)` per underlying task and reuses it across languages and seeds. It makes `T` exceed `p^K` in both languages, yet CF remains 1 for the specified shared multiplicative difficulty model. This is a conditional cancellation result, not a general claim that dependence or repair cancels.

A 5,000-resample bootstrap of the illustrative extra-Turkish-multiplicative-loss sample gives CF 95% interval `2.287` to `2.632` and Delta interval `-0.743` to `-0.610`. This is a one-cell illustration, not a 14-cell test.

## Null rejection and conditional power by task count

Each Monte Carlo dataset contains eight languages and two backbones, producing the full 14-cell non-English Holm family. The null datasets have analytic CF=1 in every cell. Under both null and alternative, a Beta(9,1) task difficulty is shared across the languages, models, and two seed runs. The alternative changes only Turkish/Gemini task success to the observed Laplace-smoothed rate; other cells remain under the null. Step rates and task rates are treated as generating probabilities, and language/model-specific rescue probabilities make the stated task rates attainable under this synthetic process. Task difficulty is sampled independently across underlying task clusters. The n=4 row is therefore a four-independent-cluster simulation, not an exact reconstruction of the existing BFCL task IDs and scenario variants.

The one-cell column uses the target cell's unadjusted bootstrap p-value. The familywise column records whether any of the 14 Holm-adjusted cells rejects. The adjusted target column gives power for Turkish/Gemini after the full family correction.

| Unique tasks | Seed rows per cell | Null one-cell false positive | Null familywise false positive | Alternative one-cell power | Alternative TR/Gemini Holm power |
|---:|---:|---:|---:|---:|---:|
| 4 | 8 | 0.120 [0.082, 0.172] (24/200) | 0.515 [0.446, 0.583] (103/200) | 0.145 [0.103, 0.200] (29/200) | 0.060 [0.035, 0.102] (12/200) |
| 10 | 20 | 0.080 [0.050, 0.126] (16/200) | 0.220 [0.168, 0.282] (44/200) | 0.150 [0.107, 0.206] (30/200) | 0.055 [0.031, 0.096] (11/200) |
| 20 | 40 | 0.030 [0.014, 0.064] (6/200) | 0.070 [0.042, 0.114] (14/200) | 0.170 [0.124, 0.228] (34/200) | 0.050 [0.027, 0.090] (10/200) |
| 25 | 50 | 0.080 [0.050, 0.126] (16/200) | 0.090 [0.058, 0.138] (18/200) | 0.230 [0.177, 0.293] (46/200) | 0.055 [0.031, 0.096] (11/200) |
| 50 | 100 | 0.055 [0.031, 0.096] (11/200) | 0.110 [0.074, 0.161] (22/200) | 0.260 [0.204, 0.325] (52/200) | 0.045 [0.024, 0.083] (9/200) |

At n=20, the Turkish/Gemini Holm false-positive estimate is `0.010 [0.003, 0.036] (2/200)`, the 14-cell familywise false-positive estimate is `0.070 [0.042, 0.114] (14/200)`, and the adjusted Turkish/Gemini power under the stated alternative is `0.050 [0.027, 0.090] (10/200)`.

The conditional alternative uses source rates `p_EN=0.866`, `p_TR=0.793`, `T_EN=0.900`, and `T_TR=0.300` from `analysis/bfcl/main_results_cf_summary.json`. The expected Turkish/Gemini CF and Delta under these rates are `1.244` and `-0.216`. These power estimates are conditional on that observed effect and the synthetic shared-difficulty/repair model. They are not prospective guarantees or evidence that any task count is adequate. A prospective 20-task collection should sample five distinct scenario indices per category and preserve a horizon distribution close to the current tasks; the n=20 curve is only an idealized independent-cluster calculation.

The Monte Carlo rate intervals are Wilson 95% intervals based on 200 replicates. Their width remains material near a 5% error rate, especially at the smallest task counts. The 5,000 bootstrap resamples reduce the 14-cell Holm resolution floor to `0.00280`; they add numerical resolution, not independent task information.

The simulated false-positive rates, especially for the 14-cell family, are higher than the nominal 5% level under this shared-difficulty null. This indicates that the current one-sided bootstrap-tail p-value is not validated for this dependence structure. The results should not be used as confirmatory inference until the test is recalibrated or validated under a null model that matches the task and seed dependencies.

## Reproduction and limits

The fixed generator and bootstrap seed schedules, full process parameters, point estimates, Monte Carlo counts, and Wilson intervals are in `analysis/bfcl/cf_calibration_summary.json`. The earlier calibration remains nested under `historical_v1`; the expanded values do not reproduce the review-response simulation figures.

Reproduce with `python scripts/run_cf_calibration.py`. For a shorter diagnostic run, pass `--mc-replicates` and `--bootstrap-resamples`; do not use reduced settings as the reported results.
