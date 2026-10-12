# BFCL Task-Cluster Sensitivity Report

This offline analysis resamples saved BFCL task records. It does not add model calls or benchmark tasks.

- BFCL tasks: 20 (multi_turn_base_0, multi_turn_base_63, multi_turn_base_18, multi_turn_base_65, multi_turn_base_80, multi_turn_miss_func_10, multi_turn_miss_func_90, multi_turn_miss_func_55, multi_turn_miss_func_69, multi_turn_miss_func_92, multi_turn_miss_param_39, multi_turn_miss_param_97, multi_turn_miss_param_58, multi_turn_miss_param_70, multi_turn_miss_param_171, multi_turn_long_context_59, multi_turn_long_context_6, multi_turn_long_context_61, multi_turn_long_context_71, multi_turn_long_context_2)
- Languages: EN, AR, TR, ZH, HI, JA, ES, SW
- Models: gemini, claude_sonnet46
- Full trajectories / isolated replays: 640 / 5952
- Bootstrap resamples and seed: 5000 / 0
- Cluster counts per model: gemini: 40 variant-seed clusters, 20 underlying scenario families; claude_sonnet46: 40 variant-seed clusters, 20 underlying scenario families
- Scenario-family grouping: {'scenario_0': ['multi_turn_base_0'], 'scenario_10': ['multi_turn_miss_func_10'], 'scenario_171': ['multi_turn_miss_param_171'], 'scenario_18': ['multi_turn_base_18'], 'scenario_2': ['multi_turn_long_context_2'], 'scenario_39': ['multi_turn_miss_param_39'], 'scenario_55': ['multi_turn_miss_func_55'], 'scenario_58': ['multi_turn_miss_param_58'], 'scenario_59': ['multi_turn_long_context_59'], 'scenario_6': ['multi_turn_long_context_6'], 'scenario_61': ['multi_turn_long_context_61'], 'scenario_63': ['multi_turn_base_63'], 'scenario_65': ['multi_turn_base_65'], 'scenario_69': ['multi_turn_miss_func_69'], 'scenario_70': ['multi_turn_miss_param_70'], 'scenario_71': ['multi_turn_long_context_71'], 'scenario_80': ['multi_turn_base_80'], 'scenario_90': ['multi_turn_miss_func_90'], 'scenario_92': ['multi_turn_miss_func_92'], 'scenario_97': ['multi_turn_miss_param_97']}
- Existing point-estimate check: match

Underlying-scenario bootstrap estimates are the primary uncertainty analysis when at least two scenario clusters are available. Task-seed bootstrap results are conditional sensitivity diagnostics over the selected task variants and seeds, not independent-scenario inference. A one-scenario design cannot estimate scenario-cluster variance. Bootstrap tail probabilities are not calibrated inferential p-values, so neither raw nor Holm-adjusted tails support significance claims. Variant holdouts report point-estimate sensitivity without significance tests.

## K sweep summary

The table counts how many analyzed non-English model cells change Delta sign or CF reportability after at least one selected task variant is removed.

| K | Null | Delta sign changes | CF reportability changes |
|---:|---|---:|---:|
| 8 | common | 5/14 | 5/14 |
| 8 | position | 6/14 | 4/14 |
| 9 | common | 4/14 | 5/14 |
| 9 | position | 4/14 | 1/14 |
| 10 | common | 3/14 | 5/14 |
| 10 | position | 3/14 | 3/14 |

## Cluster-unit comparison at K=10

| Null | Cluster unit | Status | Language/model cells |
|---|---|---|---:|
| common | underlying_task | estimated | 14 |
| common | task_seed | estimated | 14 |
| position | underlying_task | estimated | 14 |
| position | task_seed | estimated | 14 |

Scenario-cluster intervals use the distinct underlying scenario IDs shown above. Task-seed intervals condition on the selected variants and seeds. Tail values in both groups remain directional diagnostics only.

### underlying_task estimates under the common null

| Cell | CF | Delta | CF 95% CI | Delta 95% CI | Raw tail diagnostic | Holm-adjusted tail diagnostic |
|---|---:|---:|---|---|---:|---:|
| AR::claude_sonnet46 | -0.537 | -0.547 | [-4.567, 4.417] | [-1.391, 0.165] | 0.07278544291141771 | 0.8006398720255948 |
| AR::gemini | 0.519 | 0.254 | [-1.712, 3.262] | [-0.451, 0.902] | 0.7620475904819036 | 1.0 |
| ES::claude_sonnet46 | 0.277 | -0.320 | [-1.136, 1.708] | [-1.107, 0.392] | 0.20095980803839233 | 1.0 |
| ES::gemini | 0.697 | 0.119 | [-4.151, 6.168] | [-0.779, 0.883] | 0.6048790241951609 | 1.0 |
| HI::claude_sonnet46 | -0.625 | -0.363 | [-4.403, 4.238] | [-1.089, 0.271] | 0.13597280543891221 | 1.0 |
| HI::gemini | -6.784 | -0.665 | [-14.901, 14.868] | [-1.495, 0.051] | 0.03439312137572485 | 0.41271745650869823 |
| JA::claude_sonnet46 | 0.136 | -0.269 | [-2.760, 2.700] | [-1.052, 0.390] | 0.2473505298940212 | 1.0 |
| JA::gemini | 0.580 | 0.280 | [-1.990, 3.463] | [-0.568, 1.068] | 0.7324535092981403 | 1.0 |
| SW::claude_sonnet46 | -0.334 | -0.763 | [-4.722, 3.573] | [-1.624, -0.007] | 0.024795040991801638 | 0.3223355328934213 |
| SW::gemini | -0.516 | -0.512 | [-3.888, 4.147] | [-1.537, 0.275] | 0.12077584483103379 | 1.0 |
| TR::claude_sonnet46 | 0.000 | -0.090 | [-3.382, 3.689] | [-0.501, 0.393] | 0.3277344531093781 | 1.0 |
| TR::gemini | 0.697 | 0.119 | [-3.351, 4.553] | [-0.740, 0.858] | 0.6040791841631674 | 1.0 |
| ZH::claude_sonnet46 | -0.429 | -0.817 | [-2.985, 0.854] | [-1.735, -0.072] | 0.014997000599880024 | 0.20995800839832035 |
| ZH::gemini | 0.188 | 0.176 | [-1.367, 1.546] | [-0.598, 0.941] | 0.6788642271545691 | 1.0 |

### task_seed estimates under the common null

| Cell | CF | Delta | CF 95% CI | Delta 95% CI | Raw tail diagnostic | Holm-adjusted tail diagnostic |
|---|---:|---:|---|---|---:|---:|
| AR::claude_sonnet46 | -0.537 | -0.547 | [-4.576, 4.038] | [-1.145, 0.012] | 0.028594281143771244 | 0.31453709258148366 |
| AR::gemini | 0.519 | 0.254 | [0.108, 2.872] | [-0.301, 0.774] | 0.8292341531693661 | 1.0 |
| ES::claude_sonnet46 | 0.277 | -0.320 | [-0.939, 1.730] | [-0.888, 0.241] | 0.1277744451109778 | 1.0 |
| ES::gemini | 0.697 | 0.119 | [-2.858, 4.772] | [-0.511, 0.688] | 0.6552689462107578 | 1.0 |
| HI::claude_sonnet46 | -0.625 | -0.363 | [-4.416, 3.776] | [-0.924, 0.122] | 0.07318536292741452 | 0.6586682663467307 |
| HI::gemini | -6.784 | -0.665 | [-15.401, 14.950] | [-1.253, -0.153] | 0.004799040191961607 | 0.06238752249550089 |
| JA::claude_sonnet46 | 0.136 | -0.269 | [-1.622, 2.260] | [-0.855, 0.248] | 0.17176564687062587 | 1.0 |
| JA::gemini | 0.580 | 0.280 | [0.185, 2.666] | [-0.359, 0.841] | 0.8162367526494702 | 1.0 |
| SW::claude_sonnet46 | -0.334 | -0.763 | [-3.807, 2.023] | [-1.404, -0.176] | 0.0057988402319536095 | 0.06958608278344332 |
| SW::gemini | -0.516 | -0.512 | [-4.535, 3.784] | [-1.193, 0.080] | 0.052189562087582485 | 0.5218956208758249 |
| TR::claude_sonnet46 | 0.000 | -0.090 | [-3.207, 3.279] | [-0.454, 0.310] | 0.3095380923815237 | 1.0 |
| TR::gemini | 0.697 | 0.119 | [-2.199, 4.391] | [-0.477, 0.672] | 0.6608678264347131 | 1.0 |
| ZH::claude_sonnet46 | -0.429 | -0.817 | [-2.194, 0.201] | [-1.436, -0.265] | 0.0021995600879824036 | 0.03079384123175365 |
| ZH::gemini | 0.188 | 0.176 | [-1.743, 1.895] | [-0.413, 0.726] | 0.7338532293541292 | 1.0 |

## Leave-one-task-variant-out at K=10

- `AR::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[-0.742, -0.304]; reportable CF range=[-2.282, -0.196].
- `AR::gemini`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[0.134, 0.386]; reportable CF range=[0.385, 0.662].
- `EN::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[0.000, 0.000]; reportable CF range=not reportable.
- `EN::gemini`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[0.000, 0.000]; reportable CF range=not reportable.
- `ES::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[-0.467, -0.142]; reportable CF range=[0.113, 0.485].
- `ES::gemini`: Delta-sign changes=True; CF-reportability changes=False; Delta range=[-0.069, 0.301]; reportable CF range=[0.388, 1.297].
- `HI::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=True; Delta range=[-0.543, -0.146]; reportable CF range=[-1.720, -0.173].
- `HI::gemini`: Delta-sign changes=False; CF-reportability changes=True; Delta range=[-0.830, -0.496]; reportable CF range=[-7.156, 7.352].
- `JA::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[-0.389, -0.048]; reportable CF range=[-0.188, 0.657].
- `JA::gemini`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[0.098, 0.456]; reportable CF range=[0.417, 0.814].
- `SW::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[-1.008, -0.577]; reportable CF range=[-0.671, -0.155].
- `SW::gemini`: Delta-sign changes=False; CF-reportability changes=True; Delta range=[-0.642, -0.191]; reportable CF range=[-1.103, -0.167].
- `TR::claude_sonnet46`: Delta-sign changes=True; CF-reportability changes=True; Delta range=[-0.293, 0.000]; reportable CF range=[0.000, 0.641].
- `TR::gemini`: Delta-sign changes=True; CF-reportability changes=False; Delta range=[-0.069, 0.301]; reportable CF range=[0.388, 1.297].
- `ZH::claude_sonnet46`: Delta-sign changes=False; CF-reportability changes=False; Delta range=[-1.034, -0.564]; reportable CF range=[-0.727, -0.253].
- `ZH::gemini`: Delta-sign changes=False; CF-reportability changes=True; Delta range=[0.002, 0.322]; reportable CF range=[-0.000, 0.380].

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/run_task_sensitivity.py --n-boot 5000 --bootstrap-seed 0 --task-ids multi_turn_base_0 multi_turn_base_63 multi_turn_base_18 multi_turn_base_65 multi_turn_base_80 multi_turn_miss_func_10 multi_turn_miss_func_90 multi_turn_miss_func_55 multi_turn_miss_func_69 multi_turn_miss_func_92 multi_turn_miss_param_39 multi_turn_miss_param_97 multi_turn_miss_param_58 multi_turn_miss_param_70 multi_turn_miss_param_171 multi_turn_long_context_59 multi_turn_long_context_6 multi_turn_long_context_61 multi_turn_long_context_71 multi_turn_long_context_2 --input-artifact-prefix newstudy20261010
```

The JSON records all cells, both nulls, results for both cluster units, point-estimate invariance checks, and each leave-one-task-variant-out estimate.
