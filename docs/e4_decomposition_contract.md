# E4 Decomposition Contract

This document fixes the `E4` decomposition input/output contract for the
BFCL-based heterogeneity analysis.

## Goal

Given existing BFCL full-run and isolated-replay artifacts, compute:

1. failure-stage mix
2. failure-type mix
3. propagation rate
4. recovery rate
5. replay-matched propagation/recovery comparisons

The contract is intentionally programmatic. It does not rely on model-judge
annotations.

## Inputs

### 1. Full-run records

Source:

- `data/bfcl/runs/*.jsonl`

Required fields per record:

- `task_id`
- `language_code`
- `model_key`
- `run_label`
- `success`
- `evaluation.decoded_result`

### 2. Isolated-replay records

Source:

- `data/bfcl/isolated_replays/*.jsonl`

Required fields per record:

- `task_id`
- `language_code`
- `model_key`
- `run_label`
- `turn_index`
- `step_index`
- `gold_call`
- `candidate_call`
- `valid`
- `evaluation.error_type`

### 3. Task references

Source:

- BFCL tasks loaded from the same categories used in the run/replay slice

Required fields:

- ordered gold call sequence per task

## Stage taxonomy

Each invalid replay step is assigned exactly one stage:

1. `intent_selection`
2. `argument_parameter`
3. `sequencing_planning`

Recovery is not a per-step share row in the summary table. It is reported as a
trajectory-level rate after an off-reference step occurs.

## Failure-type taxonomy

Each invalid replay step is assigned exactly one coarse failure type:

1. `no_call`
2. `wrong_function`
3. `wrong_arguments`
4. `wrong_order_or_context`

## Programmatic labeling rules

Let the current gold call be the ordered BFCL reference call at the replay
step's flat index.

1. If there is no parsable `candidate_call`, label:
   - stage: `intent_selection`
   - failure type: `no_call`
2. If the candidate function name equals the gold function name:
   - stage: `argument_parameter`
   - failure type: `wrong_arguments`
   - except if the arguments normalize identically but BFCL still reports an
     instance-state mismatch, then label stage `sequencing_planning` and failure
     type `wrong_context`
3. If the candidate function name appears elsewhere in the same task's gold
   sequence (earlier or later), label:
   - stage: `sequencing_planning`
   - failure type: `wrong_order_or_context`
4. Otherwise label:
   - stage: `intent_selection`
   - failure type: `wrong_function`

## Trajectory alignment rule

Trajectory-level propagation/recovery is computed from the full-run decoded call
trace against the ordered gold sequence.

Alignment is greedy:

1. flatten the decoded full-run call sequence
2. keep a pointer to the next unmatched gold call
3. if the current emitted call matches the next gold call after argument-order
   normalization, advance the pointer
4. otherwise mark the emitted call as an off-reference detour and keep the
   pointer fixed

This intentionally permits successful runs that contain harmless or recoverable
extra calls before later realigning with the reference trajectory.

## Trajectory metrics

For each full-run record:

- `has_detour`: at least one off-reference emitted call under the greedy
  alignment above
- `propagated_to_failure`: `has_detour == 1` and `success == 0`
- `recovered`: `has_detour == 1` and `success == 1`

For any group of runs:

- `propagation_rate = mean(propagated_to_failure | has_detour == 1)`
- `recovery_rate = mean(recovered | has_detour == 1)`

These sum to 1 by construction for groups with at least one detour-bearing run.

## Matched-validity comparison

To reduce pure error-frequency confounding, matched propagation/recovery is
computed only inside replay-validity bins shared by English and the comparison
group.

Per full-run trial:

- `replay_valid_steps`
- `replay_total_steps`

define the validity bin.

For each shared bin:

1. compute English propagation/recovery among detour-bearing runs in that bin
2. compute comparison-group propagation/recovery among detour-bearing runs in
   that bin
3. weight the bin by the smaller of the two group counts

The final matched rates are the weighted averages over shared bins.

## Outputs

Primary script:

- `scripts/run_decomposition_analysis.py`

Artifacts:

- `analysis/bfcl/<prefix>_summary.json`
- `analysis/bfcl/<prefix>_report.md`

The summary JSON must contain:

- `scope`
- `aggregates.english.replay`
- `aggregates.english.trajectory`
- `aggregates.non_english.replay`
- `aggregates.non_english.trajectory`
- `aggregates.matched_validity`
- `cells`

The markdown report must expose the aggregate stage shares, trajectory rates,
matched-validity rates, and per-cell highlights needed for manuscript table
construction.
