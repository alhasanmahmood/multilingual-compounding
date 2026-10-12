# Included Files and Selection Rationale

This repository is the reproducibility package for the paper. Its primary
evidence is a fresh, horizon-selected BFCL slice with 20 distinct scenarios,
five tasks from each of four categories, eight languages, two models, and two
seeds. It contains 640 full trajectories and 5,952 isolated replays. The
historical pilot is retained separately: its four category variants all share
scenario 0, yielding 128 trajectories and 1,280 replays. Historical and fresh
results are not pooled. Both cohorts support descriptive analysis of these
selected tasks; they do not establish population-wide effects.

The files below let readers inspect the reported evidence, regenerate the
offline analyses, or compile the manuscript. Recollecting model outputs is an
optional workflow and requires provider credentials.

## Paper source

| Path | Purpose |
|------|---------|
| `paper/main.tex` | Submission manuscript source. |
| `paper/references.bib` | Bibliography used by the manuscript. |
| `paper/acl.sty`, `paper/acl_natbib.bst` | Official style and bibliography files used for COLING through ARR. |
| `paper/generated/newstudy20261010_main_table.tex` | Generated primary result table included in the manuscript. |
| `paper/generated/newstudy20261010_delta_figure.tex` | Generated primary Delta figure included in the manuscript. |
| `paper/generated/newstudy20261011_translation_diagnostics.tex` | Generated translation diagnostic table included in the appendix. |
| `paper/generated/newstudy20261010_expansion_results_table.tex` and `paper/generated/newstudy20261010_expansion_cf_sensitivity_plot_data.csv` | Additional generated result display and plot data for audit. |

## Code

`src/multilingual_compounding/` contains the analysis and evaluation package.
The most relevant commands are:

| Script | Purpose |
|--------|---------|
| `scripts/analyze_completed_expansion.py` | Checks completeness and provenance of the saved 20-scenario cohort; with `--run-analyses`, regenerates the four offline analyses. |
| `scripts/run_compounding_analysis.py` | Computes the primary compounding metrics from full runs and isolated replays. |
| `scripts/run_decomposition_analysis.py` | Computes replay failure stages and reference-relative trajectory outcomes. |
| `scripts/run_robustness_analysis.py` | Checks localization policy and other robustness conditions. |
| `scripts/run_task_sensitivity.py` | Measures sensitivity to scenario omissions, horizons, null definitions, and task/seed resampling. |
| `scripts/run_cf_calibration.py` | Runs stated synthetic processes to check the behavior and limits of the bootstrap tail diagnostic. These are simulations, not added benchmark data. |
| `scripts/run_translation_similarity.py` | Scores source and target turns with pinned LaBSE and creates deliberate-error probes. Scores are similarity diagnostics, not translation accuracy. |
| `scripts/render_expansion_paper_results.py` | Rebuilds the generated result displays from saved analysis outputs. |
| `scripts/audit_submission_paper.py` | Checks the manuscript's local references and generated values against saved artifacts. |

The optional collection workflow is in `scripts/plan_bfcl_expansion.py`,
`scripts/validate_expansion_environment.py`,
`scripts/run_expansion_collection.py`, and
`scripts/run_bfcl_evaluation.py`. It is not needed to reproduce the reported
offline results.

## Evidence and generated analyses

| Path | Purpose |
|------|---------|
| `data/bfcl/localized_queries/newstudy20261010_bfcl_multiturn_localizations.jsonl` | The 160 collected task-language query rows. Its hash is checked by the collection audit and translation diagnostic. |
| `data/bfcl/runs/newstudy20261010_{gemini,claude_sonnet46}_{LANG}_expansion_seed{0,1}.jsonl` | The 640 primary full-task trajectories across eight languages, two models, and two seeds. |
| `data/bfcl/isolated_replays/newstudy20261010_{gemini,claude_sonnet46}_{LANG}_expansion_seed{0,1}.jsonl` | The 5,952 primary isolated replay results. |
| `data/bfcl/metadata/newstudy20261010_evaluation_metadata_*.json` | Provider, model, run, and artifact provenance. |
| `analysis/bfcl/newstudy20261010_plan.json` and `analysis/bfcl/newstudy20261010_expansion_collection_audit.json` | The fixed task plan and strict completeness and provenance audit. |
| `analysis/bfcl/newstudy20261010_expansion_cf_summary.json` | Primary compounding estimates used by the result display. |
| `analysis/bfcl/newstudy20261010_expansion_decomposition_summary.json` and matching report | Primary replay and trajectory decomposition. |
| `analysis/bfcl/newstudy20261010_expansion_robustness_summary.json` and matching report | Primary robustness analyses. |
| `analysis/bfcl/newstudy20261010_expansion_task_sensitivity_summary.json` and matching report | Scenario omission, horizon, and task/seed sensitivity results. |
| `analysis/bfcl/cf_calibration_summary.json` and `analysis/bfcl/cf_calibration_report.md` | Synthetic calibration evidence and its stated assumptions. |
| `analysis/bfcl/newstudy20261010_labse_pairs.csv`, `newstudy20261010_labse_controls.csv`, and `newstudy20261010_labse_summary.json` | Translation similarity scores and deliberate-error probes. The model manifest and environment freeze record the encoder and software versions. |
| `analysis/bfcl/newstudy20261010_author_translation_review.json` | Separate record of the author's later review of target text and English backtranslations. It does not change collection-time row statuses or establish independent expert validation. |
| `tests/` | Focused tests for the analysis, collection checks, and artifact renderers. |

Historical inputs and outputs remain in their original paths, such as
`data/bfcl/localized_queries/bfcl_multiturn_localizations.jsonl` and
`analysis/bfcl/main_results_cf_summary.json`. They are not substitutes for the
fresh primary cohort and must not be combined with its estimates.

## Documents and supporting data

`docs/PROJECT_EXPLAINER.md` gives a plain-language account of the study.
`docs/COLLECTION_PROTOCOL.md` records the selection and collection process.
`docs/REPRODUCIBILITY.md` explains evidence checks, software versions, translation
review, and release exclusions. The E3 and E4 contract notes document
their analysis interfaces. `vendor/berkeley-function-call-leaderboard/`
contains the pinned BFCL source and data required by the analysis and optional
collection code.

## Keep private or machine-specific material out of the release

Exclude `reviews/`, `.env`, local virtual environments, local model weights and
model caches, package installation or download logs, `data/bfcl/trace_db/`, and
temporary LaTeX build files. Also exclude internal baseline copies, rendered
page images, and working histories under
`analysis/bfcl/submission_refinement_20261012/` unless a particular audit file
is intentionally selected for release. These items contain private review
material, credentials, machine-specific state, duplicated runtime traces, or
internal drafting history. The public package still needs the primary JSONL
trajectories and replays, localization cache, provenance metadata, fixed plan,
analysis outputs, source code, generated displays, and manuscript source.
Private reviewer correspondence, account-balance notes, collection supervisor
state, duplicate review presentations, and local audit passports remain ignored.
The three indexed AI translation-review JSONs and targeted LaBSE review JSON
are retained as scientific input-quality evidence, with the later author
attestation kept separate from the collected cache.
