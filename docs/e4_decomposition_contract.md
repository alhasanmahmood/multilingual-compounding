# E4 Decomposition Contract

This document records the behavior implemented by
`src/multilingual_compounding/decomposition.py` and
`scripts/run_decomposition_analysis.py`. The analysis labels observed replay
errors and full-run differences from a BFCL reference sequence. These labels
are descriptive and are not model-judge annotations.

## Inputs

Full-run records come from `data/bfcl/runs/*.jsonl` and must include
`task_id`, `language_code`, `model_key`, `run_label`, `success`, and
`evaluation.decoded_result`.

Isolated replay records come from `data/bfcl/isolated_replays/*.jsonl` and
must include `task_id`, `language_code`, `model_key`, `run_label`,
`turn_index`, `step_index`, `gold_call`, `candidate_call`, `valid`, and
`evaluation.error_type`.

The matching BFCL task data supplies the ordered gold call sequence for each
task. Replay rows are sorted by turn and step before classification. Full-run
calls are flattened in their emitted order.

## Replay stage labels

Every invalid replay step is assigned one stage:

1. `intent_selection`: no parsable candidate call, an invalid gold call, or a
   different candidate function that is outside the reference sequence and is
   not marked as an instance-state mismatch.
2. `argument_parameter`: the candidate names the expected function but its
   arguments differ, or the evaluator reports an unexpected mismatch despite
   identical parsed arguments.
3. `sequencing_planning`: the candidate names a function from another point in
   the reference sequence, or the evaluator reports an instance-state mismatch
   for a same or different candidate function.

These stage labels describe where a replay mismatch appears to occur. They do
not establish the model's internal cause.

## Failure-type labels

The failure type is a separate field from the stage. The classifier can emit
the following labels:

| Failure type | Assignment rule |
|--------------|-----------------|
| `no_call` | Candidate is absent, unparsable, or marked `replay:no_call`. |
| `unknown_gold_call` | The gold call cannot be parsed. |
| `wrong_arguments` | Candidate and gold function names match, but parsed arguments differ. |
| `unexpected_same_call_mismatch` | Parsed function and arguments match, but replay is still marked invalid for a reason other than the handled instance-state mismatch. |
| `wrong_context` | Parsed function and arguments match, but the evaluator reports `multi_turn:instance_state_mismatch`. |
| `wrong_order_or_context` | The candidate function occurs elsewhere in the task's gold sequence, or a different function is marked with an instance-state mismatch. |
| `wrong_function` | The candidate function differs from the expected function and does not occur elsewhere in the gold sequence. |

The rule order in `_classify_stage` determines the output. In particular,
`wrong_context` and `unexpected_same_call_mismatch` are valid labels even
though they were absent from the earlier four-label list. Do not merge this
failure-type taxonomy with the three stage labels.

## Full-trajectory reference alignment

The decoded call trace is compared greedily with the ordered BFCL reference.
Function names and arguments are parsed, and argument order is normalized. A
call that matches the next unmatched reference call advances the pointer. Any
other emitted call is marked as a detour and leaves the pointer in place. This
can mark harmless alternatives or extra calls in a successful run. A detour
does not by itself mean that the full task failed.

The trajectory row sets:

- `has_detour` when at least one emitted call differs from the next reference
  call under that alignment;
- `propagated_to_failure` when `has_detour` is true and the benchmark outcome
  is failure;
- `recovered` when `has_detour` is true and the benchmark outcome is success.

The reported propagation and recovery rates are conditional outcome shares
among detour-bearing trajectories. The labels describe co-occurrence of a
reference detour and the final benchmark outcome. They do not show that the
detour caused that outcome or that a model repaired its internal state.

The first detour also receives stage and failure-type labels from the same
classifier, with an off-reference marker. These trajectory labels are not the
replay failure counts. For example, the instance-state mismatch labels
`wrong_context` and `unexpected_same_call_mismatch` describe replay outcomes
and are not used as evidence that a full-run detour caused failure.

## Matched replay-validity comparison

For detour-bearing runs, the script groups trajectories by the exact pair
`(replay_valid_steps, replay_total_steps)`. It keeps bins present in both the
English and comparison-language group. Within each bin, it computes each
group's propagation and recovery shares and weights those shares by the
smaller group count. The output `weighted_pairs` is this sum of bin weights;
it does not mean that individual English and non-English runs were paired.

This descriptive weighting compares groups with the same replay count and
validity count. It does not remove all confounding and is not a causal
adjustment. The rates still condition on having a reference detour.

## Outputs and scope

The script writes `analysis/bfcl/<prefix>_summary.json` and
`analysis/bfcl/<prefix>_report.md`. The primary fresh-cohort outputs use the
`newstudy20261010_expansion_decomposition` prefix. The historical pilot has a
separate summary and report and is not pooled with the fresh cohort.

The JSON contains the analysis scope, English and non-English aggregates,
matched-validity results, and per-model/language cells with replay and
trajectory summaries. It preserves individual trajectory rows and their first
detour labels for audit.
