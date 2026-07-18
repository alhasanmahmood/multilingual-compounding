# E3 Metrics Contract

This note locks the interface between the evaluation pipeline and
`src/multilingual_compounding/metrics.py`.

## Required record shape

Each E2 output record passed into the metrics module must provide:

- `task_id`: stable task identifier used for paired task-level bootstrap
- `language`: language label (`EN`/`English` accepted as the English baseline)
- `backbone`: model identifier
- `success`: full multi-turn task outcome in `{0,1}`
- `step_validity`: ordered list of isolated single-turn validity outcomes in `{0,1}`

## Non-negotiable measurement rule

`step_validity` must come from isolated replay of each critical step with the
gold preceding context. It must not be computed from in-trajectory marginal
calls emitted during the full run.

## Audit outcomes

The quick audit of the original stub found one contract gap that had to be
fixed before any benchmark work:

- the bootstrap claimed to be task-level, but `TaskRecord` had no `task_id`, so
  resampling could not preserve paired task structure across languages within a
  backbone

The corrected implementation now:

- requires `task_id`
- treats English labels robustly (`EN` and `English`)
- resamples tasks, not language-specific rows
- keeps the rest of the paper-facing CF / Delta logic unchanged

## Regression coverage

`tests/test_compounding_metrics.py` covers:

- English baseline alias handling
- paired task-level bootstrap execution
- synthetic detection of compounding (`CF > 1` / `Delta < 0`)
