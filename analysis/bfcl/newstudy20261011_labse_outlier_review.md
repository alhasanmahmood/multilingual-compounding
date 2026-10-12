# LaBSE outlier and numeric-flag review

- Scored CSV: `analysis/bfcl/newstudy20261010_labse_pairs.csv`
- CSV SHA-256: `7885706bb5873e725128f729c9d5fb23be19c5cb843c1b32abd262a2cafb0604`
- Model: `sentence-transformers/LaBSE` revision `836121a0533e5664b21c7aacc5d22951f2b8b25b`
- Input population: 602 rows across 7 languages, 86 per language.
- Full-text inspection: 54 unique rows, covering the lowest 3 scores per language (21 rows) and all 34 numeric flags, with 1 overlap.
- Literal/filename flags: 0 quoted-literal and 0 filename preservation failures.

## Result

No confirmed task-critical mistranslation or wrong number was found in the inspected rows. All numeric flags were explained by number wording, regex boundaries, equivalent precision wording, or a repeated threshold. See JSON for each exact pair ID, extracted values, and disposition.

Two wording nuances remain: HI `multi_turn_miss_param_39/HI/0` slightly narrows the folder location to the folder currently being worked in; ZH `multi_turn_long_context_71/ZH/3` renders “vehicle secured” broadly as “vehicle in a safe condition.” Neither is a confirmed task change; the English “secured” wording is ambiguous.

This is a targeted AI review, not native-speaker certification of all translations. Cosine similarity is a screening signal, not an accuracy percentage.

## Lowest three cosine pairs per language

| Language | Pair ID | Cosine | Disposition |
|---|---|---:|---|
| AR | `multi_turn_miss_param_97/AR/3` | 0.7912 | faithful: Tank full now; faithful. |
| AR | `multi_turn_miss_param_39/AR/0` | 0.8362 | faithful: New folder at current work location; faithful. |
| AR | `multi_turn_long_context_59/AR/2` | 0.8378 | faithful_in_context: Carries the preceding liters context into the fill request; faithful. |
| ES | `multi_turn_long_context_2/ES/0` | 0.8789 | faithful: Repairs source disfluency and preserves folder, filename, and purpose. |
| ES | `multi_turn_miss_func_55/ES/4` | 0.8822 | faithful: Ticket, missing feedback, and status retrieval preserved. |
| ES | `multi_turn_miss_param_39/ES/0` | 0.8860 | faithful: New folder wherever currently working; faithful. |
| HI | `multi_turn_miss_param_39/HI/0` | 0.6145 | faithful_with_slight_location_specificity: Faithful, with slight specificity: says inside the folder currently being worked in. |
| HI | `multi_turn_miss_param_97/HI/4` | 0.7817 | faithful: Tank-full context and request to start car preserved. |
| HI | `multi_turn_miss_param_97/HI/2` | 0.7847 | faithful: Empty-tank concern and request to fill fully preserved. |
| JA | `multi_turn_miss_param_97/JA/2` | 0.7118 | faithful: Fuel-exhaustion concern and request to fill tank preserved. |
| JA | `multi_turn_long_context_59/JA/2` | 0.7315 | faithful_in_context: Carries the preceding liters context into the fill request; faithful. |
| JA | `multi_turn_miss_param_39/JA/0` | 0.7541 | faithful: New folder at current work location; faithful. |
| SW | `multi_turn_long_context_59/SW/2` | 0.8003 | faithful_in_context: Prior turn establishes liters on hand; translation carries context forward. |
| SW | `multi_turn_miss_param_70/SW/2` | 0.8114 | faithful: 32 PSI target, below-target condition, and repair route preserved. |
| SW | `multi_turn_base_80/SW/3` | 0.8297 | faithful: Full tank, securing doors, and starting engine preserved. |
| TR | `multi_turn_miss_param_39/TR/0` | 0.7482 | faithful: New folder where currently working; faithful. |
| TR | `multi_turn_long_context_59/TR/2` | 0.7678 | faithful_in_context: Carries the preceding liters context into the fill request; faithful. |
| TR | `multi_turn_miss_param_70/TR/2` | 0.7875 | faithful_with_explicit_threshold_repeat: Repeats 32 PSI to make the conditional threshold explicit; faithful. |
| ZH | `multi_turn_long_context_71/ZH/2` | 0.6928 | faithful: Request to fill fuel tank completely preserved. |
| ZH | `multi_turn_miss_func_92/ZH/2` | 0.7113 | faithful: Concern and request to fill tank completely preserved. |
| ZH | `multi_turn_long_context_71/ZH/3` | 0.7832 | faithful_with_wording_nuance: “Secured” becomes broadly “in a safe condition”; source is ambiguous, no confirmed task change. |

## Numeric flags

| Disposition | Exact pair IDs |
|---|---|
| 3 is written as Arabic ثلاثة. | `multi_turn_miss_param_39/AR/2` |
| The target visibly contains the number, but adjacency to Arabic, Chinese, Japanese, or another Unicode letter prevents the regex boundary match. | `multi_turn_base_63/JA/0`<br>`multi_turn_base_63/ZH/0`<br>`multi_turn_base_65/JA/0`<br>`multi_turn_base_65/ZH/0`<br>`multi_turn_long_context_59/JA/4`<br>`multi_turn_long_context_59/ZH/4`<br>`multi_turn_miss_func_55/JA/0`<br>`multi_turn_miss_func_55/ZH/0`<br>`multi_turn_miss_func_69/JA/0`<br>`multi_turn_miss_func_69/ZH/0`<br>`multi_turn_miss_func_90/JA/0`<br>`multi_turn_miss_func_90/ZH/0`<br>`multi_turn_miss_func_92/JA/4`<br>`multi_turn_miss_param_171/JA/2`<br>`multi_turn_miss_param_171/ZH/2`<br>`multi_turn_miss_param_39/JA/2`<br>`multi_turn_miss_param_39/ZH/2`<br>`multi_turn_miss_param_58/JA/2`<br>`multi_turn_miss_param_58/ZH/2`<br>`multi_turn_miss_param_70/JA/0`<br>`multi_turn_miss_param_70/ZH/0` |
| Both ZIP identifiers are visible but adjacent to Japanese text. | `multi_turn_miss_func_92/JA/0` |
| 0.01 and two decimal places express the source “nearest hundredth.” | `multi_turn_base_63/TR/1` |
| Turkish repeats 32 PSI as the explicit threshold in the conditional. | `multi_turn_miss_param_70/TR/2` |
| 32 PSI is visibly present and repeated; Chinese adjacency also blocks regex extraction. | `multi_turn_miss_param_70/ZH/2` |
| Arabic target visibly contains 290.0; regex captures only the final decimal 0 because the preceding Arabic conjunction blocks the left boundary. | `multi_turn_base_80/AR/4` |
| Source “15th” is missed by the regex; target correctly renders June 15, 2026. | `multi_turn_miss_param_171/AR/0`<br>`multi_turn_miss_param_171/ES/0`<br>`multi_turn_miss_param_171/HI/0`<br>`multi_turn_miss_param_171/SW/0`<br>`multi_turn_miss_param_171/TR/0` |
| Source “15th” is missed; target correctly renders June 15 and other visible values adjacent to Chinese or Japanese text are also missed. | `multi_turn_miss_param_171/JA/0`<br>`multi_turn_miss_param_171/ZH/0` |

The JSON sidecar gives the source/target numeric arrays and exact disposition for each flagged pair. No translation cache, scored CSV, manuscript, or API endpoint was modified or called.
