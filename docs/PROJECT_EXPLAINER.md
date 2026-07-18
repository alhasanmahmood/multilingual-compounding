# Project Explainer

Plain-language overview of the method and experiments in
**"When Do Errors Compound Across Languages?: Heterogeneous Multilingual
Reliability of Long-Horizon Agentic Tool Use."**

## One-sentence summary

The paper asks whether a small per-step disadvantage in non-English tool use
stays small over a long trajectory or grows into a larger full-task gap, and
finds heterogeneous behavior rather than a universal compounding law.

## Problem

Most tool-use evaluation is English-only. In agentic settings, one early mistake
can poison later steps. The scientific question is therefore trajectory-level:

> Do multilingual errors compound beyond what a step-level independence null
> would predict?

## Method sketch

1. **Localize BFCL multi-turn user queries** into eight languages while keeping
   tool schemas English and language-invariant.
2. **Run full multi-turn tasks** and score success by executable system state.
3. **Replay each critical step in isolation** with gold preceding context to
   estimate per-step validity without in-trajectory confounding.
4. **Compute compounding metrics** comparing observed task success against an
   independence null (`CF`, `Delta`, bootstrap CIs, Holm adjustment).
5. **Decompose failures** into stage mix plus matched propagation/recovery.
6. **Check robustness** via localization fidelity/invariance, K-sensitivity,
   leave-one-language-out, and seed variance.

## Main evidence base

- Benchmark: BFCL v3 multi-turn (pinned vendor commit in `settings.py`)
- Languages: EN, AR, TR, ZH, HI, JA, ES, SW
- Main backbones: Gemini 3 Flash Preview and Claude Sonnet 4.6
- Supporting exclusion narrative: GPT-4o English baseline collapse under the
  evaluation setup

## What the package reproduces offline

From saved runs and replays under `data/bfcl/`, the analysis scripts regenerate:

- compounding summaries used for Table 1 / appendix CIs;
- E4 stage and matched recovery summaries;
- E6 robustness summaries.

No new API calls are required for those steps.

## Reading guide for the code

| Module | Role |
|--------|------|
| `metrics.py` | Pure math for CF / Delta / bootstrap |
| `evaluation.py` | Artifact loading and CF summarization |
| `decomposition.py` | E4 programmatic decomposition |
| `robustness.py` | E6 robustness diagnostics |
| `bfcl_vendor.py` | BFCL task/handler/replay adapter |

For path-by-path inclusion decisions, see `docs/FILES_RATIONALE.md`.
