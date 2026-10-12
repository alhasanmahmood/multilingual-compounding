# Collection protocol

The frozen plan is `analysis/bfcl/newstudy20261010_plan.json`. It selects one
category variant per distinct BFCL scenario, with five tasks in each of four
multi-turn categories. Complete scenario families with 8 to 10 reference calls
are sorted by descending horizon and numeric ID, then assigned to categories
in round-robin order. Selection precedes model outcomes. Category and scenario
are confounded; this design does not estimate category effects.

The selected tasks have seven ten-call, twelve nine-call, and one eight-call
reference sequences, totaling 186 calls and a mean length of 9.3. Eight
languages yield 160 task-language queries. Gemini 3 Flash Preview and Claude
Sonnet 4.6 were served through OpenRouter at temperature 0.001, with seeds 0
and 1. Exact requested and provider-reported identities and settings are in
the plan, raw records, and metadata files.

Only user queries are localized; tool schemas and reference solutions stay
in English. AI review, exact-literal checks, source/target hashes, and turn
alignment were resolved before collection. The later author review is stored
as a separate attestation rather than retroactively changing frozen row-level
approval statuses. Review does not certify independent bilingual accuracy.

The pipeline runs each full trajectory through the pinned BFCL execution
checker. It separately replays every reference call with gold preceding
context, producing 640 full trajectories and 5,952 isolated replays. Gold-call
environment preflight checks are released with the collection. The current
coordinator validates the plan and complete localized-query matrix before
creating provider jobs, and resumes only validated checkpoints.

The saved collection is complete. Reproduce its four analyses with the README's
offline command; recollection is optional and incurs provider charges. For new
collection, use a new plan and prefixes, resolve translation review, then run
the environment and input preflight before launching the coordinator. Do not
use partial output as a completed cohort or overwrite the published inputs.

Historical pilot files contain four category variants of one scenario and
remain separate. Their disclosed literal drift and GPT-4o diagnostics are
retained for inspection, not pooled with the primary experiment. Synthetic
calibration is a conditional diagnostic, not additional benchmark evidence
or a demonstration of adequate statistical power.
