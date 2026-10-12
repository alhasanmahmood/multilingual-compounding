# E6 Robustness Report

## Analysis Scope

- Localization policy: `reviewed`
- Tasks represented in filtered rows: `20`
- Full trajectories and replays: `640` and `5952`
- Task intersection policy: `complete_intersection`

## Localization Controls

- Policy: `reviewed`; validated rows retained: `160 / 160`
- AI review status counts: `{'corrected': 86, 'reviewed': 54}`; English source/target identity rows: `20`
- Exact quoted source literals checked: `400`
- Human review status counts: `{'pending': 160}`
- Automatic heuristic diagnostic only: invariance passes `9 / 160`, rating counts `{5: 5, 3: 75, 4: 37, 2: 43}`
- Legacy combined heuristic would retain `9` and remove `151` rows; it did not filter this analysis.

## K Sensitivity

- K range checked: `[8, 9, 10]`
- Bootstrap tail values are uncalibrated directional diagnostics, not inferential p-values.

## Leave-One-Language-Out

- Hold out `AR`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `ES`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `HI`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `JA`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `SW`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `TR`: max directional cell=`ZH::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`
- Hold out `ZH`: max directional cell=`SW::claude_sonnet46`, significant cells=`[]`, status=`descriptive_only`

## Seed Variance

- Run labels considered: `['expansion_seed0', 'expansion_seed1']`
- `AR::claude_sonnet46`: p_range=`[0.6117021276595744, 0.6117021276595744]`, T_range=`[0.4090909090909091, 0.5]`, Delta_range=`[-0.6056240937387171, -0.4000658631375038]`, CF_range=`[-1.5457160196892865, 0.0]`
- `AR::gemini`: p_range=`[0.5797872340425532, 0.601063829787234]`, T_range=`[0.45454545454545453, 0.45454545454545453]`, Delta_range=`[-0.10065088507499634, 0.5317091233347347]`, CF_range=`[0.2553413485833618, 1.4268098898384554]`
- `ES::claude_sonnet46`: p_range=`[0.6170212765957447, 0.6170212765957447]`, T_range=`[0.5909090909090909, 0.6363636363636364]`, Delta_range=`[-0.3158218783014313, -0.23682637100864748]`, CF_range=`[0.0, 0.5045353459998649]`
- `ES::gemini`: p_range=`[0.5957446808510638, 0.601063829787234]`, T_range=`[0.4090909090909091, 0.5]`, Delta_range=`[-0.005340705270671542, 0.1819897060833509]`, CF_range=`[0.6125172633302302, 1.022647250707597]`
- `HI::claude_sonnet46`: p_range=`[0.601063829787234, 0.6063829787234043]`, T_range=`[0.45454545454545453, 0.5]`, Delta_range=`[-0.4167729232230383, -0.2470546114183809]`, CF_range=`[-2.088162308909761, -0.296489038794088]`
- `HI::gemini`: p_range=`[0.6276595744680851, 0.6276595744680851]`, T_range=`[0.3181818181818182, 0.36363636363636365]`, Delta_range=`[-0.7134656881691229, -0.5389965007326869]`, CF_range=`[-3.6374140450228274, -3.6374140450228274]`
- `JA::claude_sonnet46`: p_range=`[0.6063829787234043, 0.6117021276595744]`, T_range=`[0.5454545454545454, 0.5909090909090909]`, Delta_range=`[-0.23789931361339964, -0.23445136642908376]`, CF_range=`[0.0, 0.27067328569486865]`
- `JA::gemini`: p_range=`[0.5797872340425532, 0.5851063829787234]`, T_range=`[0.4090909090909091, 0.4090909090909091]`, Delta_range=`[0.03615567554649646, 0.4263486076769085]`, CF_range=`[0.40289875555477817, 0.9243586801651751]`
- `SW::claude_sonnet46`: p_range=`[0.6170212765957447, 0.6329787234042553]`, T_range=`[0.36363636363636365, 0.5454545454545454]`, Delta_range=`[-0.801329694083132, -0.6207767688823886]`, CF_range=`[-1.5372836688606966, 0.12293421060680354]`
- `SW::gemini`: p_range=`[0.6436170212765957, 0.6436170212765957]`, T_range=`[0.5, 0.5]`, Delta_range=`[-0.6209652472302755, -0.31296466716931665]`, CF_range=`[-0.6349658531156656, -0.3850856826224341]`
- `TR::claude_sonnet46`: p_range=`[0.5904255319148937, 0.601063829787234]`, T_range=`[0.5454545454545454, 0.5454545454545454]`, Delta_range=`[-0.15515569928968928, 0.0006753221713060309]`, CF_range=`[0.359303082510149, 0.9916335647363527]`
- `TR::gemini`: p_range=`[0.5957446808510638, 0.601063829787234]`, T_range=`[0.45454545454545453, 0.45454545454545453]`, Delta_range=`[-0.10065088507499634, 0.2873502217411771]`, CF_range=`[0.38818929543222885, 1.4268098898384554]`
- `ZH::claude_sonnet46`: p_range=`[0.6170212765957447, 0.6329787234042553]`, T_range=`[0.4090909090909091, 0.45454545454545453]`, Delta_range=`[-0.9084588413341694, -0.5781861427689224]`, CF_range=`[-0.8307349252640489, -0.283518022493748]`
- `ZH::gemini`: p_range=`[0.6063829787234043, 0.6117021276595744]`, T_range=`[0.5454545454545454, 0.5909090909090909]`, Delta_range=`[0.08241771225310023, 0.23177246492173226]`, CF_range=`[-0.0, 0.47345566597945443]`

## Environment Holdout

- Status: `not_run`
- Reason: The current manuscript is explicitly BFCL-primary, so no second environment is in completed scope for a meaningful environment-holdout rerun.
