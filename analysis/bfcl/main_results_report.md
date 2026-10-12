# BFCL Compounding Analysis Report

- BFCL commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Tasks in current slice: `4`
- Task IDs: `['multi_turn_base_0', 'multi_turn_miss_func_0', 'multi_turn_miss_param_0', 'multi_turn_long_context_0']`
- Languages: `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`
- Models: `['claude_sonnet46', 'gemini']`
- Run labels: `['expanded_seed0', 'expanded_seed1', 'pilot_seed0', 'pilot_seed1']`
- Full-task trials: `128`
- Isolated replay trials: `1280`
- Bootstrap: `{'n_boot': 5000, 'seed': 0, 'cluster_unit': 'underlying_task', 'cluster_counts_by_backbone': {'claude_sonnet46': 1, 'gemini': 1}, 'status': 'unavailable', 'unavailable_reason': "At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}", 'tail_interpretation': 'Bootstrap tail probabilities are uncalibrated directional diagnostics, not inferential p-values.'}`
- Mean K: `10.00`
- Rounded K: `10`
- K range checked: `[9, 10, 11]`

Bootstrap-tail probabilities (raw and Holm-adjusted) are uncalibrated directional diagnostics, not inferential p-values.

## CF snapshot
- `AR::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.500, Delta=2.357. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `AR::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.100, Delta=0.727. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `ES::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.600, Delta=0.128. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `ES::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.500, Delta=0.608. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `HI::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.600, Delta=2.182. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `HI::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.500, Delta=0.608. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `JA::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.600, Delta=0.716. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `JA::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.500, Delta=1.264. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `SW::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.200, Delta=2.196. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `SW::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.100, Delta=1.111. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `TR::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.600, Delta=1.024. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `TR::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.300, Delta=-0.216. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `ZH::claude_sonnet46`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.400, Delta=1.603. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
- `ZH::gemini`: scenario-level bootstrap unavailable (1 cluster(s)); point estimate T=0.100, Delta=-0.001. Reason: At least two underlying_task clusters are required per model; insufficient cluster counts: {'claude_sonnet46': 1, 'gemini': 1}
