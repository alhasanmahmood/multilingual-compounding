# Multilingual Long-Horizon Tool-Use Compounding

This repository is the standalone reproducibility package for the paper
**"When Do Errors Compound Across Languages? A Descriptive Study of
Multilingual Long-Horizon Tool Use."**
It contains the manuscript source, the curated BFCL evaluation artifacts needed
to reproduce the reported analyses, and the minimal code required to regenerate
the compounding (E3), decomposition (E4), and robustness (E6) results.

The package is organized so that reviewers can reproduce the paper **without
making new API calls**. Optional scripts are included for recollecting
evaluation trajectories when API credentials are available.

## Start here: reproduce the paper offline

The revised paper uses the completed **20-scenario expansion**, with eight
languages, two seeds, and two backbones: **640 full trajectories and 5,952
isolated replays**. Each cell has forty trajectories and 372 replays. Tasks
were selected before outcomes, with one category variant per distinct scenario.
Primary outputs use `newstudy20261010_expansion`; raw inputs use
`newstudy20261010`. Translation review corrected 86 of 140 non-English query
sets before collection. An author subsequently reported reviewing the
translations through a mixture of target-language text and English
backtranslations and judged them adequate. This is author review, rather
than independent bilingual expert validation. The attestation is stored
separately in `analysis/bfcl/newstudy20261010_author_translation_review.json`
to preserve the collected-data hashes.

After activating the environment under **Setup**, audit the complete saved data
without provider calls:

```powershell
.\.venv\Scripts\python.exe scripts/analyze_completed_expansion.py
```

To regenerate all four analyses into a new output prefix, use:

```powershell
.\.venv\Scripts\python.exe scripts/analyze_completed_expansion.py --run-analyses --output-prefix expansion_reproduction
```

The command refuses existing output files. The completed overview and exact
reproduction commands are in
`analysis/bfcl/newstudy20261010_expansion_overview.md`. Generated main-paper
displays are in `paper/generated/`. The older steps 1-3 under **Reproduction
workflow** reproduce the historical pilot. Step 4 regenerates synthetic
calibration and its historical plug-in power diagnostic. These commands make
no new model calls.

The October 12 manuscript refinement has a read-only source/display audit:

```powershell
.\.venv\Scripts\python.exe scripts/audit_submission_paper.py
```

It checks the official style-file hashes, internal references, named local
artifacts, primary table and plot values, and translation-score displays.
To compare a separately regenerated bundle, add `--reproduction-prefix`
with its output prefix. Primary table/plot regeneration through
`scripts/update_expansion_manuscript.py` preserves edited manuscript prose.
The measurement contracts and release checks are documented in
`docs/REPRODUCIBILITY.md`.

### Translation consistency diagnostic

The later LaBSE check compares 602 nonempty English source turns directly with
the translated turns used in collection, 86 per target language. Per-turn
scores, per-language distributions, and deliberate-error probes are saved in
`analysis/bfcl/newstudy20261010_labse_*`. Cosine similarity is a consistency
diagnostic, not an accuracy percentage or a certification of translation
quality. The paper reports it in the translation diagnostics appendix.

To rerun locally in a separate environment and output directory:

```powershell
python -m venv .venv-labse
.\.venv-labse\Scripts\python.exe -m pip install -r requirements.txt -r requirements-translation-diagnostics.txt
.\.venv-labse\Scripts\python.exe scripts/run_translation_similarity.py --model-revision 836121a0533e5664b21c7aacc5d22951f2b8b25b --device cpu --output-dir analysis/bfcl/labse_reproduction
```

The first scoring run downloads the public encoder, approximately 1.9 GB.
It makes no paid model-API calls. The script verifies the frozen cache and
source/review hashes and refuses output overwrites or token truncation.
For an already downloaded snapshot, `--model-path` with `--model-manifest`
also verifies the model files against the saved manifest. The executed
package versions are in `analysis/bfcl/newstudy20261011_labse_environment.txt`.
The independent AI inspection of low-scoring pairs and string-level flags
is recorded separately from the author's review.

The historical study contains **four category variants of one scenario, eight languages, two seeds, and two
backbones**. It has 128 full trajectories and 1,280 isolated replays, giving
eight task trials and 80 replay outcomes per backbone-language cell. The
`gemini_*_pilot_seed*` files contain Gemini runs for all four category variants;
`claude_sonnet46_*_expanded_seed*` files contain Claude runs for the same four
variants. Both use seeds 0 and 1. The four category variants share BFCL scenario
index 0, so they are not four independent scenarios. Reported task and replay
rates use add-one smoothing.

| Local evidence package | Path | What it contains |
|---|---|---|
| Historical localized inputs | `data/bfcl/localized_queries/bfcl_multiturn_localizations.jsonl` | 32 historical task-language queries with fidelity and reference-call checks |
| Primary localized inputs | `data/bfcl/localized_queries/newstudy20261010_bfcl_multiturn_localizations.jsonl` | 160 fresh task-language queries; 140 non-English rows AI-reviewed, 86 corrected; row statuses preserve collection-time human approval pending, with subsequent author review recorded separately |
| Full trajectories | `data/bfcl/runs/` | Per-model, language, and run-label JSONL files with execution outcomes |
| Isolated replay | `data/bfcl/isolated_replays/` | Critical steps replayed with gold preceding context |
| Collection provenance | `data/bfcl/metadata/` | Provider/model settings and run metadata |
| Historical point estimates | `analysis/bfcl/main_results_cf_summary.json` | Common and position-specific nulls; scenario uncertainty unavailable with one cluster |
| Historical stage and detour analysis | `analysis/bfcl/e4_main_summary.json` | Historical stage counts, trajectory rows, and matched-validity estimates |
| Historical robustness checks | `analysis/bfcl/e6_main_summary.json` | Historical horizon, seed, localization, and language holdout analyses |
| Synthetic calibration | `analysis/bfcl/cf_calibration_summary.json` | Explicit simulated processes, fixed seeds, and conditional power estimates |
| Historical scenario/variant sensitivity | `analysis/bfcl/task_sensitivity_summary.json` | 5,000-draw conditional diagnostics and variant holdouts for the one-scenario pilot |
| Fresh expansion design | `analysis/bfcl/newstudy20261010_plan.json` | 20 distinct scenarios, five per category, selected before outcome collection |
| Primary expansion evidence | `analysis/bfcl/newstudy20261010_expansion_collection_audit.json` | Complete coverage, source/translation hashes, and model identities for 640 trajectories and 5,952 replays |
| Primary expansion analyses | `analysis/bfcl/newstudy20261010_expansion_*` | Compounding, decomposition, robustness, scenario influence, and paper results note |

Direct audit found translated exact search literals in 12/28 historical
non-English rows despite the automatic check passing. These inputs confound
four language comparisons; see `analysis/bfcl/historical_translation_literal_audit.json`.
Historical inputs stay with their outputs. The completed fresh cohort uses
corrected translations collected separately; historical results are not pooled
into the primary comparison.

The empirical study is descriptive. Increasing to 5,000 resamples removes the
original numerical testing floor, but synthetic null checks show that the
bootstrap tails are not calibrated significance tests. Historical scenario-level
intervals are unavailable because there is only one scenario. Greedy detour
flags are reference-relative and include every successful trace; matched-bin
outcomes do not establish causal error propagation. The simulation illustrates
the metric under specified assumptions and does not enlarge the BFCL task set.

## Repository layout

```text
multilingual-compounding/
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .env.example
├── paper/
│   ├── main.tex
│   ├── references.bib
│   ├── acl.sty
│   └── acl_natbib.bst
├── scripts/
│   ├── run_compounding_analysis.py
│   ├── run_decomposition_analysis.py
│   ├── run_robustness_analysis.py
│   ├── run_cf_calibration.py
│   └── run_bfcl_evaluation.py
├── src/
│   └── multilingual_compounding/
│       ├── metrics.py
│       ├── evaluation.py
│       ├── decomposition.py
│       ├── robustness.py
│       ├── localization.py
│       ├── bfcl_vendor.py
│       ├── openrouter_handler.py
│       ├── settings.py
│       ├── paths.py
│       └── env.py
├── data/
│   └── bfcl/
│       ├── localized_queries/
│       ├── runs/
│       ├── isolated_replays/
│       └── metadata/
├── analysis/
│   └── bfcl/
├── docs/
│   ├── FILES_RATIONALE.md
│   ├── PROJECT_EXPLAINER.md
│   ├── e3_metrics_contract.md
│   └── e4_decomposition_contract.md
├── tests/
└── vendor/
    └── berkeley-function-call-leaderboard/
```

## What is included

The repository contains the files needed to reproduce the paper offline:

- localized BFCL multi-turn queries for eight languages;
- full-task runs and isolated step replays for the main backbone pair
  (Gemini 3 Flash Preview and Claude Sonnet 4.6);
- supporting GPT-4o pilot and native-OpenAI diagnostic artifacts referenced in
  the manuscript's backbone-exclusion discussion;
- canonical analysis outputs for compounding, decomposition, and robustness;
- manuscript source and bibliography;
- a pinned BFCL vendor checkout used by the evaluation adapters.

Rerunning the paper analyses does **not** require new model calls.

### Preparing a release copy

Maintainers can export the curated files to a new directory outside the
checkout, with a per-file SHA-256 manifest and a ZIP archive:

```bash
python scripts/build_offline_release.py --output-dir ../multilingual-reliability-release
```

The exporter copies only the curated files tracked by Git and records their
exact hashes. Private revision notes, review correspondence, credentials,
environments, model weights, logs, and render histories are excluded from the
tracked release. It does not publish anything or certify anonymity. Public
provenance uses relative paths or clearly marked local-snapshot placeholders.
An anonymous reviewer package still needs a separate inspection before upload
or linking from the manuscript.

## Setup

Use a fresh Python 3.11 environment and install both files below. The pinned
`tree_sitter==0.21.3` dependency is required by the vendored evaluator;
reusing an environment with a newer parser can fail before analysis starts.
The saved evidence files are marked `-text` in `.gitattributes` so Git preserves
the exact bytes checked by the collection and translation hashes.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-reproduction.txt
python -m pip install -e .
```

## Reproduction workflow

Run all commands from the repository root.

The following steps reproduce the historical pilot. Use the expansion command
under **Start here** for the current main table and figure.

### 1. Historical compounding analysis (E3)

```bash
python scripts/run_compounding_analysis.py \
  --models gemini claude_sonnet46 \
  --run-labels pilot_seed0 pilot_seed1 expanded_seed0 expanded_seed1 \
  --per-category-limit 1 \
  --artifact-prefix main_results
```

This regenerates:

- `analysis/bfcl/main_results_cf_summary.json`
- `analysis/bfcl/main_results_report.md`

### 2. Historical decomposition analysis (E4)

```bash
python scripts/run_decomposition_analysis.py \
  --models gemini claude_sonnet46 \
  --run-labels pilot_seed0 pilot_seed1 expanded_seed0 expanded_seed1 \
  --per-category-limit 1 \
  --artifact-prefix e4_main
```

This regenerates:

- `analysis/bfcl/e4_main_summary.json`
- `analysis/bfcl/e4_main_report.md`

### 3. Robustness analysis (E6)

```bash
python scripts/run_robustness_analysis.py \
  --models gemini claude_sonnet46 \
  --run-labels pilot_seed0 pilot_seed1 expanded_seed0 expanded_seed1 \
  --per-category-limit 1 \
  --artifact-prefix e6_main
```

This regenerates:

- `analysis/bfcl/e6_main_summary.json`
- `analysis/bfcl/e6_main_report.md`

### 4. Synthetic CF calibration and conditional power diagnostic

```bash
python scripts/run_cf_calibration.py
```

This regenerates `analysis/bfcl/cf_calibration_summary.json` and
`analysis/bfcl/cf_calibration_report.md`. It uses the same smoothed metric and
bootstrap functions as the paper, with fixed random seeds. Large-sample
processes check independence, shared multiplicative survival, additive repair,
unequal position difficulty, and shared task difficulty. The task-count curves
use 200 Monte Carlo datasets, 5,000 scenario-cluster resamples, two seed rows per
scenario, and the complete 14-comparison family. The report includes null
false-positive rates, conditional power, and Wilson intervals. Legacy output is
retained under `historical_v1`. The null checks do not validate confirmatory inference.

### 5. Scenario and category-variant sensitivity

```bash
python scripts/run_task_sensitivity.py --n-boot 5000 --bootstrap-seed 0
```

This writes `analysis/bfcl/task_sensitivity_summary.json` and its report.
Point estimates reproduce the historical main summary. The four variants share
one scenario, so the primary scenario bootstrap is unavailable. The eight-row
variant/seed bootstrap and variant holdouts are conditional sensitivity diagnostics.

The fresh collection is documented in [the collection protocol](docs/COLLECTION_PROTOCOL.md).
Its translations and model artifacts use the separate `newstudy20261010` prefix.
Collection is not evidence until all expected trajectories and replays are audited.

### 6. Unit tests

```bash
python -m unittest discover -s tests -v
```

### 7. Compile the paper

If a LaTeX toolchain is available locally:

```bash
cd paper
latexmk -pdf main.tex
```

If `latexmk` is unavailable:

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Figures in the manuscript are drawn with TikZ; no external figure assets are
required.

## Optional: recollect BFCL evaluation trajectories

The paper already includes saved runs and replays. This step is only needed if
you want to rebuild trajectories from the public BFCL instances.

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` and `OPENAI_BASE_URL` (OpenRouter-compatible endpoints
   are supported; `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` aliases are also
   accepted).

Example command for the main backbone pair:

```bash
python scripts/run_bfcl_evaluation.py \
  --models gemini claude_sonnet46 \
  --run-labels pilot_seed0 pilot_seed1 \
  --per-category-limit 1 \
  --artifact-prefix recollect
```

After recollection, rerun the three analysis scripts above.

## Pinned benchmark version

- Gorilla / BFCL commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Evaluation temperature: `0.001`
- Main languages: English, Arabic, Turkish, Chinese, Hindi, Japanese, Spanish, Swahili

## Data provenance

- Task instances and executable environments come from the public BFCL v3
  multi-turn release (pinned vendor checkout under `vendor/`).
- Localized user queries were produced by the repository translation pipeline.
  The fresh cohort received direct AI review, exact-literal/alignment checks,
  subsequent author review using target text and backtranslations, and a local
  LaBSE consistency diagnostic. These do not establish independent bilingual
  expert validation. Historical checks missed disclosed literal drift.
- Model trajectories were collected through OpenAI-compatible chat-completions
  endpoints and are retained under `data/bfcl/`.

## Additional documentation

- `docs/FILES_RATIONALE.md` explains why each included path is part of the
  submission package.
- `docs/PROJECT_EXPLAINER.md` gives a plain-language overview of the method and
  experiments.
- `docs/e3_metrics_contract.md` and `docs/e4_decomposition_contract.md` specify
  the programmatic input/output contracts used by the analysis scripts.
