# Multilingual Long-Horizon Tool-Use Compounding

This repository is the standalone reproducibility package for the paper
**"When Do Errors Compound Across Languages?: Heterogeneous Multilingual
Reliability of Long-Horizon Agentic Tool Use."**
It contains the manuscript source, the curated BFCL evaluation artifacts needed
to reproduce the reported analyses, and the minimal code required to regenerate
the compounding (E3), decomposition (E4), and robustness (E6) results.

The package is organized so that reviewers can reproduce the paper **without
making new API calls**. Optional scripts are included for recollecting
evaluation trajectories when API credentials are available.

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

The repository already ships everything needed to reproduce the paper offline:

- localized BFCL multi-turn queries for eight languages;
- full-task runs and isolated step replays for the main backbone pair
  (Gemini 3 Flash Preview and Claude Sonnet 4.6);
- supporting GPT-4o pilot and native-OpenAI diagnostic artifacts referenced in
  the manuscript's backbone-exclusion discussion;
- canonical analysis outputs for compounding, decomposition, and robustness;
- manuscript source and bibliography;
- a pinned BFCL vendor checkout used by the evaluation adapters.

Rerunning the paper analyses does **not** require new model calls.

## Setup

Use Python 3.11 or newer.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Reproduction workflow

Run all commands from the repository root.

### 1. Compounding analysis (E3 / Table 1)

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

### 2. Decomposition analysis (E4 / stage and recovery tables)

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

### 4. Unit tests

```bash
python -m unittest discover -s tests -v
```

### 5. Compile the paper

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
- Localized user queries were produced by the repository translation pipeline
  and validated with back-translation plus reference-call invariance checks.
- Model trajectories were collected through OpenAI-compatible chat-completions
  endpoints and are retained under `data/bfcl/`.

## Additional documentation

- `docs/FILES_RATIONALE.md` explains why each included path is part of the
  submission package.
- `docs/PROJECT_EXPLAINER.md` gives a plain-language overview of the method and
  experiments.
- `docs/e3_metrics_contract.md` and `docs/e4_decomposition_contract.md` specify
  the programmatic input/output contracts used by the analysis scripts.
