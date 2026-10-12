# Offline manuscript results for `newstudy20261010_expansion`

Generated from the passed completion audit and the completed offline summary bundle. This helper made no API calls and did not edit the manuscript source.

## Validated collection counts

| Quantity | Observed count |
|---|---:|
| Selected tasks | 20 |
| Unique scenarios | 20 |
| Categories | 4 |
| Tasks by category | `{"multi_turn_base": 5, "multi_turn_long_context": 5, "multi_turn_miss_func": 5, "multi_turn_miss_param": 5}` |
| Languages | 8 (EN, AR, TR, ZH, HI, JA, ES, SW) |
| Model backbones | 2 (gemini, claude_sonnet46) |
| Run labels | 2 (expansion_seed0, expansion_seed1) |
| Localization rows checked | 160 |
| Gold-call positions | 186 |
| Full trajectories | 640 |
| Isolated replays | 5952 |

The offline summaries cover the same 20 task IDs, languages, backbones, run labels, trajectories, and replay rows. The main CF summary reports K=9 from a mean horizon of 9.30.

## K=9 main estimates under the common null

The LaTeX table contains the per-cell estimates. CF is marked NR when the summary marks it non-reportable. The reported 95% intervals use the 2.5th and 97.5th bootstrap percentiles over the selected underlying scenarios.

| Language | Model | Delta | CF | Delta interval | CF interval | CF reportable |
|---|---|---:|---:|---|---|---|
| AR | claude_sonnet46 | -0.511 | -0.597 | [-1.293, 0.127] | [-4.512, 4.916] | True |
| AR | gemini | 0.201 | 0.577 | [-0.434, 0.772] | [-2.524, 3.941] | True |
| ES | claude_sonnet46 | -0.276 | 0.308 | [-0.972, 0.352] | [-1.332, 1.977] | True |
| ES | gemini | 0.080 | 0.774 | [-0.712, 0.797] | [-5.425, 5.869] | True |
| HI | claude_sonnet46 | -0.341 | -0.694 | [-1.028, 0.231] | [-5.208, 5.068] | True |
| HI | gemini | -0.657 | -7.538 | [-1.429, -0.029] | [-15.613, 16.900] | True |
| JA | claude_sonnet46 | -0.238 | 0.152 | [-0.985, 0.386] | [-2.441, 2.804] | True |
| JA | gemini | 0.213 | 0.644 | [-0.568, 0.906] | [-1.566, 4.355] | True |
| SW | claude_sonnet46 | -0.705 | -0.371 | [-1.503, -0.017] | [-5.615, 4.960] | True |
| SW | gemini | -0.478 | -0.574 | [-1.411, 0.218] | [-4.298, 4.205] | True |
| TR | claude_sonnet46 | -0.081 | 0.000 | [-0.472, 0.361] | [-3.728, 3.833] | True |
| TR | gemini | 0.080 | 0.774 | [-0.704, 0.758] | [-3.515, 5.109] | True |
| ZH | claude_sonnet46 | -0.760 | -0.476 | [-1.669, -0.079] | [-3.301, 1.147] | True |
| ZH | gemini | 0.154 | 0.209 | [-0.559, 0.832] | [-1.732, 1.929] | True |

Primary bootstrap settings: 5000 resamples, seed 0, cluster unit `underlying_task`. Scenario clusters by backbone: `{"claude_sonnet46": 20, "gemini": 20}`.

## K and null sensitivity

The point ranges below summarize the non-English model/language cells for each K and null. Per-cell point estimates and both underlying-task and task-seed bootstrap intervals are in the accompanying CSV. These ranges summarize cells, not a population-level effect.

| K | Null | CF-reportable cells | Delta range across cells | CF range among reportable cells | Underlying-task bootstrap cells | Task-seed bootstrap cells |
|---:|---|---:|---|---|---:|---:|
| 8 | common | 14 | [-0.702, 0.149] | [-8.480, 0.871] | 14/14 (available) | 14/14 (available) |
| 8 | position | 14 | [-0.925, 0.089] | [-1.680, 1.188] | 14/14 (available) | 14/14 (available) |
| 9 | common | 14 | [-0.760, 0.213] | [-7.538, 0.774] | 14/14 (available) | 14/14 (available) |
| 9 | position | 14 | [-0.890, 0.161] | [-1.870, 0.780] | 14/14 (available) | 14/14 (available) |
| 10 | common | 14 | [-0.817, 0.280] | [-6.784, 0.697] | 14/14 (available) | 14/14 (available) |
| 10 | position | 13 | [-0.807, 0.304] | [-0.721, 2.888] | 14/14 (available) | 14/14 (available) |

Underlying-task interval rows use the primary CF summary; task-seed rows use the task-sensitivity summary. Both summaries record the same resample count and seed. The main CF records follow plan/CLI model order gemini, claude_sonnet46, while sensitivity sorts the task/model tuples, consuming backbone draws in claude_sonnet46, gemini order. The bootstrap_cf function advances one seeded RNG across backbones in record insertion order, so a shared seed does not guarantee the same per-backbone resamples. The reported intervals are therefore sourced and labeled separately, not presented as identical across summaries. Underlying-task intervals describe variability across this selected scenario set, not confirmatory population inference. Task-seed intervals are conditional on selected tasks and seeds. Bootstrap tail values are uncalibrated directional diagnostics, so this note makes no significance claim.

## E4 decomposition counts

Stage and failure-type maps below report exact invalid replay-step counts from the decomposition summary. Trajectory counts come from the same summary.

| Group | Invalid replay steps | Stage counts | Failure-type counts | Trajectory runs | Runs with detour |
|---|---:|---|---|---:|---:|
| English | 292 | `{"argument_parameter": 34, "intent_selection": 54, "sequencing_planning": 204}` | `{"no_call": 28, "wrong_arguments": 34, "wrong_function": 26, "wrong_order_or_context": 204}` | 80 | 78 |
| Non-English | 2026 | `{"argument_parameter": 265, "intent_selection": 393, "sequencing_planning": 1368}` | `{"no_call": 175, "wrong_arguments": 265, "wrong_function": 218, "wrong_order_or_context": 1368}` | 560 | 546 |

## Leave-one-scenario influence at K=9

Across 14 non-English model/language cells, omitting at least one selected scenario changed the Delta sign in 4 of 14 cells and changed CF reportability in 5 of 14 cells.
Scenarios that changed at least one cell: `{"scenario_0": {"cf_reportability_cells": 0, "delta_sign_cells": 1}, "scenario_18": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_39": {"cf_reportability_cells": 0, "delta_sign_cells": 1}, "scenario_55": {"cf_reportability_cells": 2, "delta_sign_cells": 1}, "scenario_58": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_59": {"cf_reportability_cells": 1, "delta_sign_cells": 3}, "scenario_63": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_65": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_69": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_71": {"cf_reportability_cells": 2, "delta_sign_cells": 0}, "scenario_90": {"cf_reportability_cells": 2, "delta_sign_cells": 0}, "scenario_92": {"cf_reportability_cells": 1, "delta_sign_cells": 0}, "scenario_97": {"cf_reportability_cells": 1, "delta_sign_cells": 2}}`. Each audited task maps one-to-one to a scenario family. Task-seed clusters by backbone: `{"claude_sonnet46": 40, "gemini": 40}`.

These leave-one-scenario results are influence diagnostics over the selected scenarios. They are not significance tests.

## Reproducibility and outputs

- Completion audit: `analysis/bfcl/newstudy20261010_expansion_collection_audit.json` (SHA-256 `df3b288c6d5a0be6db9c529fc028370d793df6bf725fddc0922761538b530606`).
- CF summary: `analysis/bfcl/newstudy20261010_expansion_cf_summary.json` (SHA-256 `785536c73b19317f9ee7e1a69e01faf9eef6c87907f162c7279297005151ff95`).
- Decomposition summary: `analysis/bfcl/newstudy20261010_expansion_decomposition_summary.json` (SHA-256 `937e208eeefe454f2f0446cc90f3c0e2cf75d2d94c96f7aeab0586a63bfdde06`).
- Robustness summary: `analysis/bfcl/newstudy20261010_expansion_robustness_summary.json` (SHA-256 `653cfd5200276bb75dd32a9a5fe76e53ab1d73b9953955de617d0dd506f25181`).
- Task-sensitivity summary: `analysis/bfcl/newstudy20261010_expansion_task_sensitivity_summary.json` (SHA-256 `242557655558152e3991efecf4f388b8ae2592c8418d22d6b3a7c3c9bddf70e9`).
- Plan SHA-256 in completion audit: `5f8c17e8357c17bacb0ab180a5dbf05238bf992237b01c092fb55ea04d72b79d`.
- Raw artifact manifest SHA-256 in completion audit: `cfaebf25031926ee42788a220a67926a4c9e5d892ac5b20faca50d4952651149`.
- LaTeX table: `paper/generated/newstudy20261010_expansion_results_table.tex`.
- K/null/cluster plot data: `paper/generated/newstudy20261010_expansion_cf_sensitivity_plot_data.csv`.

Reproduce after the completion audit and offline summaries exist:

```powershell
.\python scripts/render_expansion_paper_results.py --output-prefix newstudy20261010_expansion
```

The LaTeX table and CSV are standalone artifacts for review. They are not inserted into `paper/main.tex` automatically.
