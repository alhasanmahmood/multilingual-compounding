# Project Explainer

Plain-language guide to **"When Do Errors Compound Across Languages?: A
Descriptive Study of Multilingual Long-Horizon Tool Use."**

## Research question

The paper asks whether differences in individual tool calls between English and
other languages correspond to differences in success over a full multi-step
task. An isolated replay estimates whether a model can make one critical call
when given the correct earlier state. A full trajectory shows what happens
when the model carries out the whole task itself.

## What was measured

The primary study uses 20 distinct BFCL scenarios, five tasks from each of four
categories. The tasks have 8 to 10 critical calls, with a mean of 9.3. The
study covers English, Arabic, Turkish, Chinese, Hindi, Japanese, Spanish, and
Swahili, using Gemini 3 Flash Preview and Claude Sonnet 4.6 with two seeds per
task. This produces 640 full trajectories and 5,952 isolated replay results.
The fixed task plan and collection audit are in
`analysis/bfcl/newstudy20261010_plan.json` and
`analysis/bfcl/newstudy20261010_expansion_collection_audit.json`.

The slice was selected by task length and completeness. Each underlying
scenario appears in one category, so scenario and category effects cannot be
separated. The results describe this selected BFCL slice. They do not establish
that the same patterns hold for other tasks, models, or tool environments.

The earlier pilot remains separate. It has four category variants of one
underlying scenario, with 128 trajectories and 1,280 replays. Those variants
are not four independent scenarios, and their results are not pooled with the
20-scenario study.

## How the comparison works

1. Localize the user queries into eight languages while keeping the tools and
   tool schemas in English.
2. Run each task from start to finish. Score success from the resulting system
   state.
3. Replay each critical call separately with the correct preceding state. Use
   these results to estimate single-call validity without errors from earlier
   calls in the full trajectory.
4. Compare observed task success with a reference calculation that assumes
   critical calls succeed independently. `Delta` is the difference on a log
   scale; the compounding factor (`CF`) is a ratio of those log differences.
   The reference is a comparison null, not a realistic model of every agent.
5. Describe which stages contain replay errors and whether full traces finish
   after a call that differs from the BFCL reference sequence. These
   reference-relative outcomes do not establish that the earlier call caused
   the final success or failure.
6. Check whether estimates change across task horizons, scenario omissions,
   localization filters, and synthetic processes.

The main paper emphasizes `Delta` because `CF` becomes unstable when the
predicted non-English to English success ratio under the null is close to one.
Results are descriptive:
synthetic checks found that the bootstrap tail values are not calibrated
inferential p-values. The paper does not claim a confirmed general compounding
effect, a causal recovery effect, or significance from those tails.

## Translation review

Before collection, an AI review checked the localized queries and 86 of the
140 non-English rows were corrected. The author later reported reviewing a
mixture of target-language text and English backtranslations and judged the
translations adequate. This was not independent bilingual expert validation.

The later LaBSE analysis compares 602 nonempty English source turns directly
with their aligned target-language turns. It reports cosine similarity and
tests deliberately changed numbers, quoted literals, filenames, negations, and
task pairings. Some deliberately changed constraints still receive high
similarity scores. These values are therefore consistency diagnostics, not
translation accuracy percentages or a pass threshold. Details and row-level
scores are in `docs/TRANSLATION_VALIDATION_20261011.md` and the associated
`analysis/bfcl/newstudy20261010_labse_*` files.

## Reproducing the saved results

The core analyses run from saved files and make no model API calls. First check
the collection and then regenerate the analyses to a new output prefix:

```powershell
.\.venv\Scripts\python.exe scripts/analyze_completed_expansion.py
.\.venv\Scripts\python.exe scripts/analyze_completed_expansion.py --run-analyses --output-prefix expansion_reproduction
```

The first command checks that all planned trajectories and replays are present
and match their provenance. The second regenerates compounding,
decomposition, robustness, and task-sensitivity outputs. It refuses to
overwrite existing outputs. The exact original commands and generated paper
displays are listed in `analysis/bfcl/newstudy20261010_expansion_overview.md`.
The synthetic calibration uses `scripts/run_cf_calibration.py`. The optional
translation diagnostic uses `scripts/run_translation_similarity.py` and its
separate pinned LaBSE dependency environment. The README contains setup and
reproduction details.

## Reading guide

| File | Purpose |
|------|---------|
| `src/multilingual_compounding/metrics.py` | Compounding and `Delta` calculations, smoothing, and bootstrap resampling. |
| `src/multilingual_compounding/evaluation.py` | Loads full runs and isolated replays and builds analysis records. |
| `src/multilingual_compounding/decomposition.py` | Classifies replay errors and summarizes reference-relative trajectory outcomes. |
| `src/multilingual_compounding/robustness.py` | Checks localization and other robustness settings. |
| `analysis/bfcl/newstudy20261010_expansion_*` | Saved primary analysis summaries and reports. |
| `paper/main.tex` | Manuscript source. |

For path selection and release exclusions, see `docs/FILES_RATIONALE.md`.
