# BFCL Task-Cluster Sensitivity Report

This offline analysis resamples saved BFCL task records. It does not add model calls or benchmark tasks.

- BFCL category variants: 4 (multi_turn_base_0, multi_turn_miss_func_0, multi_turn_miss_param_0, multi_turn_long_context_0)
- Languages: EN, AR, TR, ZH, HI, JA, ES, SW
- Models: gemini, claude_sonnet46
- Full trajectories / isolated replays: 128 / 1280
- Bootstrap resamples and seed: 5000 / 0
- Cluster counts per model: gemini: 8 variant-seed clusters, 1 underlying scenario families; claude_sonnet46: 8 variant-seed clusters, 1 underlying scenario families
- Scenario-family grouping: {'scenario_0': ['multi_turn_base_0', 'multi_turn_long_context_0', 'multi_turn_miss_func_0', 'multi_turn_miss_param_0']}
- Existing point-estimate check: match

The four category variants share one underlying scenario family. Scenario-level bootstrap intervals and directional tail diagnostics are unavailable because one cluster cannot estimate variance. The task-seed intervals below are variant-level sensitivity diagnostics, not independent-scenario inference. Simulation also finds the bootstrap tail probabilities are not calibrated inferential p-values, so neither raw nor Holm-adjusted tails support significance claims. Variant holdouts report point-estimate sensitivity without significance tests.

## K sweep summary

The table counts how many of the 14 non-English model cells change Delta sign or CF reportability after at least one category variant is removed.

| K | Null | Delta sign changes | CF reportability changes |
|---:|---|---:|---:|
| 9 | common | 3/14 | 0/14 |
| 9 | position | 2/14 | 0/14 |
| 10 | common | 3/14 | 0/14 |
| 10 | position | 2/14 | 0/14 |
| 11 | common | 2/14 | 0/14 |
| 11 | position | 2/14 | 0/14 |

## Turkish/Gemini at K=10 under the common null

- **Underlying-scenario bootstrap:** unavailable with cluster counts {'claude_sonnet46': 1, 'gemini': 1}; Only one underlying scenario family is present; a bootstrap variance estimate requires at least two clusters.
- **Variant-seed bootstrap sensitivity:** CF=1.244, Delta=-0.216, CF 95% CI=[0.459, 3.679], Delta 95% CI=[-1.456, 0.573], raw tail diagnostic=0.3107, Holm-adjusted tail diagnostic=1.0000, reportable CF=True. These intervals resample the eight category-variant/seed rows.
- **Full-data point estimate:** CF=1.244, Delta=-0.216, reportable CF=True.
- **Leave-one-category-variant-out point estimates:**
  - Omit `multi_turn_base_0`: Delta=-1.161, CF=2.480, r_ind=0.456.
  - Omit `multi_turn_long_context_0`: Delta=-0.063, CF=1.080, r_ind=0.456.
  - Omit `multi_turn_miss_func_0`: Delta=0.308, CF=0.734, r_ind=0.315.
  - Omit `multi_turn_miss_param_0`: Delta=-0.063, CF=1.080, r_ind=0.456.
- **Variant influence:** Delta sign changes across omissions=True; CF reportability changes=False; Delta range across omissions=[-1.161, 0.308]; reportable CF range=[0.734, 2.480].

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/run_task_sensitivity.py --n-boot 5000 --bootstrap-seed 0
```

The JSON records all cells, both nulls, task-seed bootstrap diagnostics, the unavailable scenario-level bootstrap reason, and each leave-one-category-variant-out estimate.
