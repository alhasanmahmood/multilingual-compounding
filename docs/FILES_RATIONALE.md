# Included Files and Selection Rationale

This repository was carved out of a larger research monorepo to isolate the
third paper's reproducibility package. Every included path below is required
either to rerun the reported analyses offline, optionally recollect evaluation
trajectories, compile the manuscript, or audit the measurement contracts used
in the paper.

## Included directories

### `paper/`

Contains the submission manuscript and ACL style files.

| Path | Rationale |
|------|-----------|
| `paper/main.tex` | Manuscript source of record for the submission. |
| `paper/references.bib` | Bibliography consumed by `main.tex`. |
| `paper/acl.sty` | ACL style file required for compilation. |
| `paper/acl_natbib.bst` | Bibliography style required for compilation. |

Orphan TikZ preview PNGs and internal drafting notes from the development tree
were excluded because the manuscript embeds figures via TikZ and does not
`\includegraphics` those assets.

### `src/multilingual_compounding/`

Provides the minimal Python package needed by the analysis and evaluation
scripts.

| Path | Rationale |
|------|-----------|
| `metrics.py` | Reference compounding-factor math (CF, Delta, bootstrap, Holm). |
| `evaluation.py` | Artifact I/O, CF summarization, and optional end-to-end evaluation. |
| `decomposition.py` | E4 stage mix, propagation, and recovery analysis. |
| `robustness.py` | E6 fidelity filtering, K-sensitivity, LOLO, and seed variance. |
| `localization.py` | Query localization / back-translation helpers for optional recollection. |
| `bfcl_vendor.py` | Adapter over the pinned BFCL vendor for tasks, handlers, and replay. |
| `openrouter_handler.py` | OpenAI-compatible chat-completions handler used for model calls. |
| `settings.py` | Languages, model registry, temperature, and pinned BFCL commit. |
| `paths.py` | Canonical repository path constants. |
| `env.py` | Minimal `.env` loader with OpenRouter alias support. |

### `scripts/`

Executable entry points for the standalone submission repository.

| Path | Rationale |
|------|-----------|
| `run_compounding_analysis.py` | Offline regeneration of the main CF / Table 1 outputs. |
| `run_decomposition_analysis.py` | Offline regeneration of E4 stage and recovery outputs. |
| `run_robustness_analysis.py` | Offline regeneration of E6 robustness outputs. |
| `run_bfcl_evaluation.py` | Optional full evaluation / recollection pipeline (API required). |

### `data/bfcl/`

Curated evaluation artifacts sufficient to reproduce the paper without new API
calls.

| Path | Rationale |
|------|-----------|
| `localized_queries/bfcl_multiturn_localizations.jsonl` | Eight-language localized BFCL queries plus invariance/fidelity metadata. |
| `runs/gemini_*_pilot_seed{0,1}.jsonl` | Main Gemini full-task trajectories used in Table 1 / E4 / E6. |
| `runs/claude_sonnet46_*_expanded_seed{0,1}.jsonl` | Main Claude full-task trajectories used in Table 1 / E4 / E6. |
| `runs/gpt4o_*_pilot_seed{0,1}.jsonl` | Supporting GPT-4o trajectories for the English-baseline exclusion narrative. |
| `runs/gpt4o_openai_EN_native_retry_seed0.jsonl` | Direct-OpenAI diagnostic trajectory referenced in the manuscript. |
| Matching `isolated_replays/*.jsonl` | Isolated step-validity evidence required by CF and matched recovery analyses. |
| `metadata/*.json` | Provenance metadata for the retained evaluation slices. |

Screening, principled-backbone exploration, and non-main expanded runs were
excluded because they are not required to regenerate the reported tables and
would inflate the package without changing paper numbers.

### `analysis/bfcl/`

Canonical analysis outputs used in the manuscript (also regenerable offline).

| Path | Rationale |
|------|-----------|
| `main_results_cf_summary.json` | Canonical compounding summary underlying Table 1 and appendix CIs. |
| `main_results_report.md` | Human-readable snapshot of the same CF results. |
| `e4_main_summary.json` / `e4_main_report.md` | Stage mix and matched propagation/recovery results. |
| `e6_main_summary.json` / `e6_main_report.md` | Localization robustness, K-sensitivity, and LOLO diagnostics. |

### `docs/`

| Path | Rationale |
|------|-----------|
| `FILES_RATIONALE.md` | This selection-rationale document. |
| `PROJECT_EXPLAINER.md` | Plain-language overview for reviewers and reimplementers. |
| `e3_metrics_contract.md` | Locked input/output contract for compounding metrics. |
| `e4_decomposition_contract.md` | Locked input/output contract for decomposition analysis. |

### `tests/`

Unit tests covering metrics, settings resolution, environment loading,
decomposition helpers, and robustness filters. Included so reviewers can
sanity-check the math and contracts without API access.

### `vendor/berkeley-function-call-leaderboard/`

Pinned BFCL source and data needed by `bfcl_vendor.py`. Only the BFCL subtree
is retained; unrelated Gorilla projects (raft, goex, agent-arena, etc.) from the
upstream clone were removed to keep the package small and focused.

## Included root files

| Path | Rationale |
|------|-----------|
| `README.md` | Reviewer-facing setup and reproduction instructions. |
| `pyproject.toml` | Installable package metadata for `pip install -e .`. |
| `requirements.txt` | Minimal dependency pin list. |
| `.env.example` | Documents environment variables for optional recollection. |
| `.gitignore` | Keeps secrets, virtualenvs, and LaTeX build debris out of the repo. |
| `LICENSE` | Preserves the upstream MIT license. |

## Artifact decisions

`data/bfcl/` retains the exact run and replay files needed to regenerate the
paper's main tables offline, plus the GPT-4o artifacts required to audit the
backbone-exclusion claims. `analysis/bfcl/` retains the canonical regenerated
summaries so reviewers can inspect reported numbers without first running the
scripts, while the scripts remain available to reproduce those files from data.
