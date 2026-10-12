# E4 Decomposition Report

## Scope

- Tasks: `20`
- Task IDs: `['multi_turn_base_0', 'multi_turn_base_63', 'multi_turn_base_18', 'multi_turn_base_65', 'multi_turn_base_80', 'multi_turn_miss_func_10', 'multi_turn_miss_func_90', 'multi_turn_miss_func_55', 'multi_turn_miss_func_69', 'multi_turn_miss_func_92', 'multi_turn_miss_param_39', 'multi_turn_miss_param_97', 'multi_turn_miss_param_58', 'multi_turn_miss_param_70', 'multi_turn_miss_param_171', 'multi_turn_long_context_59', 'multi_turn_long_context_6', 'multi_turn_long_context_61', 'multi_turn_long_context_71', 'multi_turn_long_context_2']`
- Models: `['claude_sonnet46', 'gemini']`
- Languages: `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`
- Run labels: `['expansion_seed0', 'expansion_seed1']`
- Full-task trials: `640`
- Replay trials: `5952`

## Aggregate Stage Mix

- EN invalid replay steps: `292`
- non-EN invalid replay steps: `2026`
- EN stage shares: `{'sequencing_planning': 0.6986301369863014, 'argument_parameter': 0.11643835616438356, 'intent_selection': 0.18493150684931506}`
- non-EN stage shares: `{'argument_parameter': 0.13079960513326752, 'sequencing_planning': 0.6752221125370188, 'intent_selection': 0.19397828232971373}`

## Trajectory Effects

- EN propagation rate: `0.41025641025641024`
- EN recovery rate: `0.5897435897435898`
- non-EN propagation rate: `0.5091575091575091`
- non-EN recovery rate: `0.4908424908424908`

## Matched-Validity Trajectory Effects

- Shared replay-validity bins: `[[2, 9], [2, 10], [3, 9], [4, 9], [5, 9], [5, 10], [6, 8], [6, 9], [6, 10], [7, 9], [7, 10], [8, 10], [9, 10]]`
- Weighted matched pairs: `77`
- EN matched propagation rate: `0.4155844155844156`
- non-EN matched propagation rate: `0.5309098838674028`
- EN matched recovery rate: `0.5844155844155844`
- non-EN matched recovery rate: `0.46909011613259727`

## Cell Highlights

### `claude_sonnet46::AR`

- Replay stage shares: `{'intent_selection': 0.1527777777777778, 'sequencing_planning': 0.7083333333333334, 'argument_parameter': 0.1388888888888889}`
- Replay failure-type shares: `{'wrong_function': 0.08333333333333333, 'wrong_order_or_context': 0.7083333333333334, 'wrong_arguments': 0.1388888888888889, 'no_call': 0.06944444444444445}`
- Propagation rate: `0.55`
- Recovery rate: `0.45`

### `claude_sonnet46::EN`

- Replay stage shares: `{'intent_selection': 0.24342105263157895, 'sequencing_planning': 0.631578947368421, 'argument_parameter': 0.125}`
- Replay failure-type shares: `{'wrong_function': 0.09868421052631579, 'wrong_order_or_context': 0.631578947368421, 'wrong_arguments': 0.125, 'no_call': 0.14473684210526316}`
- Propagation rate: `0.45`
- Recovery rate: `0.55`

### `claude_sonnet46::ES`

- Replay stage shares: `{'intent_selection': 0.19718309859154928, 'sequencing_planning': 0.6901408450704225, 'argument_parameter': 0.11267605633802817}`
- Replay failure-type shares: `{'wrong_function': 0.09859154929577464, 'wrong_order_or_context': 0.6901408450704225, 'wrong_arguments': 0.11267605633802817, 'no_call': 0.09859154929577464}`
- Propagation rate: `0.358974358974359`
- Recovery rate: `0.6410256410256411`

### `claude_sonnet46::HI`

- Replay stage shares: `{'intent_selection': 0.23809523809523808, 'sequencing_planning': 0.6258503401360545, 'argument_parameter': 0.1360544217687075}`
- Replay failure-type shares: `{'wrong_function': 0.1292517006802721, 'wrong_order_or_context': 0.6258503401360545, 'wrong_arguments': 0.1360544217687075, 'no_call': 0.10884353741496598}`
- Propagation rate: `0.525`
- Recovery rate: `0.475`

### `claude_sonnet46::JA`

- Replay stage shares: `{'intent_selection': 0.23448275862068965, 'sequencing_planning': 0.6275862068965518, 'argument_parameter': 0.13793103448275862}`
- Replay failure-type shares: `{'wrong_function': 0.11724137931034483, 'wrong_order_or_context': 0.6275862068965518, 'wrong_arguments': 0.13793103448275862, 'no_call': 0.11724137931034483}`
- Propagation rate: `0.425`
- Recovery rate: `0.575`

### `claude_sonnet46::SW`

- Replay stage shares: `{'intent_selection': 0.23741007194244604, 'sequencing_planning': 0.6115107913669064, 'argument_parameter': 0.1510791366906475}`
- Replay failure-type shares: `{'wrong_function': 0.14388489208633093, 'wrong_order_or_context': 0.6115107913669064, 'wrong_arguments': 0.1510791366906475, 'no_call': 0.09352517985611511}`
- Propagation rate: `0.55`
- Recovery rate: `0.45`

### `claude_sonnet46::TR`

- Replay stage shares: `{'intent_selection': 0.25333333333333335, 'sequencing_planning': 0.5866666666666667, 'argument_parameter': 0.16}`
- Replay failure-type shares: `{'wrong_function': 0.13333333333333333, 'wrong_order_or_context': 0.5866666666666667, 'wrong_arguments': 0.16, 'no_call': 0.12}`
- Propagation rate: `0.4358974358974359`
- Recovery rate: `0.5641025641025641`

### `claude_sonnet46::ZH`

- Replay stage shares: `{'argument_parameter': 0.15827338129496402, 'sequencing_planning': 0.6834532374100719, 'intent_selection': 0.15827338129496402}`
- Replay failure-type shares: `{'wrong_arguments': 0.15827338129496402, 'wrong_order_or_context': 0.6834532374100719, 'wrong_function': 0.08633093525179857, 'no_call': 0.07194244604316546}`
- Propagation rate: `0.575`
- Recovery rate: `0.425`

### `gemini::AR`

- Replay stage shares: `{'argument_parameter': 0.14473684210526316, 'sequencing_planning': 0.7236842105263158, 'intent_selection': 0.13157894736842105}`
- Replay failure-type shares: `{'wrong_arguments': 0.14473684210526316, 'wrong_order_or_context': 0.7236842105263158, 'no_call': 0.07894736842105263, 'wrong_function': 0.05263157894736842}`
- Propagation rate: `0.5263157894736842`
- Recovery rate: `0.47368421052631576`

### `gemini::EN`

- Replay stage shares: `{'sequencing_planning': 0.7714285714285715, 'argument_parameter': 0.10714285714285714, 'intent_selection': 0.12142857142857143}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.7714285714285715, 'wrong_arguments': 0.10714285714285714, 'no_call': 0.04285714285714286, 'wrong_function': 0.07857142857142857}`
- Propagation rate: `0.3684210526315789`
- Recovery rate: `0.631578947368421`

### `gemini::ES`

- Replay stage shares: `{'argument_parameter': 0.12751677852348994, 'sequencing_planning': 0.7516778523489933, 'intent_selection': 0.12080536912751678}`
- Replay failure-type shares: `{'wrong_arguments': 0.12751677852348994, 'wrong_order_or_context': 0.7516778523489933, 'no_call': 0.06040268456375839, 'wrong_function': 0.06040268456375839}`
- Propagation rate: `0.5263157894736842`
- Recovery rate: `0.47368421052631576`

### `gemini::HI`

- Replay stage shares: `{'sequencing_planning': 0.6521739130434783, 'intent_selection': 0.2028985507246377, 'argument_parameter': 0.14492753623188406}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.6521739130434783, 'no_call': 0.08695652173913043, 'wrong_arguments': 0.14492753623188406, 'wrong_function': 0.11594202898550725}`
- Propagation rate: `0.6578947368421053`
- Recovery rate: `0.34210526315789475`

### `gemini::JA`

- Replay stage shares: `{'intent_selection': 0.2064516129032258, 'sequencing_planning': 0.7032258064516129, 'argument_parameter': 0.09032258064516129}`
- Replay failure-type shares: `{'wrong_function': 0.14193548387096774, 'wrong_order_or_context': 0.7032258064516129, 'no_call': 0.06451612903225806, 'wrong_arguments': 0.09032258064516129}`
- Propagation rate: `0.5789473684210527`
- Recovery rate: `0.42105263157894735`

### `gemini::SW`

- Replay stage shares: `{'argument_parameter': 0.12121212121212122, 'intent_selection': 0.1590909090909091, 'sequencing_planning': 0.7196969696969697}`
- Replay failure-type shares: `{'wrong_arguments': 0.12121212121212122, 'wrong_function': 0.06818181818181818, 'wrong_order_or_context': 0.7196969696969697, 'no_call': 0.09090909090909091}`
- Propagation rate: `0.5`
- Recovery rate: `0.5`

### `gemini::TR`

- Replay stage shares: `{'sequencing_planning': 0.7114093959731543, 'intent_selection': 0.18791946308724833, 'argument_parameter': 0.10067114093959731}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.7114093959731543, 'no_call': 0.08053691275167785, 'wrong_arguments': 0.10067114093959731, 'wrong_function': 0.10738255033557047}`
- Propagation rate: `0.5263157894736842`
- Recovery rate: `0.47368421052631576`

### `gemini::ZH`

- Replay stage shares: `{'intent_selection': 0.23448275862068965, 'sequencing_planning': 0.6551724137931034, 'argument_parameter': 0.1103448275862069}`
- Replay failure-type shares: `{'wrong_function': 0.16551724137931034, 'wrong_order_or_context': 0.6551724137931034, 'no_call': 0.06896551724137931, 'wrong_arguments': 0.1103448275862069}`
- Propagation rate: `0.39473684210526316`
- Recovery rate: `0.6052631578947368`
