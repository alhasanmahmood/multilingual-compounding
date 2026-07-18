# E6 Robustness Report

## Localization Controls

- Localization records: `32`
- Invariance passes: `32 / 32`
- Fidelity rating counts: `{5: 4, 3: 24, 4: 4}`
- Records kept at fidelity >= `3`: `32`
- Records removed by the low-fidelity filter: `0`

## K Sensitivity

- K range checked: `[9, 10, 11]`

## Leave-One-Language-Out

- Hold out `AR`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `ES`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `HI`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `JA`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `SW`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `TR`: max directional cell=`ZH::gemini`, significant cells=`[]`
- Hold out `ZH`: max directional cell=`TR::gemini`, significant cells=`[]`

## Seed Variance

- Run labels considered: `['expanded_seed0', 'expanded_seed1', 'pilot_seed0', 'pilot_seed1']`
- `AR::claude_sonnet46`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.3333333333333333, 0.6666666666666666]`, Delta_range=`[1.8199971022491153, 2.7871340246902054]`, CF_range=`[-0.0, 0.2758087489450394]`
- `AR::gemini`: p_range=`[0.6428571428571429, 0.6428571428571429]`, T_range=`[0.16666666666666666, 0.16666666666666666]`, Delta_range=`[1.2673828120837074, 1.2673828120837074]`, CF_range=`[0.5594501939997888, 0.5594501939997888]`
- `ES::claude_sonnet46`: p_range=`[0.8333333333333334, 0.8571428571428571]`, T_range=`[0.5, 0.6666666666666666]`, Delta_range=`[-0.005973302784818613, 0.2739897418811448]`, CF_range=`[-0.0, 1.0212038226281712]`
- `ES::gemini`: p_range=`[0.7619047619047619, 0.7619047619047619]`, T_range=`[0.5, 0.5]`, Delta_range=`[0.6670047327978439, 0.6670047327978439]`, CF_range=`[0.4337005078186789, 0.4337005078186789]`
- `HI::claude_sonnet46`: p_range=`[0.6904761904761905, 0.6904761904761905]`, T_range=`[0.5, 0.6666666666666666]`, Delta_range=`[1.8745490122445787, 2.4362208265775043]`, CF_range=`[-0.0, 0.1330487173586166]`
- `HI::gemini`: p_range=`[0.7619047619047619, 0.7619047619047619]`, T_range=`[0.5, 0.5]`, Delta_range=`[0.6670047327978439, 0.6670047327978439]`, CF_range=`[0.4337005078186789, 0.4337005078186789]`
- `JA::claude_sonnet46`: p_range=`[0.7857142857142857, 0.8095238095238095]`, T_range=`[0.5, 0.6666666666666666]`, Delta_range=`[0.5715841383994855, 0.8564214393256612]`, CF_range=`[-0.0, 0.2514475914900806]`
- `JA::gemini`: p_range=`[0.7142857142857143, 0.7142857142857143]`, T_range=`[0.5, 0.5]`, Delta_range=`[1.3123899441735547, 1.3123899441735547]`, CF_range=`[0.28017840169239316, 0.28017840169239316]`
- `SW::claude_sonnet46`: p_range=`[0.6190476190476191, 0.6190476190476191]`, T_range=`[0.16666666666666666, 0.3333333333333333]`, Delta_range=`[2.141919385107533, 2.5610768237863333]`, CF_range=`[0.21299922182191247, 0.39291677342456904]`
- `SW::gemini`: p_range=`[0.6190476190476191, 0.6190476190476191]`, T_range=`[0.16666666666666666, 0.16666666666666666]`, Delta_range=`[1.6447860919121782, 1.6447860919121782]`, CF_range=`[0.494568877337444, 0.494568877337444]`
- `TR::claude_sonnet46`: p_range=`[0.7619047619047619, 0.7857142857142857]`, T_range=`[0.5, 0.6666666666666666]`, Delta_range=`[0.8701137698962973, 1.1641380259931986]`, CF_range=`[-0.0, 0.19815270002110622]`
- `TR::gemini`: p_range=`[0.7857142857142857, 0.7857142857142857]`, T_range=`[0.3333333333333333, 0.3333333333333333]`, Delta_range=`[-0.04617696197785781, -0.04617696197785781]`, CF_range=`[1.0530700278233285, 1.0530700278233285]`
- `ZH::claude_sonnet46`: p_range=`[0.6904761904761905, 0.7142857142857143]`, T_range=`[0.3333333333333333, 0.5]`, Delta_range=`[1.1300683873796, 2.1485387541257235]`, CF_range=`[0.11808538426129771, 0.3801784016923932]`
- `ZH::gemini`: p_range=`[0.6904761904761905, 0.6904761904761905]`, T_range=`[0.16666666666666666, 0.16666666666666666]`, Delta_range=`[0.552793172262259, 0.552793172262259]`, CF_range=`[0.7443413073770109, 0.7443413073770109]`

## Environment Holdout

- Status: `not_run`
- Reason: The current manuscript is explicitly BFCL-primary, so no second environment is in completed scope for a meaningful environment-holdout rerun.
