# E4 Decomposition Report

## Scope

- Tasks: `4`
- Task IDs: `['multi_turn_base_0', 'multi_turn_miss_func_0', 'multi_turn_miss_param_0', 'multi_turn_long_context_0']`
- Models: `['claude_sonnet46', 'gemini']`
- Languages: `['AR', 'EN', 'ES', 'HI', 'JA', 'SW', 'TR', 'ZH']`
- Run labels: `['expanded_seed0', 'expanded_seed1', 'pilot_seed0', 'pilot_seed1']`
- Full-task trials: `128`
- Replay trials: `1280`

## Aggregate Stage Mix

- EN invalid replay steps: `19`
- non-EN invalid replay steps: `302`
- EN stage shares: `{'sequencing_planning': 0.42105263157894735, 'intent_selection': 0.5789473684210527}`
- non-EN stage shares: `{'argument_parameter': 0.2980132450331126, 'sequencing_planning': 0.26158940397350994, 'intent_selection': 0.44039735099337746}`

## Trajectory Effects

- EN propagation rate: `0.125`
- EN recovery rate: `0.875`
- non-EN propagation rate: `0.6111111111111112`
- non-EN recovery rate: `0.3888888888888889`

## Matched-Validity Trajectory Effects

- Shared replay-validity bins: `[[8, 10], [9, 10]]`
- Weighted matched pairs: `14`
- EN matched propagation rate: `0.14285714285714285`
- non-EN matched propagation rate: `0.3534798534798535`
- EN matched recovery rate: `0.8571428571428571`
- non-EN matched recovery rate: `0.6465201465201466`

## Cell Highlights

### `claude_sonnet46::AR`

- Replay stage shares: `{'intent_selection': 0.34615384615384615, 'sequencing_planning': 0.3076923076923077, 'argument_parameter': 0.34615384615384615}`
- Replay failure-type shares: `{'wrong_function': 0.34615384615384615, 'wrong_order_or_context': 0.3076923076923077, 'wrong_arguments': 0.34615384615384615}`
- Propagation rate: `0.5`
- Recovery rate: `0.5`

### `claude_sonnet46::EN`

- Replay stage shares: `{'intent_selection': 1.0}`
- Replay failure-type shares: `{'wrong_function': 0.8888888888888888, 'no_call': 0.1111111111111111}`
- Propagation rate: `0.25`
- Recovery rate: `0.75`

### `claude_sonnet46::ES`

- Replay stage shares: `{'intent_selection': 0.9090909090909091, 'argument_parameter': 0.09090909090909091}`
- Replay failure-type shares: `{'wrong_function': 0.9090909090909091, 'wrong_arguments': 0.09090909090909091}`
- Propagation rate: `0.375`
- Recovery rate: `0.625`

### `claude_sonnet46::HI`

- Replay stage shares: `{'intent_selection': 0.75, 'sequencing_planning': 0.20833333333333334, 'argument_parameter': 0.041666666666666664}`
- Replay failure-type shares: `{'wrong_function': 0.75, 'wrong_order_or_context': 0.20833333333333334, 'wrong_arguments': 0.041666666666666664}`
- Propagation rate: `0.375`
- Recovery rate: `0.625`

### `claude_sonnet46::JA`

- Replay stage shares: `{'intent_selection': 0.8, 'argument_parameter': 0.2}`
- Replay failure-type shares: `{'wrong_function': 0.8, 'wrong_arguments': 0.2}`
- Propagation rate: `0.375`
- Recovery rate: `0.625`

### `claude_sonnet46::SW`

- Replay stage shares: `{'intent_selection': 0.6, 'argument_parameter': 0.36666666666666664, 'sequencing_planning': 0.03333333333333333}`
- Replay failure-type shares: `{'wrong_function': 0.6, 'wrong_arguments': 0.36666666666666664, 'wrong_order_or_context': 0.03333333333333333}`
- Propagation rate: `0.875`
- Recovery rate: `0.125`

### `claude_sonnet46::TR`

- Replay stage shares: `{'intent_selection': 0.8235294117647058, 'argument_parameter': 0.17647058823529413}`
- Replay failure-type shares: `{'wrong_function': 0.8235294117647058, 'wrong_arguments': 0.17647058823529413}`
- Propagation rate: `0.375`
- Recovery rate: `0.625`

### `claude_sonnet46::ZH`

- Replay stage shares: `{'argument_parameter': 0.5217391304347826, 'sequencing_planning': 0.21739130434782608, 'intent_selection': 0.2608695652173913}`
- Replay failure-type shares: `{'wrong_arguments': 0.5217391304347826, 'wrong_order_or_context': 0.21739130434782608, 'wrong_function': 0.21739130434782608, 'no_call': 0.043478260869565216}`
- Propagation rate: `0.625`
- Recovery rate: `0.375`

### `gemini::AR`

- Replay stage shares: `{'argument_parameter': 0.5714285714285714, 'sequencing_planning': 0.35714285714285715, 'intent_selection': 0.07142857142857142}`
- Replay failure-type shares: `{'wrong_arguments': 0.5714285714285714, 'wrong_order_or_context': 0.35714285714285715, 'wrong_function': 0.07142857142857142}`
- Propagation rate: `1.0`
- Recovery rate: `0.0`

### `gemini::EN`

- Replay stage shares: `{'sequencing_planning': 0.8, 'intent_selection': 0.2}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.8, 'wrong_function': 0.2}`
- Propagation rate: `0.0`
- Recovery rate: `1.0`

### `gemini::ES`

- Replay stage shares: `{'argument_parameter': 0.4444444444444444, 'sequencing_planning': 0.4444444444444444, 'intent_selection': 0.1111111111111111}`
- Replay failure-type shares: `{'wrong_arguments': 0.4444444444444444, 'wrong_order_or_context': 0.4444444444444444, 'wrong_function': 0.1111111111111111}`
- Propagation rate: `0.5`
- Recovery rate: `0.5`

### `gemini::HI`

- Replay stage shares: `{'sequencing_planning': 0.6666666666666666, 'intent_selection': 0.3333333333333333}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.6666666666666666, 'wrong_function': 0.3333333333333333}`
- Propagation rate: `0.3333333333333333`
- Recovery rate: `0.6666666666666666`

### `gemini::JA`

- Replay stage shares: `{'sequencing_planning': 0.5454545454545454, 'argument_parameter': 0.18181818181818182, 'intent_selection': 0.2727272727272727}`
- Replay failure-type shares: `{'wrong_order_or_context': 0.5454545454545454, 'wrong_arguments': 0.18181818181818182, 'wrong_function': 0.2727272727272727}`
- Propagation rate: `0.3333333333333333`
- Recovery rate: `0.6666666666666666`

### `gemini::SW`

- Replay stage shares: `{'argument_parameter': 0.5333333333333333, 'intent_selection': 0.3333333333333333, 'sequencing_planning': 0.13333333333333333}`
- Replay failure-type shares: `{'wrong_arguments': 0.5333333333333333, 'wrong_function': 0.3333333333333333, 'wrong_order_or_context': 0.13333333333333333}`
- Propagation rate: `1.0`
- Recovery rate: `0.0`

### `gemini::TR`

- Replay stage shares: `{'intent_selection': 0.625, 'sequencing_planning': 0.375}`
- Replay failure-type shares: `{'wrong_function': 0.625, 'wrong_order_or_context': 0.375}`
- Propagation rate: `0.75`
- Recovery rate: `0.25`

### `gemini::ZH`

- Replay stage shares: `{'intent_selection': 0.4166666666666667, 'sequencing_planning': 0.3333333333333333, 'argument_parameter': 0.25}`
- Replay failure-type shares: `{'wrong_function': 0.4166666666666667, 'wrong_order_or_context': 0.3333333333333333, 'wrong_arguments': 0.25}`
- Propagation rate: `1.0`
- Recovery rate: `0.0`

