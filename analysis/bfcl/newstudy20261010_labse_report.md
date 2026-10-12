# LaBSE translation consistency diagnostic

This local diagnostic compares each direct English source turn with its current target-language turn. It does not use backtranslations. Cosine scores measure embedding similarity, not translation accuracy or probability of correctness. No universal pass threshold is applied.

- Model: `sentence-transformers/LaBSE` at pinned revision `836121a0533e5664b21c7aacc5d22951f2b8b25b`
- Frozen localization cache SHA-256: `04f858c21801117fe0f99d6974773d1818c10d91a3ecbbf1579c707455a4e034`
- Collection audit SHA-256: `df3b288c6d5a0be6db9c529fc028370d793df6bf725fddc0922761538b530606`
- Scored nonempty direct pairs: 602 across 7 languages
- Encoder window policy: No chunking: every nonempty text is tokenized without special tokens and must fit within max_seq_length minus tokenizer special-token allowance. Over-limit text fails explicitly; no truncation is allowed.

## Score distribution by language

| Language | Pairs | Median | 10th percentile | Minimum | Mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| AR | 86 | 0.9269 | 0.8782 | 0.7912 | 0.9199 |
| ES | 86 | 0.9377 | 0.9009 | 0.8789 | 0.9339 |
| HI | 86 | 0.8705 | 0.8146 | 0.6145 | 0.8641 |
| JA | 86 | 0.8737 | 0.8101 | 0.7118 | 0.8667 |
| SW | 86 | 0.9111 | 0.8550 | 0.8003 | 0.9024 |
| TR | 86 | 0.8823 | 0.8108 | 0.7482 | 0.8744 |
| ZH | 86 | 0.9282 | 0.8540 | 0.6928 | 0.9116 |

## Lowest-scoring real pairs for manual inspection

### AR

- `multi_turn_miss_param_97` turn 3, cosine `0.7912`. Source: Great! My tank are full now. Target: رائع! خزان الوقود ممتلئ الآن.
- `multi_turn_miss_param_39` turn 0, cosine `0.8362`. Source: I need you to set up a fresh folder wherever you're currently working. Target: أحتاج منك إنشاء مجلد جديد في المكان الذي تعمل فيه حاليًا.
- `multi_turn_long_context_59` turn 2, cosine `0.8378`. Source: With the liters in mind, I'll need to top up my vehicleâ€™s tank. Please go ahead and fill up the tank before I hit the road. Target: مع وضع اللترات في الاعتبار، سأحتاج إلى تعبئة خزان السيارة. يرجى المضي قدمًا وملء الخزان قبل أن أنطلق في الطريق.

### ES

- `multi_turn_long_context_2` turn 0, cosine `0.8789`. Source: Go into document folder and Could you draft up a create a document titled 'TeamNotes.txt' for keeping track of all the fresh ideas? Target: Ve a la carpeta de documentos y crea un documento llamado 'TeamNotes.txt' para llevar un registro de las ideas nuevas, por favor.
- `multi_turn_miss_func_55` turn 4, cosine `0.8822`. Source: Apparently, I never got feedback on the tire pressure ticket I created. Can you fetch that ticket for me so I can review the current status? Target: Aparentemente, nunca recibí comentarios sobre el ticket de presión de neumáticos que creé. ¿Puedes buscar ese ticket para mí para que pueda revisar el estado actual?
- `multi_turn_miss_param_39` turn 0, cosine `0.8860`. Source: I need you to set up a fresh folder wherever you're currently working. Target: Necesito que configures una carpeta nueva donde sea que estés trabajando actualmente.

### HI

- `multi_turn_miss_param_39` turn 0, cosine `0.6145`. Source: I need you to set up a fresh folder wherever you're currently working. Target: आप जिस फ़ोल्डर में अभी काम कर रहे हैं, उसमें एक नया फ़ोल्डर बनाएं।
- `multi_turn_miss_param_97` turn 4, cosine `0.7817`. Source: With my tank now full, let's embark on this journey. I'd appreciate it if you could start the car for me. Target: अब जब मेरा टैंक पूरा भर गया है, तो चलिए इस यात्रा पर निकलते हैं। अगर आप मेरे लिए कार स्टार्ट कर सकें तो मैं आभारी रहूंगा।
- `multi_turn_miss_param_97` turn 2, cosine `0.7847`. Source: Thanks a lot! Before I embark on this journey, it makes sense to ensure I won't be left stranded due to an empty tank. Just add to the tank fully. Target: बहुत धन्यवाद! इस यात्रा पर निकलने से पहले यह सुनिश्चित करना समझदारी है कि मैं खाली टैंक के कारण कहीं फंस न जाऊं। बस टैंक को पूरी तरह से भर दें।

### JA

- `multi_turn_miss_param_97` turn 2, cosine `0.7118`. Source: Thanks a lot! Before I embark on this journey, it makes sense to ensure I won't be left stranded due to an empty tank. Just add to the tank fully. Target: ありがとうございます！この旅に出る前に、燃料切れで立ち往生しないようにするのが賢明ですね。タンクを満タンにしてください。
- `multi_turn_long_context_59` turn 2, cosine `0.7315`. Source: With the liters in mind, I'll need to top up my vehicleâ€™s tank. Please go ahead and fill up the tank before I hit the road. Target: リットルを考慮して、車のタンクを満タンにする必要があります。出発する前にタンクを満タンにしてください。
- `multi_turn_miss_param_39` turn 0, cosine `0.7541`. Source: I need you to set up a fresh folder wherever you're currently working. Target: 現在作業している場所に新しいフォルダを作成してください。

### SW

- `multi_turn_long_context_59` turn 2, cosine `0.8003`. Source: With the liters in mind, I'll need to top up my vehicleâ€™s tank. Please go ahead and fill up the tank before I hit the road. Target: Kwa kuzingatia lita nilizo nazo, nitahitaji kujaza tanki la gari langu. Tafadhali endelea na kujaza tanki kabla sijaanza safari.
- `multi_turn_miss_param_70` turn 2, cosine `0.8114`. Source: I mean they should be at 32 PSI. Should any of the tires fall short, chart a course to the nearest tire service center to have this rectified. Target: Namaanisha zinapaswa kuwa kwenye 32 PSI. Ikiwa shinikizo la tairi lolote liko chini ya kiwango hicho, panga njia hadi kituo cha huduma ya matairi kilicho karibu ili kurekebisha hali hiyo.
- `multi_turn_base_80` turn 3, cosine `0.8297`. Source: With the tank now replenished, let's confirm our readiness for departure. Please secure all doors and initiate the engine for me. Target: Kwa kuwa tanki sasa limejazwa, hebu thibitisha utayari wetu wa kuondoka. Tafadhali funga milango yote na washa injini kwa ajili yangu.

### TR

- `multi_turn_miss_param_39` turn 0, cosine `0.7482`. Source: I need you to set up a fresh folder wherever you're currently working. Target: Şu anda çalıştığınız yerde yeni bir klasör oluşturmanızı istiyorum.
- `multi_turn_long_context_59` turn 2, cosine `0.7678`. Source: With the liters in mind, I'll need to top up my vehicleâ€™s tank. Please go ahead and fill up the tank before I hit the road. Target: Litrelere bakarak, aracımın deposunu doldurmam gerekecek. Yola çıkmadan önce lütfen depoyu doldurun.
- `multi_turn_miss_param_70` turn 2, cosine `0.7875`. Source: I mean they should be at 32 PSI. Should any of the tires fall short, chart a course to the nearest tire service center to have this rectified. Target: Yani lastik basınçları 32 PSI olmalı. Lastiklerden herhangi birinin basıncı 32 PSI değerinin altındaysa, sorunu gidermek için en yakın lastik servis merkezine giden bir rota belirleyin.

### ZH

- `multi_turn_long_context_71` turn 2, cosine `0.6928`. Source: Fill the fuel tank to completely full. Target: 将油箱加满。
- `multi_turn_miss_func_92` turn 2, cosine `0.7113`. Source: Given this apprehension, can you fill up the fuel completely? Target: 鉴于这种担忧，你能帮我把油箱加满吗？
- `multi_turn_long_context_71` turn 3, cosine `0.7832`. Source: With the vehicle secured, start the engine for our prepared journey. Target: 在车辆安全的情况下，启动引擎，准备出发。

## Literal-preservation diagnostics

Numeric multiset differences: 0 of 602 pairs.
Rows with an exact source-quoted literal not found in the target text: 0.
Rows with a source filename not found verbatim in the target text: 0.
These are string-level review flags. They do not determine semantic correctness; number formatting and localization choices can require inspection. Full values are in the pair CSV.

## Controlled comparisons

| Control type | Class | Pairs | Mean baseline cosine | Mean comparison cosine | Mean score drop |
| --- | --- | ---: | ---: | ---: | ---: |
| mismatched_task_turn | real_task_cross_pair_control | 483 | 0.8959 | 0.3241 | 0.5718 |
| negation_reversal | artificial_authored_challenge | 7 | 0.8586 | 0.8008 | 0.0578 |
| number_changed | real_bfcl_target_corruption | 79 | 0.9106 | 0.8819 | 0.0287 |
| quoted_literal_or_filename_changed | real_bfcl_target_corruption | 245 | 0.9081 | 0.8852 | 0.0229 |

Number and quoted-literal corruptions alter real BFCL target turns deterministically. Mismatched-task controls pair a source turn with another task's target turn at the same language and turn index. Negation controls are separately authored challenge sentences with their provenance in the JSON input. These controls test score sensitivity; they are not a benchmark of natural translation errors.

## Interpretation limits

LaBSE was trained to represent cross-lingual sentence meaning and retrieve translation pairs. A high cosine score can coexist with a changed number, filename, negation, or task constraint, and a lower score can reflect valid wording or domain-specific phrasing. The score is not calibrated as an accuracy percentage. Review the lowest pairs and the per-control score changes alongside the direct author review and literal checks. This diagnostic alone cannot establish that every translation is accurate.

## Reproducibility

- Created UTC: `2026-10-10T23:18:36.316872+00:00`
- Python and package versions: `{"numpy": "2.4.6", "python": "3.11.9", "sentence-transformers": "5.1.2", "torch": "2.8.0+cu128", "transformers": "4.57.1"}`
- Tokenizer max sequence length: `256`
- Negation challenge file SHA-256: `aa9d970e1c22f76fac505d65bfc1acd0a5a76a530f6881895eb8e288d4f0dc04`
- Command argv: `["scripts/run_translation_similarity.py", "--model-revision", "836121a0533e5664b21c7aacc5d22951f2b8b25b", "--model-path", "<local-model-snapshot>", "--device", "cuda"]`
