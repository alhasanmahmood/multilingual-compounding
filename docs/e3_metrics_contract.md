# E3 Metrics Contract

This note documents the data and resampling rules used by
`src/multilingual_compounding/metrics.py` and
`scripts/run_compounding_analysis.py`.

## Required record shape

Each `TaskRecord` passed to the metrics module must provide:

- `task_id`: stable task-seed identifier used to pair language rows
- `language`: language label; `EN` and `English` are accepted as English
- `backbone`: model identifier
- `success`: full-task outcome in `{0,1}`
- `step_validity`: ordered isolated-replay outcomes in `{0,1}` for the critical
  calls in the task

For the released cohort, `evaluation.py` constructs `task_id` from the BFCL
task ID and run label, for example
`multi_turn_base_0::expansion_seed0`. It also populates optional
`underlying_task_id` with the shared scenario identifier and `task_variant_id`
with the category-specific BFCL task ID. `underlying_task_id` falls back to
`task_id` when it is absent. The language rows for a scenario stay together
when that scenario is sampled.

## Measurement rule

`step_validity` must come from isolated replay of each critical call with the
gold preceding context. It must not come from calls emitted within the full
trajectory. `success` is the separately scored full-task outcome.

For each language and model, the metrics compute a smoothed full-task success
rate and a smoothed isolated-call validity rate. The common independence null
uses `p^K`; the position-specific null uses the product of smoothed rates at
each call position, with the documented fallback for missing positions. Both
are comparison references, not claims that real agent calls are independent.
`Delta` is the difference between log observed relative success and log null
relative success. `CF` is their ratio and is withheld when the null-relative
log value is too close to zero.

## Bootstrap units

`scripts/run_compounding_analysis.py` defaults to
`--cluster-unit underlying_task`. For the primary cohort this samples the 20
distinct scenario IDs within each model, keeping all language rows and both
seeds for a sampled scenario together. It therefore estimates variation over
the selected scenarios, conditional on this design. It does not turn the
horizon-selected BFCL slice into a representative task sample.

The alternative `task_seed` unit samples each category-specific task and run
label separately. It is reported as a sensitivity view and conditions on those
task and seed rows. The lower-level `metrics.bootstrap_cf()` function defaults
to `task_seed` when called directly; callers should set the unit explicitly
when they need to reproduce the primary script.

The historical pilot has four category variants but only one underlying
scenario. An `underlying_task` bootstrap cannot estimate scenario variation
for that cohort and the analysis reports it as unavailable. Treating variants
or seeds as independent scenarios would change the sampling unit without
support from the design.

## Interpretation limit

The bootstrap tail fields retain legacy names such as `p_raw` and `p_holm`,
but synthetic calibration shows that they are not generally calibrated
inferential p-values. Read them only as directional diagnostics. They do not
establish a statistically significant effect. `Delta` point estimates and
intervals describe this selected dataset and do not identify a causal mechanism.

## Regression coverage

`tests/test_compounding_metrics.py` covers English baseline aliases, paired
resampling, the `task_seed` and `underlying_task` units, and toy examples for
the metric calculations. The full analysis path is checked separately by the
collection audit and offline reproduction commands documented in the
repository README.
