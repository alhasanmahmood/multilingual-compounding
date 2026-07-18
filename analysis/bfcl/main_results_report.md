# BFCL Compounding Analysis Report

- BFCL commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
- Tasks in current slice: `4`
- Task IDs: `['multi_turn_base_0', 'multi_turn_miss_func_0', 'multi_turn_miss_param_0', 'multi_turn_long_context_0']`
- Languages: `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`
- Models: `['claude_sonnet46', 'gemini']`
- Run labels: `['expanded_seed0', 'expanded_seed1', 'pilot_seed0', 'pilot_seed1']`
- Full-task trials: `128`
- Isolated replay trials: `1280`
- Mean K: `10.00`
- Rounded K: `10`
- K range checked: `[9, 10, 11]`

## CF snapshot
- `AR::claude_sonnet46`: T=0.500, p=0.671, CF=0.12492799595447049, Delta=2.357, p_holm=1.0
- `AR::gemini`: T=0.100, p=0.646, CF=0.7514757280415297, Delta=0.727, p_holm=1.0
- `ES::claude_sonnet46`: T=0.600, p=0.854, CF=0.5471987258667719, Delta=0.128, p_holm=1.0
- `ES::gemini`: T=0.500, p=0.768, CF=0.491685912567117, Delta=0.608, p_holm=1.0
- `HI::claude_sonnet46`: T=0.600, p=0.695, CF=0.06598496587337765, Delta=2.182, p_holm=1.0
- `HI::gemini`: T=0.500, p=0.768, CF=0.491685912567117, Delta=0.608, p_holm=1.0
- `JA::claude_sonnet46`: T=0.600, p=0.805, CF=0.17716152204513483, Delta=0.716, p_holm=1.0
- `JA::gemini`: T=0.500, p=0.720, CF=0.317478092378548, Delta=1.264, p_holm=1.0
- `SW::claude_sonnet46`: T=0.200, p=0.622, CF=0.36328767018254066, Delta=2.196, p_holm=1.0
- `SW::gemini`: T=0.100, p=0.622, CF=0.6641065106697166, Delta=1.111, p_holm=1.0
- `TR::claude_sonnet46`: T=0.600, p=0.780, CF=0.1308768100331296, Delta=1.024, p_holm=1.0
- `TR::gemini`: T=0.300, p=0.793, CF=1.2442857043007645, Delta=-0.216, p_holm=1.0
- `ZH::claude_sonnet46`: T=0.400, p=0.707, CF=0.2588140517894778, Delta=1.603, p_holm=1.0
- `ZH::gemini`: T=0.100, p=0.695, CF=1.0004273055645871, Delta=-0.001, p_holm=1.0
