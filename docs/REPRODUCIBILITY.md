# Reproducibility and release scope

The main study contains 20 distinct BFCL scenarios, eight query languages,
two model configurations, and two seeds: 640 full trajectories and 5,952
isolated replays. All analyses can be reproduced from saved data without
model-API calls. The README gives the setup and commands.

Use Python 3.11 and the tested dependency versions in
`requirements-reproduction.txt` for the offline environment. The general
`requirements.txt` supports development; its tree-sitter pins are required
by the vendored evaluator. LaBSE uses a separate environment and
`requirements-translation-diagnostics.txt`. Its model revision and file hashes
are published with the scores; model weights are downloaded separately.

The collection audit checks complete task-language-model-seed coverage,
source and target hashes, query alignment, provider identities, and every
reference-call replay position. The source/display audit checks the official
style files, references, displayed values, plot points and intervals, and
translation-score summaries. Unit tests cover the analysis and collection
guards. These checks verify internal consistency; they do not turn the
selected tasks into representative coverage or causal evidence.

Data and generated evidence retain exact bytes through `.gitattributes`.
The raw-file manifest uses the original v1 digest convention, normalizing
path separators to backslashes for hashing on all operating systems. Displayed
paths use portable relative names. The frozen plan and localization cache
hashes remain unchanged.

Original collector-source bytes are retained under
`data/bfcl/collection_source_snapshot/` with their recorded SHA-256 hashes.
These files document the code used for collection; run the current scripts
under `scripts/` for new work. The current coordinator adds a stricter offline
input gate before any provider job. A new collection should use a separate
plan and artifact prefix rather than replacing the frozen study.

Direct AI review corrected 86 of 140 non-English query sets. The indexed
review JSONs and later targeted LaBSE dispositions remain published to support
that input-quality account. The author attestation records mixed review of
target text and English backtranslations. None of these establish independent
bilingual validation; cosine similarity is not an accuracy percentage.

Publication cleanup normalized only workstation paths, process IDs, and
command presentation. `analysis/bfcl/publication_metadata.json` records the
before/after metadata hashes. Raw queries, trajectories, replay outcomes,
the plan, scores, and numerical summaries were not altered. Original metadata
is retained privately. Public local-model paths use an explicit placeholder
while preserving model revision and manifest verification hashes.

Commands that regenerate deterministic calibration, sensitivity, environment
reports, or paper displays replace their named outputs. To retain published
outputs, use the supplied alternate summary/report paths or a new output
prefix. The completed-expansion analyzer and LaBSE scorer refuse existing
outputs. The primary display generator updates only the table and figure;
edited manuscript prose is preserved.

Private review correspondence, financial notes, credentials, local logs,
render histories, environments, model weights, supervisor state, and duplicate
review presentations are ignored. The exporter selects only the curated
Git-tracked files. A public repository export is not an anonymous submission
package; verify the anonymous snapshot separately.
