# Historical BFCL Translation Literal Audit

This read-only audit checks all 32 rows in `data/bfcl/localized_queries/bfcl_multiturn_localizations.jsonl`, including 28 non-English rows across Arabic, Turkish, Chinese, Hindi, Japanese, Spanish, and Swahili. The original cache SHA-256 is `568cc26f5e53502669010b67778af28078d50f20064270626484ef2bf1644b14`. English turns came from the pinned BFCL snapshot `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`.

The four task IDs are category variants of numeric scenario 0 and share one underlying scenario. Findings below are descriptive for this one scenario, not independent replications. No cache or raw result was edited. No external API was called, and this audit is not human or native-speaker verification.

## Result

The cache reports machine invariance passing for 28/28 non-English rows, with an empty machine `missing_literals` field for 28/28 rows. Direct target-language checking found 24 missing exact quoted-literal occurrences across 12 rows. All misses are the search term `'budget analysis'`, translated in instructions asking `grep` to find that exact text.

The exact-literal check examined 189 source-quoted occurrences. Other quoted filenames and directory names were preserved. The blank turn in `multi_turn_miss_func_0` stayed empty at the same index in all seven target languages. No additional material issue was found in task meaning, turn sequence, numeric or unit constraints, or the intentionally incomplete miss-parameter prompts.

| Language | Direct literal misses | Affected rows |
|---|---:|---:|
| AR | 8 | 4 |
| TR | 0 | 0 |
| ZH | 6 | 3 |
| HI | 0 | 0 |
| JA | 2 | 1 |
| ES | 0 | 0 |
| SW | 8 | 4 |


## Direct findings

For each finding, the exact English source term appears in the original prompt but not in the target text. The target text gives a translated phrase instead. Since the user requested a literal `grep` search, that can search for a different string and miss the intended content.

### Arabic (8 turn findings)

#### `multi_turn_base_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
قم بإجراء بحث مفصل باستخدام grep لتحديد الأقسام في الملف المتعلقة بـ 'تحليل الميزانية'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_base_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
عند تحديد محتوى 'تحليل الميزانية' المطلوب، قم بفرز 'final_report.pdf' حسب السطر لتحسين الوضوح والفهم.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
قم بإجراء بحث مفصل باستخدام grep لتحديد الأقسام في الملف المتعلقة بـ 'تحليل الميزانية'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
عند تحديد محتوى 'تحليل الميزانية' المطلوب، قم بفرز 'final_report.pdf' حسب السطر لتحسين الوضوح والفهم.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_param_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
قم بإجراء بحث مفصل باستخدام grep لتحديد الأقسام في الملف المتعلقة بـ 'تحليل الميزانية'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_param_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
عند تحديد محتوى 'تحليل الميزانية' المطلوب، قم بفرز 'final_report.pdf' حسب السطر لتحسين الوضوح والفهم.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
قم بإجراء بحث مفصل باستخدام grep لتحديد الأقسام في الملف المتعلقة بـ 'تحليل الميزانية'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
عند تحديد محتوى 'تحليل الميزانية' المطلوب، قم بفرز 'final_report.pdf' حسب السطر لتحسين الوضوح والفهم.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

### Chinese (6 turn findings)

#### `multi_turn_base_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
使用 grep 进行详细搜索，以识别文件中与“预算分析”相关的部分。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_base_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
在识别出所需的“预算分析”内容后，按行对“final_report.pdf”进行排序，以提高清晰度和理解。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
使用 grep 进行详细搜索，以识别文件中与“预算分析”相关的部分。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
在识别出所需的“预算分析”内容后，按行对“final_report.pdf”进行排序，以提高清晰度和理解。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
使用 grep 进行详细搜索，以识别文件中与“预算分析”相关的部分。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
在识别出所需的“预算分析”内容后，按行对“final_report.pdf”进行排序，以提高清晰度和理解力。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

### Japanese (2 turn findings)

#### `multi_turn_base_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
grepを使用して詳細な検索を行い、ファイル内の「予算分析」に関するセクションを特定してください。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_base_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
必要な「予算分析」コンテンツを特定したら、'final_report.pdf' を行ごとに並べ替えて、明確さと理解を向上させてください。
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

### Swahili (8 turn findings)

#### `multi_turn_base_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
Fanya utafutaji wa kina kwa kutumia grep ili kutambua sehemu katika faili zinazohusiana na 'uchambuzi wa bajeti'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_base_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
Baada ya kutambua maudhui yanayohitajika ya 'uchambuzi wa bajeti', panga 'final_report.pdf' kwa mstari ili kuboresha uwazi na uelewa.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
Fanya utafutaji wa kina kwa kutumia grep ili kutambua sehemu katika faili zinazohusiana na 'uchambuzi wa bajeti'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_func_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
Baada ya kutambua maudhui yanayohitajika ya 'uchambuzi wa bajeti', panga 'final_report.pdf' kwa mstari ili kuboresha uwazi na uelewa.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_param_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
Fanya utafutaji wa kina kwa kutumia grep ili kutambua sehemu katika faili zinazohusiana na 'uchambuzi wa bajeti'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_miss_param_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
Baada ya kutambua maudhui yanayohitajika ya 'uchambuzi wa bajeti', panga 'final_report.pdf' kwa mstari ili kuboresha uwazi na uelewa.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 1

Missing exact source literal: `budget analysis`.

Source:
```text
Perform a detailed search using grep to identify sections in the file pertaining to 'budget analysis'.
```

Target:
```text
Fanya utafutaji wa kina kwa kutumia grep ili kutambua sehemu katika faili zinazohusiana na 'uchambuzi wa bajeti'.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

#### `multi_turn_long_context_0`, turn 2

Missing exact source literal: `budget analysis`.

Source:
```text
Upon identifying the requisite 'budget analysis' content, sort the 'final_report.pdf' by line for improved clarity and comprehension.
```

Target:
```text
Baada ya kutambua maudhui yanayohitajika ya 'uchambuzi wa bajeti', panga 'final_report.pdf' kwa mstari ili kuboresha uwazi na uelewa.
```

Machine invariance: `true`. Machine missing-literal field: `[]`.

Recommended fix: keep `'budget analysis'` verbatim and translate the surrounding instruction.

## Interpretation

These machine checks missed an exact-text mismatch that matters for execution: the phrase is not just a concept to translate, it is the string passed to `grep`. The mismatch repeats across four category variants of the same scenario, so it should be treated as one recurring localization issue in a narrow historical sample.

Backtranslation and machine invariance are cache diagnostics only. This report compares each target turn directly with the English source. The JSON companion provides all 28 row-level cache diagnostics, hashes, source and target evidence for every finding, and per-language and per-task counts.
