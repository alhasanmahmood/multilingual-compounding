# E6 Robustness Report

## Localization Controls

- Localization records: `160`
- Invariance passes: `9 / 160`
- Fidelity rating counts: `{5: 5, 3: 75, 4: 37, 2: 43}`
- Records kept at fidelity >= `3`: `9`
- Records removed by the low-fidelity filter: `151`

## K Sensitivity

- K range checked: `[8, 9, 10]`

## Leave-One-Language-Out

- Hold out `AR`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`
- Hold out `ES`: max directional cell=`TR::gemini`, significant cells=`[]`
- Hold out `HI`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`
- Hold out `JA`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`
- Hold out `SW`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`
- Hold out `TR`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`
- Hold out `ZH`: max directional cell=`ES::claude_sonnet46`, significant cells=`[]`

## Seed Variance

- Run labels considered: `['expansion_seed0', 'expansion_seed1']`
- `AR::claude_sonnet46`: p_range=`[0.75, 0.75]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[0.665319357250285, 1.1519243486827664]`, CF_range=`[0.09276392112792708, 0.1504056643464006]`
- `AR::gemini`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.3333333333333333, 0.6666666666666666]`, Delta_range=`[1.4376846057059558, 2.130831786265901]`, CF_range=`[-0.15608177148912455, 0.21998490142676233]`
- `ES::claude_sonnet46`: p_range=`[0.8333333333333334, 0.8333333333333334]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[-0.2829252836701521, 0.20367970776232922]`, CF_range=`[-0.7132217047606344, 0.36639715820183977]`
- `ES::gemini`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[2.130831786265901, 2.130831786265901]`, CF_range=`[-0.15608177148912455, -0.15608177148912455]`
- `HI::claude_sonnet46`: p_range=`[0.75, 0.75]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[0.665319357250285, 1.1519243486827664]`, CF_range=`[0.09276392112792708, 0.1504056643464006]`
- `HI::gemini`: p_range=`[0.75, 0.75]`, T_range=`[0.3333333333333333, 0.3333333333333333]`, Delta_range=`[0.37763728479850406, 0.37763728479850406]`, CF_range=`[0.5177676786341892, 0.5177676786341892]`
- `JA::claude_sonnet46`: p_range=`[0.75, 0.8333333333333334]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[-0.2829252836701521, 1.1519243486827664]`, CF_range=`[-0.7132217047606344, 0.09276392112792708]`
- `JA::gemini`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[2.130831786265901, 2.130831786265901]`, CF_range=`[-0.15608177148912455, -0.15608177148912455]`
- `SW::claude_sonnet46`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.3333333333333333, 0.6666666666666666]`, Delta_range=`[1.0322194975977914, 2.211971669590218]`, CF_range=`[0.05055598144780497, 0.4399698028535246]`
- `SW::gemini`: p_range=`[0.6666666666666666, 0.6666666666666666]`, T_range=`[0.3333333333333333, 0.3333333333333333]`, Delta_range=`[1.4376846057059558, 1.4376846057059558]`, CF_range=`[0.21998490142676233, 0.21998490142676233]`
- `TR::claude_sonnet46`: p_range=`[0.6666666666666666, 0.75]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[0.665319357250285, 2.211971669590218]`, CF_range=`[0.05055598144780497, 0.1504056643464006]`
- `TR::gemini`: p_range=`[0.75, 0.75]`, T_range=`[0.3333333333333333, 0.3333333333333333]`, Delta_range=`[0.37763728479850406, 0.37763728479850406]`, CF_range=`[0.5177676786341892, 0.5177676786341892]`
- `ZH::claude_sonnet46`: p_range=`[0.75, 0.75]`, T_range=`[0.6666666666666666, 0.6666666666666666]`, Delta_range=`[0.665319357250285, 1.1519243486827664]`, CF_range=`[0.09276392112792708, 0.1504056643464006]`
- `ZH::gemini`: p_range=`[0.75, 0.75]`, T_range=`[0.3333333333333333, 0.6666666666666666]`, Delta_range=`[0.37763728479850406, 1.0707844653584493]`, CF_range=`[-0.3673620142877884, 0.5177676786341892]`

## Environment Holdout

- Status: `not_run`
- Reason: The current manuscript is explicitly BFCL-primary, so no second environment is in completed scope for a meaningful environment-holdout rerun.
