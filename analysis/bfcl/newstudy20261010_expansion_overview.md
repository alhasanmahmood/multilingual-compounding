# Completed BFCL Expansion Overview

This report summarizes saved model outputs only. It makes no new model or translation API calls.

- Collection status: `complete`
- Selected BFCL tasks: `20` across `20` unique numeric scenario IDs
- Categories: `4`; tasks per category: `{'multi_turn_base': 5, 'multi_turn_miss_func': 5, 'multi_turn_miss_param': 5, 'multi_turn_long_context': 5}`
- Critical gold-call positions per task: `{'multi_turn_base_0': 10, 'multi_turn_base_63': 10, 'multi_turn_base_18': 9, 'multi_turn_base_65': 9, 'multi_turn_base_80': 9, 'multi_turn_miss_func_10': 10, 'multi_turn_miss_func_90': 10, 'multi_turn_miss_func_55': 9, 'multi_turn_miss_func_69': 9, 'multi_turn_miss_func_92': 9, 'multi_turn_miss_param_39': 10, 'multi_turn_miss_param_97': 10, 'multi_turn_miss_param_58': 9, 'multi_turn_miss_param_70': 9, 'multi_turn_miss_param_171': 9, 'multi_turn_long_context_59': 10, 'multi_turn_long_context_6': 9, 'multi_turn_long_context_61': 9, 'multi_turn_long_context_71': 9, 'multi_turn_long_context_2': 8}`
- Total gold-call positions: `186`
- Full trajectories and isolated replays: `640` and `5952`
- Languages: `EN, AR, TR, ZH, HI, JA, ES, SW`; models: `gemini, claude_sonnet46`; run labels: `expansion_seed0, expansion_seed1`
- Localization rows checked: `160`
- Provider-reported evaluation model IDs: `{'gemini': ['google/gemini-3-flash-preview'], 'claude_sonnet46': ['anthropic/claude-sonnet-4.6']}`
- Raw artifact manifest SHA-256: `cfaebf25031926ee42788a220a67926a4c9e5d892ac5b20faca50d4952651149`
- Plan SHA-256: `5f8c17e8357c17bacb0ab180a5dbf05238bf992237b01c092fb55ea04d72b79d`; localization cache SHA-256: `04f858c21801117fe0f99d6974773d1818c10d91a3ecbbf1579c707455a4e034`
- CF point-estimate snapshot uses K=`9` (mean horizon `9.30`); bootstrap unit is `underlying_task` with `5000` resamples.
- Bootstrap tail values are uncalibrated directional diagnostics, not inferential p-values.
- The plan assigns one unique scenario per category-specific task; category and scenario are not independently crossed, so category contrasts remain descriptive and confounded by scenario assignment.

## New compounding point estimates

| Language | Model | T | Delta | r_ind | CF | CF reportable | CF 95% CI | Delta 95% CI |
|---|---|---:|---:|---:|---:|---|---|---|
| AR | claude_sonnet46 | 0.4524 | -0.5111 | 1.3772 | -0.5970 | True | [-4.5121, 4.9162] | [-1.2928, 0.1272] |
| AR | gemini | 0.4524 | 0.2014 | 0.6213 | 0.5767 | True | [-2.5242, 3.9414] | [-0.4339, 0.7724] |
| ES | claude_sonnet46 | 0.6190 | -0.2757 | 1.4893 | 0.3078 | True | [-1.3322, 1.9774] | [-0.9716, 0.3517] |
| ES | gemini | 0.4524 | 0.0801 | 0.7015 | 0.7741 | True | [-5.4248, 5.8690] | [-0.7122, 0.7973] |
| HI | claude_sonnet46 | 0.4762 | -0.3411 | 1.2231 | -0.6941 | True | [-5.2085, 5.0678] | [-1.0281, 0.2311] |
| HI | gemini | 0.3333 | -0.6567 | 1.0800 | -7.5376 | True | [-15.6128, 16.9004] | [-1.4294, -0.0286] |
| JA | claude_sonnet46 | 0.5714 | -0.2381 | 1.3240 | 0.1516 | True | [-2.4410, 2.8037] | [-0.9848, 0.3857] |
| JA | gemini | 0.4048 | 0.2132 | 0.5494 | 0.6440 | True | [-1.5656, 4.3549] | [-0.5684, 0.9061] |
| SW | claude_sonnet46 | 0.4524 | -0.7055 | 1.6727 | -0.3714 | True | [-5.6151, 4.9604] | [-1.5035, -0.0166] |
| SW | gemini | 0.5000 | -0.4782 | 1.3550 | -0.5739 | True | [-4.2976, 4.2052] | [-1.4105, 0.2184] |
| TR | claude_sonnet46 | 0.5476 | -0.0811 | 1.0845 | 0.0000 | True | [-3.7282, 3.8330] | [-0.4720, 0.3606] |
| TR | gemini | 0.4524 | 0.0801 | 0.7015 | 0.7741 | True | [-3.5146, 5.1089] | [-0.7035, 0.7580] |
| ZH | claude_sonnet46 | 0.4286 | -0.7595 | 1.6727 | -0.4765 | True | [-3.3009, 1.1473] | [-1.6694, -0.0785] |
| ZH | gemini | 0.5714 | 0.1544 | 0.8226 | 0.2091 | True | [-1.7321, 1.9292] | [-0.5587, 0.8322] |

## Leave-one-task-variant-out stability

- K=8: Delta sign changed after at least one task omission in `5/14` non-English model/language cells; CF reportability changed in `5/14` cells.
- K=9: Delta sign changed after at least one task omission in `4/14` non-English model/language cells; CF reportability changed in `5/14` cells.
- K=10: Delta sign changed after at least one task omission in `3/14` non-English model/language cells; CF reportability changed in `5/14` cells.

These are influence diagnostics over the selected 20 task variants. They do not estimate a category effect.

## Offline analyses

- CF summary/report: `analysis/bfcl/newstudy20261010_expansion_cf_summary.json`, `analysis/bfcl/newstudy20261010_expansion_report.md`
- Decomposition summary/report: `analysis/bfcl/newstudy20261010_expansion_decomposition_summary.json`, `analysis/bfcl/newstudy20261010_expansion_decomposition_report.md`
- Robustness summary/report: `analysis/bfcl/newstudy20261010_expansion_robustness_summary.json`, `analysis/bfcl/newstudy20261010_expansion_robustness_report.md`
- Task-sensitivity summary/report: `analysis/bfcl/newstudy20261010_expansion_task_sensitivity_summary.json`, `analysis/bfcl/newstudy20261010_expansion_task_sensitivity_report.md`
- Localization-robustness filtered scope: `640` full trajectories and `5952` replays across `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`.

Reproduction commands used:

```powershell
python 'scripts/run_compounding_analysis.py' --models gemini claude_sonnet46 --task-ids multi_turn_base_0 multi_turn_base_63 multi_turn_base_18 multi_turn_base_65 multi_turn_base_80 multi_turn_miss_func_10 multi_turn_miss_func_90 multi_turn_miss_func_55 multi_turn_miss_func_69 multi_turn_miss_func_92 multi_turn_miss_param_39 multi_turn_miss_param_97 multi_turn_miss_param_58 multi_turn_miss_param_70 multi_turn_miss_param_171 multi_turn_long_context_59 multi_turn_long_context_6 multi_turn_long_context_61 multi_turn_long_context_71 multi_turn_long_context_2 --run-labels expansion_seed0 expansion_seed1 --language-codes EN AR TR ZH HI JA ES SW --artifact-prefix newstudy20261010_expansion --input-artifact-prefix newstudy20261010 --n-boot 5000 --bootstrap-seed 0 --cluster-unit underlying_task
python 'scripts/run_decomposition_analysis.py' --models gemini claude_sonnet46 --task-ids multi_turn_base_0 multi_turn_base_63 multi_turn_base_18 multi_turn_base_65 multi_turn_base_80 multi_turn_miss_func_10 multi_turn_miss_func_90 multi_turn_miss_func_55 multi_turn_miss_func_69 multi_turn_miss_func_92 multi_turn_miss_param_39 multi_turn_miss_param_97 multi_turn_miss_param_58 multi_turn_miss_param_70 multi_turn_miss_param_171 multi_turn_long_context_59 multi_turn_long_context_6 multi_turn_long_context_61 multi_turn_long_context_71 multi_turn_long_context_2 --run-labels expansion_seed0 expansion_seed1 --language-codes EN AR TR ZH HI JA ES SW --artifact-prefix newstudy20261010_expansion_decomposition --input-artifact-prefix newstudy20261010
python 'scripts/run_robustness_analysis.py' --models gemini claude_sonnet46 --task-ids multi_turn_base_0 multi_turn_base_63 multi_turn_base_18 multi_turn_base_65 multi_turn_base_80 multi_turn_miss_func_10 multi_turn_miss_func_90 multi_turn_miss_func_55 multi_turn_miss_func_69 multi_turn_miss_func_92 multi_turn_miss_param_39 multi_turn_miss_param_97 multi_turn_miss_param_58 multi_turn_miss_param_70 multi_turn_miss_param_171 multi_turn_long_context_59 multi_turn_long_context_6 multi_turn_long_context_61 multi_turn_long_context_71 multi_turn_long_context_2 --run-labels expansion_seed0 expansion_seed1 --language-codes EN AR TR ZH HI JA ES SW --artifact-prefix newstudy20261010_expansion_robustness --input-artifact-prefix newstudy20261010 --localization-prefix newstudy20261010 --localization-policy reviewed --n-boot 5000 --bootstrap-seed 0 --cluster-unit underlying_task
python 'scripts/run_task_sensitivity.py' --models gemini claude_sonnet46 --task-ids multi_turn_base_0 multi_turn_base_63 multi_turn_base_18 multi_turn_base_65 multi_turn_base_80 multi_turn_miss_func_10 multi_turn_miss_func_90 multi_turn_miss_func_55 multi_turn_miss_func_69 multi_turn_miss_func_92 multi_turn_miss_param_39 multi_turn_miss_param_97 multi_turn_miss_param_58 multi_turn_miss_param_70 multi_turn_miss_param_171 multi_turn_long_context_59 multi_turn_long_context_6 multi_turn_long_context_61 multi_turn_long_context_71 multi_turn_long_context_2 --run-labels expansion_seed0 expansion_seed1 --language-codes EN AR TR ZH HI JA ES SW --input-artifact-prefix newstudy20261010 --main-summary-path 'analysis/bfcl/newstudy20261010_expansion_cf_summary.json' --summary-path 'analysis/bfcl/newstudy20261010_expansion_task_sensitivity_summary.json' --report-path 'analysis/bfcl/newstudy20261010_expansion_task_sensitivity_report.md' --n-boot 5000 --bootstrap-seed 0 --k-values 8 9 10
```
