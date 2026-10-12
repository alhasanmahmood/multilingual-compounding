# BFCL Compounding Analysis Report

- BFCL commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Tasks in current slice: `20`
- Task IDs: `['multi_turn_base_0', 'multi_turn_base_63', 'multi_turn_base_18', 'multi_turn_base_65', 'multi_turn_base_80', 'multi_turn_miss_func_10', 'multi_turn_miss_func_90', 'multi_turn_miss_func_55', 'multi_turn_miss_func_69', 'multi_turn_miss_func_92', 'multi_turn_miss_param_39', 'multi_turn_miss_param_97', 'multi_turn_miss_param_58', 'multi_turn_miss_param_70', 'multi_turn_miss_param_171', 'multi_turn_long_context_59', 'multi_turn_long_context_6', 'multi_turn_long_context_61', 'multi_turn_long_context_71', 'multi_turn_long_context_2']`
- Languages: `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`
- Models: `['claude_sonnet46', 'gemini']`
- Run labels: `['expansion_seed0', 'expansion_seed1']`
- Full-task trials: `640`
- Isolated replay trials: `5952`
- Bootstrap: `{'n_boot': 5000, 'seed': 0, 'cluster_unit': 'underlying_task', 'cluster_counts_by_backbone': {'claude_sonnet46': 20, 'gemini': 20}, 'status': 'available', 'unavailable_reason': None, 'tail_interpretation': 'Bootstrap tail probabilities are uncalibrated directional diagnostics, not inferential p-values.'}`
- Mean K: `9.30`
- Rounded K: `9`
- K range checked: `[8, 9, 10]`

Bootstrap-tail probabilities (raw and Holm-adjusted) are uncalibrated directional diagnostics, not inferential p-values.

## CF snapshot
- `AR::claude_sonnet46`: T=0.452, p=0.612, CF=-0.5969847107381069, Delta=-0.511, Holm-adjusted bootstrap-tail diagnostic=0.6796640671865627
- `AR::gemini`: T=0.452, p=0.591, CF=0.57669123699839, Delta=0.201, Holm-adjusted bootstrap-tail diagnostic=1.0
- `ES::claude_sonnet46`: T=0.619, p=0.618, CF=0.30781781631176636, Delta=-0.276, Holm-adjusted bootstrap-tail diagnostic=1.0
- `ES::gemini`: T=0.452, p=0.599, CF=0.7740828568850311, Delta=0.080, Holm-adjusted bootstrap-tail diagnostic=1.0
- `HI::claude_sonnet46`: T=0.476, p=0.604, CF=-0.6941220288919386, Delta=-0.341, Holm-adjusted bootstrap-tail diagnostic=1.0
- `HI::gemini`: T=0.333, p=0.628, CF=-7.537594551827544, Delta=-0.657, Holm-adjusted bootstrap-tail diagnostic=0.27034593081383723
- `JA::claude_sonnet46`: T=0.571, p=0.610, CF=0.15164856013387595, Delta=-0.238, Holm-adjusted bootstrap-tail diagnostic=1.0
- `JA::gemini`: T=0.405, p=0.583, CF=0.6439615753988356, Delta=0.213, Holm-adjusted bootstrap-tail diagnostic=1.0
- `SW::claude_sonnet46`: T=0.452, p=0.626, CF=-0.37139518426356977, Delta=-0.705, Holm-adjusted bootstrap-tail diagnostic=0.27034593081383723
- `SW::gemini`: T=0.500, p=0.644, CF=-0.5738587345966866, Delta=-0.478, Holm-adjusted bootstrap-tail diagnostic=1.0
- `TR::claude_sonnet46`: T=0.548, p=0.596, CF=0.0, Delta=-0.081, Holm-adjusted bootstrap-tail diagnostic=1.0
- `TR::gemini`: T=0.452, p=0.599, CF=0.7740828568850311, Delta=0.080, Holm-adjusted bootstrap-tail diagnostic=1.0
- `ZH::claude_sonnet46`: T=0.429, p=0.626, CF=-0.4764972790636877, Delta=-0.760, Holm-adjusted bootstrap-tail diagnostic=0.1819636072785443
- `ZH::gemini`: T=0.571, p=0.610, CF=0.20909112806650815, Delta=0.154, Holm-adjusted bootstrap-tail diagnostic=1.0
