from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from ast import Call, Name, keyword, literal_eval, parse
from dataclasses import asdict
from math import log
from pathlib import Path
from statistics import mean
from typing import Any

from . import metrics as compounding_metrics
from .bfcl_vendor import (
    BFCLTask,
    StepReplayCase,
    build_handler,
    build_step_replay_cases,
    evaluate_multi_turn_entry,
    evaluate_step_replay,
    load_bfcl_multiturn_tasks,
)
from .env import load_env_file
from .localization import (
    OpenAICompatibleTranslator,
    build_localization_artifact,
)
from .paths import (
    LOCALIZATION_ROOT,
    METADATA_ROOT,
    REPLAY_ROOT,
    ROOT_ENV_FILE,
    RUNS_ROOT,
    SUMMARY_ROOT,
    TRACE_ROOT,
    ensure_project_dirs,
)
from .settings import (
    BFCL_COMMIT,
    DEFAULT_RUN_LABELS,
    DEFAULT_TEMPERATURE,
    PILOT_MODELS,
    PILOT_TEST_CATEGORIES,
    language_pairs,
)


def load_metrics_module():
    return compounding_metrics


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(make_json_safe(record), ensure_ascii=False) + "\n")


def write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    """Replace a JSONL file atomically after an explicit cache refresh."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    write_jsonl(temporary_path, records)
    os.replace(temporary_path, path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Durably append one completed artifact row for interruption-safe runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(make_json_safe(record), ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect_artifact_records(
    model_keys: list[str],
    run_labels: list[str],
    language_codes: list[str] | None = None,
    artifact_prefix: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    full_run_records: list[dict[str, Any]] = []
    replay_records: list[dict[str, Any]] = []
    selected_languages = language_pairs(language_codes)
    for model_key in model_keys:
        for run_label in run_labels:
            for language_code, _language_name in selected_languages:
                full_run_records.extend(
                    read_jsonl(
                        _artifact_output_path(
                            RUNS_ROOT,
                            f"{model_key}_{language_code}_{run_label}.jsonl",
                            artifact_prefix,
                        )
                    )
                )
                replay_records.extend(
                    read_jsonl(
                        _artifact_output_path(
                            REPLAY_ROOT,
                            f"{model_key}_{language_code}_{run_label}.jsonl",
                            artifact_prefix,
                        )
                    )
                )
    return full_run_records, replay_records


def get_original_turn_texts(task: BFCLTask) -> list[str]:
    turns: list[str] = []
    for turn in task.prompt_entry["question"]:
        user_parts = [message["content"] for message in turn if message["role"] == "user"]
        turns.append("\n".join(user_parts))
    return turns


def seed_from_run_label(run_label: str) -> int | None:
    match = re.search(r"seed(\d+)", run_label, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def select_bfcl_tasks(
    tasks: list[BFCLTask],
    task_limit: int | None = None,
    per_category_limit: int | None = None,
    task_ids: list[str] | None = None,
) -> list[BFCLTask]:
    if task_ids is not None:
        requested = list(dict.fromkeys(task_ids))
        by_id = {str(task.prompt_entry["id"]): task for task in tasks}
        missing = [task_id for task_id in requested if task_id not in by_id]
        if missing:
            raise ValueError(f"Unknown BFCL task id(s): {missing}")
        return [by_id[task_id] for task_id in requested]
    if per_category_limit is not None:
        counts: dict[str, int] = {}
        selected: list[BFCLTask] = []
        for task in tasks:
            current = counts.get(task.category, 0)
            if current >= per_category_limit:
                continue
            selected.append(task)
            counts[task.category] = current + 1
        return selected
    if task_limit is not None:
        return tasks[:task_limit]
    return tasks


def _artifact_output_path(directory: Path, filename: str, artifact_prefix: str | None = None) -> Path:
    if artifact_prefix:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", artifact_prefix):
            raise ValueError(
                "Artifact prefixes must start with a letter or digit and contain "
                "only letters, digits, underscores, or hyphens (max 64 characters)."
            )
        return directory / f"{artifact_prefix}_{filename}"
    return directory / filename


def _sha256_json(payload: Any) -> str:
    serialized = json.dumps(
        make_json_safe(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def task_content_sha256(task: BFCLTask) -> str:
    return _sha256_json(
        {
            "category": task.category,
            "prompt_entry": task.prompt_entry,
            "ground_truth": task.ground_truth,
        }
    )


def task_set_sha256(tasks: list[BFCLTask]) -> str:
    return _sha256_json(
        [
            {
                "task_id": str(task.prompt_entry["id"]),
                "task_content_sha256": task_content_sha256(task),
            }
            for task in tasks
        ]
    )


def _localization_cache_path(cache_prefix: str | None = None) -> Path:
    return _artifact_output_path(
        LOCALIZATION_ROOT, "bfcl_multiturn_localizations.jsonl", cache_prefix
    )


def _provider_credentials(api_provider: str) -> tuple[str, str]:
    if api_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
        key_name = "OPENROUTER_API_KEY"
    elif api_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        key_name = "OPENAI_API_KEY"
    else:
        raise ValueError("api_provider must be 'openrouter' or 'openai'.")
    if not api_key:
        raise ValueError(f"{key_name} must be set for api_provider={api_provider}.")
    return api_key, base_url.rstrip("/")


def _configure_handler_provider(handler, api_provider: str, model_key: str) -> str:
    api_key, base_url = _provider_credentials(api_provider)
    if not hasattr(handler, "api_key") or not hasattr(handler, "base_url"):
        raise TypeError(
            f"The configured handler for {model_key!r} cannot use the explicit "
            "provider endpoint required for this run."
        )
    handler.api_key = api_key
    handler.base_url = base_url
    if hasattr(handler, "provider_reported_model_ids"):
        handler.provider_reported_model_ids = []
    return str(PILOT_MODELS[model_key]["model_name"])


def _verify_provider_models(handler, expected_model: str, model_key: str) -> list[str]:
    reported = list(getattr(handler, "provider_reported_model_ids", []))
    normalized = list(dict.fromkeys(str(model).strip() for model in reported if model))
    if not normalized:
        raise RuntimeError(
            f"Provider response for {model_key!r} did not report a resolved model id; "
            "the completed call was not checkpointed."
        )
    unexpected = [model for model in normalized if model.casefold() != expected_model.casefold()]
    if unexpected:
        raise RuntimeError(
            f"Provider resolved {model_key!r} to unexpected model id(s) {unexpected}; "
            f"expected {expected_model!r}. The completed call was not checkpointed."
        )
    return normalized


def _evaluation_fingerprint(
    *,
    stage: str,
    tasks: list[BFCLTask],
    model_key: str,
    run_label: str,
    language_code: str,
    api_provider: str,
    localized_queries_sha256: str | None = None,
) -> str:
    model_info = PILOT_MODELS[model_key]
    return _sha256_json(
        {
            "schema_version": 2,
            "stage": stage,
            "bfcl_commit": BFCL_COMMIT,
            "task_set_sha256": task_set_sha256(tasks),
            "model_key": model_key,
            "requested_model_name": model_info["model_name"],
            "registry_name": model_info["registry_name"],
            "run_label": run_label,
            "seed": seed_from_run_label(run_label),
            "language_code": language_code,
            "temperature": DEFAULT_TEMPERATURE,
            "api_provider": api_provider,
            "localized_queries_sha256": localized_queries_sha256,
        }
    )


def _checkpoint_key(stage: str, record: dict[str, Any]) -> tuple[Any, ...]:
    common = (
        record.get("task_id"),
        record.get("language_code"),
        record.get("model_key"),
        record.get("run_label"),
    )
    if stage == "full":
        return common
    return common + (record.get("turn_index"), record.get("step_index"))


def _load_stage_checkpoint(
    path: Path,
    *,
    stage: str,
    fingerprint: str,
    task_hashes: dict[str, str],
    model_key: str,
    run_label: str,
    language_code: str,
    expected_model: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    checkpoint: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in read_jsonl(path):
        if record.get("evaluation_fingerprint") != fingerprint:
            raise ValueError(
                f"Checkpoint {path} does not match the requested dataset/settings. "
                "Use a new --artifact-prefix; existing results were left untouched."
            )
        task_id = str(record.get("task_id"))
        if task_id not in task_hashes or record.get("task_content_sha256") != task_hashes[task_id]:
            raise ValueError(f"Checkpoint {path} contains a missing or changed task fingerprint.")
        identity = (record.get("model_key"), record.get("run_label"), record.get("language_code"))
        if identity != (model_key, run_label, language_code):
            raise ValueError(f"Checkpoint {path} contains a row for a different model/run/language.")
        model_ids = record.get("provider_reported_model_ids")
        if not model_ids or any(str(model_id).casefold() != expected_model.casefold() for model_id in model_ids):
            raise ValueError(
                f"Checkpoint {path} lacks the expected provider-reported model identity; "
                "use a new --artifact-prefix."
            )
        key = _checkpoint_key(stage, record)
        if key in checkpoint:
            raise ValueError(f"Checkpoint {path} contains duplicate result key {key}.")
        checkpoint[key] = record
    return checkpoint


def _localization_fingerprint(
    task: BFCLTask,
    language_code: str,
    language_name: str,
    translation_model: str,
    api_provider: str,
) -> str:
    return _sha256_json(
        {
            "schema_version": 1,
            "bfcl_commit": BFCL_COMMIT,
            "task_content_sha256": task_content_sha256(task),
            "language_code": language_code,
            "language_name": language_name,
            "translation_model": translation_model,
            "api_provider": api_provider,
            "prompt_version": 1,
        }
    )


def _validate_localization_record(
    record: dict[str, Any],
    task: BFCLTask,
    language_code: str,
) -> tuple[dict[str, Any], str]:
    task_id = str(task.prompt_entry["id"])
    original_turns = get_original_turn_texts(task)
    if str(record.get("task_id")) != task_id or record.get("language_code") != language_code:
        raise ValueError(f"Localization row does not match requested task/language {task_id}/{language_code}.")
    localized_turns = record.get("localized_turns")
    backtranslated_turns = record.get("backtranslated_turns")
    if (
        not isinstance(localized_turns, list)
        or not isinstance(backtranslated_turns, list)
        or len(localized_turns) != len(original_turns)
        or len(backtranslated_turns) != len(original_turns)
        or any(not isinstance(text, str) or bool(text.strip()) != bool(source.strip())
               for text, source in zip(localized_turns, original_turns))
        or any(not isinstance(text, str) or bool(text.strip()) != bool(source.strip())
               for text, source in zip(backtranslated_turns, original_turns))
    ):
        raise ValueError(f"Localization row has invalid turn content for {task_id}/{language_code}.")
    recomputed = asdict(
        build_localization_artifact(
            task_id=task_id,
            language_code=language_code,
            language_name=str(record.get("language_name") or language_code),
            original_turns=original_turns,
            localized_turns=localized_turns,
            backtranslated_turns=backtranslated_turns,
            ground_truth=task.ground_truth,
        )
    )
    for field in (
        "anchor_literals",
        "preserved_literals",
        "missing_literals",
        "invariance_pass",
        "machine_fidelity_rating",
    ):
        if field in record and record[field] != recomputed[field]:
            raise ValueError(f"Localization row has stale {field} for {task_id}/{language_code}.")
    similarity = record.get("backtranslation_similarity")
    if similarity is not None and abs(float(similarity) - recomputed["backtranslation_similarity"]) > 1e-9:
        raise ValueError(f"Localization row has stale backtranslation similarity for {task_id}/{language_code}.")
    effective = {**record, **recomputed}
    if record.get("task_content_sha256"):
        if record["task_content_sha256"] != task_content_sha256(task):
            raise ValueError(f"Localization row has a stale source-task hash for {task_id}/{language_code}.")
        integrity = "source_hash_verified"
    else:
        integrity = "legacy_semantic_checks_only"
    return effective, integrity


def localize_tasks(
    tasks: list[BFCLTask],
    language_codes: list[str] | None = None,
    force: bool = False,
    cache_prefix: str | None = None,
    api_provider: str = "openrouter",
    require_human_review: bool = False,
    allow_generation: bool = True,
) -> list[dict[str, Any]]:
    output_path = _localization_cache_path(cache_prefix)
    existing_records = read_jsonl(output_path)
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in existing_records:
        key = (str(record.get("task_id")), str(record.get("language_code")))
        if key in by_key:
            raise ValueError(f"Localization cache {output_path} contains duplicate key {key}.")
        by_key[key] = record

    requested: list[tuple[BFCLTask, str, str]] = []
    selected_languages = language_pairs(language_codes)
    for task in tasks:
        for language_code, language_name in selected_languages:
            requested.append((task, language_code, language_name))

    translation_model = os.getenv("TRANSLATION_MODEL") or "gpt-4o-2024-08-06"
    if api_provider == "openrouter" and "/" not in translation_model:
        translation_model = f"openai/{translation_model}"
    missing: list[tuple[BFCLTask, str, str]] = []
    artifacts: list[dict[str, Any]] = []
    for task, language_code, language_name in requested:
        task_id = str(task.prompt_entry["id"])
        key = (task_id, language_code)
        cached = by_key.get(key)
        expected_fingerprint = _localization_fingerprint(
            task, language_code, language_name, translation_model, api_provider
        )
        if cached is None or force:
            missing.append((task, language_code, language_name))
            continue
        if cached.get("localization_fingerprint") and cached["localization_fingerprint"] != expected_fingerprint:
            raise ValueError(
                f"Localization cache row {key} does not match the source/model settings. "
                "Choose a fresh --localization-prefix or explicitly request regeneration."
            )
        if cached.get("localization_fingerprint") and not cached.get("task_content_sha256"):
            raise ValueError(f"Localization cache row {key} is missing its source-task hash.")
        effective, integrity = _validate_localization_record(cached, task, language_code)
        effective["cache_integrity"] = integrity
        artifacts.append(effective)

    if require_human_review:
        unreviewed = []
        for record in artifacts:
            review = record.get("human_review") or {}
            if (
                review.get("status") != "approved"
                or not str(review.get("reviewer", "")).strip()
                or not str(review.get("reviewed_at", "")).strip()
            ):
                unreviewed.append((record["task_id"], record["language_code"]))
        if unreviewed or missing:
            missing_rows = [
                (str(task.prompt_entry["id"]), code) for task, code, _ in missing
            ]
            raise ValueError(
                "Human localization review is required for every selected task/language. "
                f"Unreviewed rows: {unreviewed[:12]}{'...' if len(unreviewed) > 12 else ''}; "
                f"missing rows: {missing_rows[:12]}{'...' if len(missing_rows) > 12 else ''}"
            )

    if not missing:
        return artifacts
    if not allow_generation:
        missing_keys = [(str(task.prompt_entry["id"]), code) for task, code, _ in missing]
        raise FileNotFoundError(
            "Collection-only mode requires a complete localization cache and will not call "
            f"the translator. Missing task/language rows: {missing_keys[:12]}"
            f"{'...' if len(missing_keys) > 12 else ''}"
        )

    api_key, base_url = _provider_credentials(api_provider)
    translator = OpenAICompatibleTranslator(
        model=translation_model, api_key=api_key, base_url=base_url
    )
    for task, language_code, language_name in missing:
        task_id = str(task.prompt_entry["id"])
        key = (task_id, language_code)
        original_turns = get_original_turn_texts(task)
        print(f"[localize] {task_id} -> {language_code}", flush=True)
        if language_code == "EN":
            localized_turns = list(original_turns)
            backtranslated_turns = list(original_turns)
        else:
            if hasattr(translator, "provider_reported_model_ids"):
                translator.provider_reported_model_ids.clear()
            localized_turns = translator.translate_turns(original_turns, language_name)
            backtranslated_turns = translator.backtranslate_turns(
                localized_turns, language_name
            )
        artifact = asdict(
            build_localization_artifact(
                task_id=task_id,
                language_code=language_code,
                language_name=language_name,
                original_turns=original_turns,
                localized_turns=localized_turns,
                backtranslated_turns=backtranslated_turns,
                ground_truth=task.ground_truth,
            )
        )
        artifact.update(
            {
                "task_content_sha256": task_content_sha256(task),
                "localization_fingerprint": _localization_fingerprint(
                    task, language_code, language_name, translation_model, api_provider
                ),
                "translation_model": translation_model,
                "api_provider": api_provider,
                "provider_reported_model_ids": list(
                    dict.fromkeys(
                        getattr(translator, "provider_reported_model_ids", [])
                    )
                ) if language_code != "EN" else [],
                "human_review": {
                    "status": "pending",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "",
                },
                "cache_integrity": "source_hash_verified",
            }
        )
        if force and key in by_key:
            existing_records = [
                artifact
                if (str(record.get("task_id")), str(record.get("language_code"))) == key
                else record
                for record in existing_records
            ]
            write_jsonl_atomic(output_path, existing_records)
            by_key[key] = artifact
        else:
            append_jsonl(output_path, artifact)
            by_key[key] = artifact
            existing_records.append(artifact)
        artifacts.append(artifact)
    if require_human_review:
        unreviewed = [
            (record["task_id"], record["language_code"])
            for record in artifacts
            if (record.get("human_review") or {}).get("status") != "approved"
        ]
        if unreviewed:
            raise ValueError(
                "Generated localizations are pending human review. Review the side-by-side "
                "report and mark the corresponding JSONL rows approved before collection."
            )
    return artifacts


def _markdown_cell(value: Any) -> str:
    text = str(value or "")
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def write_localization_review_report(
    tasks: list[BFCLTask],
    localization_records: list[dict[str, Any]],
    output_path: Path,
    cache_path: Path,
) -> Path:
    record_lookup = {
        (str(record["task_id"]), str(record["language_code"])): record
        for record in localization_records
    }
    lines = [
        "# BFCL Localization Review",
        "",
        f"- Localization cache: `{cache_path}`",
        f"- BFCL commit: `{BFCL_COMMIT}`",
        f"- Task count: `{len(tasks)}`",
        "- Review each proposed translation against the English query and backtranslation.",
        "- After review, set `human_review.status` to `approved`, plus reviewer and date, in the matching JSONL rows.",
        "- This report is a reading aid. The collection command reads the JSONL cache as its source of record.",
        "",
    ]
    for task in tasks:
        task_id = str(task.prompt_entry["id"])
        steps = sum(len(turn) for turn in task.ground_truth)
        lines.extend([f"## {task_id}", "", f"- Category: `{task.category}`", f"- Gold calls: `{steps}`", ""])
        for language_code, language_name in language_pairs(None):
            record = record_lookup.get((task_id, language_code))
            if record is None:
                continue
            review = record.get("human_review") or {}
            lines.extend(
                [
                    f"### {language_code} ({language_name})",
                    "",
                    f"- Automatic invariance check: `{record.get('invariance_pass')}`",
                    f"- Preserved literals: `{record.get('preserved_literals', [])}`",
                    f"- Missing literals: `{record.get('missing_literals', [])}`",
                    f"- Backtranslation similarity: `{float(record.get('backtranslation_similarity', 0.0)):.3f}`",
                    f"- Machine fidelity rating: `{record.get('machine_fidelity_rating')}/5`",
                    f"- Translation model: `{record.get('translation_model', 'unknown')}`",
                    f"- Provider-reported model IDs: `{record.get('provider_reported_model_ids', [])}`",
                    f"- Human review status: `{review.get('status', 'pending')}`",
                    f"- Human reviewer/date: `{review.get('reviewer', '')}` / `{review.get('reviewed_at', '')}`",
                    f"- AI direct-text review: `{record.get('ai_review', {}).get('status', 'pending')}`",
                    f"- AI review audit: `{record.get('ai_review', {}).get('audit_path', '')}`",
                    "",
                    "| Turn | English source | Proposed translation | Backtranslation |",
                    "| --- | --- | --- | --- |",
                ]
            )
            originals = get_original_turn_texts(task)
            localized = record.get("localized_turns", [])
            backtranslated = record.get("backtranslated_turns", [])
            for index, original in enumerate(originals):
                lines.append(
                    f"| {index + 1} | {_markdown_cell(original)} | "
                    f"{_markdown_cell(localized[index] if index < len(localized) else '[MISSING TURN]')} | "
                    f"{_markdown_cell(backtranslated[index] if index < len(backtranslated) else '[MISSING TURN]')} |"
                )
            lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _localized_prompt_entry(task: BFCLTask, localized_turns: list[str]) -> dict[str, Any]:
    prompt_entry = copy.deepcopy(task.prompt_entry)
    for turn_index, turn in enumerate(prompt_entry["question"]):
        for message in turn:
            if message["role"] == "user":
                message["content"] = localized_turns[turn_index]
    return prompt_entry


def build_execution_id(
    task_id: str,
    model_key: str,
    run_label: str,
    language_code: str,
    suffix: str | None = None,
) -> str:
    parts = [
        task_id,
        f"lang{language_code}",
        f"run{run_label}",
        f"model{model_key}",
    ]
    if suffix:
        parts.append(suffix)
    return "_".join(parts)


def _build_replay_prompt(
    replay_case: StepReplayCase,
    localized_turns: list[str],
) -> str:
    prior_context = []
    for idx, (call, result) in enumerate(
        zip(replay_case.prefix_calls, replay_case.prefix_execution_results), start=1
    ):
        prior_context.append(f"{idx}. gold_call={call}\n   execution_result={result}")
    context_block = "\n".join(prior_context) if prior_context else "None."
    return (
        "You are replaying one critical tool-use step from a benchmark task.\n"
        "Previous gold context has already happened correctly.\n"
        "Return only the single next function call needed right now. "
        "Do not explain and do not emit multiple calls.\n\n"
        f"Previous gold context:\n{context_block}\n\n"
        f"Current user request:\n{localized_turns[replay_case.turn_index]}"
    )


def _function_call_to_openai_tool_call(function_call: str) -> tuple[str, str]:
    parsed = parse(function_call, mode="eval")
    if not isinstance(parsed.body, Call):
        raise ValueError(f"Unsupported function-call format: {function_call}")
    if not isinstance(parsed.body.func, Name):
        raise ValueError(f"Unsupported function target: {function_call}")

    arguments: dict[str, Any] = {}
    for argument in parsed.body.keywords:
        if not isinstance(argument, keyword) or argument.arg is None:
            raise ValueError(f"Unsupported function-call keyword: {function_call}")
        arguments[argument.arg] = literal_eval(argument.value)

    return parsed.body.func.id, json.dumps(arguments, ensure_ascii=False)


def _extract_first_candidate_call(handler, model_result: list[list[Any]]) -> str | None:
    if not model_result:
        return None
    for step_response in model_result[0]:
        try:
            decoded = handler.decode_execute(step_response, has_tool_call_tag=False)
        except Exception:
            continue
        if not decoded:
            continue
        return decoded[0]
    return None


def _build_gold_tool_message(call_id: str, function_call: str) -> dict[str, Any]:
    function_name, arguments = _function_call_to_openai_tool_call(function_call)
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": arguments,
                },
            }
        ],
    }


def _build_step_replay_entry(
    task: BFCLTask,
    replay_case: StepReplayCase,
    localized_turns: list[str],
) -> dict[str, Any]:
    current_prompt_entry = copy.deepcopy(task.prompt_entry)
    for turn_index, turn in enumerate(current_prompt_entry["question"]):
        for message in turn:
            if message["role"] == "user":
                message["content"] = localized_turns[turn_index]

    return current_prompt_entry | {"id": replay_case.execution_task_id}


def _run_step_replay_query(
    handler,
    task: BFCLTask,
    replay_case: StepReplayCase,
    localized_turns: list[str],
) -> tuple[list[list[Any]], dict[str, Any]]:
    replay_entry = _build_step_replay_entry(task, replay_case, localized_turns)
    inference_data: dict[str, Any] = {}
    inference_data = handler._pre_query_processing_FC(inference_data, replay_entry)
    inference_data = handler._compile_tools(inference_data, replay_entry)

    prior_calls_index = 0
    for turn_index, turn_messages in enumerate(replay_entry["question"]):
        if turn_index < replay_case.turn_index:
            inference_data = handler.add_first_turn_message_FC(inference_data, turn_messages)
            for gold_call in task.ground_truth[turn_index]:
                call_id = f"gold_{prior_calls_index}"
                model_response_data = {
                    "model_responses_message_for_chat_history": _build_gold_tool_message(
                        call_id, gold_call
                    ),
                    "tool_call_ids": [call_id],
                }
                inference_data = handler._add_assistant_message_FC(
                    inference_data, model_response_data
                )
                inference_data = handler._add_execution_results_FC(
                    inference_data,
                    [replay_case.prefix_execution_results[prior_calls_index]],
                    model_response_data,
                )
                prior_calls_index += 1
            continue

        if turn_index == replay_case.turn_index:
            inference_data = handler.add_first_turn_message_FC(inference_data, turn_messages)
            for _step_idx in range(replay_case.step_index):
                gold_call = task.ground_truth[turn_index][_step_idx]
                call_id = f"gold_{prior_calls_index}"
                model_response_data = {
                    "model_responses_message_for_chat_history": _build_gold_tool_message(
                        call_id, gold_call
                    ),
                    "tool_call_ids": [call_id],
                }
                inference_data = handler._add_assistant_message_FC(
                    inference_data, model_response_data
                )
                inference_data = handler._add_execution_results_FC(
                    inference_data,
                    [replay_case.prefix_execution_results[prior_calls_index]],
                    model_response_data,
                )
                prior_calls_index += 1
            break

    api_response, latency = handler._query_FC(inference_data)
    model_response_data = handler._parse_query_response_FC(api_response)
    return (
        [[model_response_data["model_responses"]]],
        {
            "input_token_count": [[model_response_data["input_token"]]],
            "output_token_count": [[model_response_data["output_token"]]],
            "latency": [[latency]],
        },
    )


def _run_single_step_query(handler, prompt_entry: dict[str, Any]) -> tuple[list[list[Any]], dict[str, Any]]:
    working_entry = copy.deepcopy(prompt_entry)
    inference_data: dict[str, Any] = {}
    inference_data = handler._pre_query_processing_FC(inference_data, working_entry)
    inference_data = handler._compile_tools(inference_data, working_entry)
    inference_data = handler.add_first_turn_message_FC(
        inference_data, working_entry["question"][0]
    )
    api_response, latency = handler._query_FC(inference_data)
    model_response_data = handler._parse_query_response_FC(api_response)
    return (
        [[model_response_data["model_responses"]]],
        {
            "input_token_count": [[model_response_data["input_token"]]],
            "output_token_count": [[model_response_data["output_token"]]],
            "latency": [[latency]],
        },
    )


def run_full_tasks(
    tasks: list[BFCLTask],
    localization_records: list[dict[str, Any]],
    models: list[str],
    run_labels: list[str],
    language_codes: list[str] | None = None,
    task_limit: int | None = None,
    artifact_prefix: str | None = None,
    api_provider: str = "openrouter",
) -> list[dict[str, Any]]:
    loc_index = {
        (record["task_id"], record["language_code"]): record for record in localization_records
    }
    all_records: list[dict[str, Any]] = []
    selected_tasks = tasks[:task_limit] if task_limit is not None else tasks
    selected_languages = language_pairs(language_codes)
    task_hashes = {str(task.prompt_entry["id"]): task_content_sha256(task) for task in selected_tasks}
    for model_key in models:
        for run_label in run_labels:
            seed = seed_from_run_label(run_label)
            handler = build_handler(model_key, temperature=DEFAULT_TEMPERATURE, seed=seed)
            expected_model = _configure_handler_provider(handler, api_provider, model_key)
            for language_code, language_name in selected_languages:
                fingerprint = _evaluation_fingerprint(
                    stage="full",
                    tasks=selected_tasks,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    api_provider=api_provider,
                    localized_queries_sha256=_sha256_json({
                        str(task.prompt_entry['id']): loc_index[(str(task.prompt_entry['id']), language_code)]['localized_turns']
                        for task in selected_tasks
                    }),
                )
                output_path = _artifact_output_path(
                    RUNS_ROOT,
                    f"{model_key}_{language_code}_{run_label}.jsonl",
                    artifact_prefix,
                )
                checkpoint = _load_stage_checkpoint(
                    output_path,
                    stage="full",
                    fingerprint=fingerprint,
                    task_hashes=task_hashes,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    expected_model=expected_model,
                )
                all_records.extend(checkpoint.values())
                for task in selected_tasks:
                    task_id = str(task.prompt_entry["id"])
                    key = (task_id, language_code, model_key, run_label)
                    if key in checkpoint:
                        continue
                    print(
                        f"[full-run] model={model_key} run={run_label} "
                        f"lang={language_code} task={task.prompt_entry['id']}",
                        flush=True,
                    )
                    localization = loc_index[(task_id, language_code)]
                    prompt_entry = _localized_prompt_entry(task, localization["localized_turns"])
                    prompt_entry["id"] = build_execution_id(
                        task.prompt_entry["id"],
                        model_key,
                        run_label,
                        language_code,
                    )
                    if hasattr(handler, "provider_reported_model_ids"):
                        handler.provider_reported_model_ids = []
                    result, metadata = handler.inference(
                        copy.deepcopy(prompt_entry),
                        include_input_log=False,
                        exclude_state_log=False,
                    )
                    evaluation = evaluate_multi_turn_entry(
                        handler=handler,
                        prompt_entry=copy.deepcopy(prompt_entry),
                        ground_truth=task.ground_truth,
                        model_result=result,
                        model_name=model_key,
                        test_category=task.category,
                    )
                    resolved_model_ids = _verify_provider_models(
                        handler, expected_model, model_key
                    )
                    metadata = dict(metadata)
                    metadata["api_provider"] = api_provider
                    metadata["requested_model_name"] = expected_model
                    metadata["provider_reported_model_ids"] = resolved_model_ids
                    record = {
                        "task_id": task_id,
                        "category": task.category,
                        "language_code": language_code,
                        "language_name": language_name,
                        "model_key": model_key,
                        "run_label": run_label,
                        "seed": seed,
                        "success": int(evaluation["valid"]),
                        "task_content_sha256": task_hashes[task_id],
                        "localized_turns_sha256": _sha256_json(localization['localized_turns']),
                        "evaluation_fingerprint": fingerprint,
                        "api_provider": api_provider,
                        "requested_model_name": expected_model,
                        "provider_reported_model_ids": resolved_model_ids,
                        "result": result,
                        "metadata": metadata,
                        "evaluation": evaluation,
                    }
                    append_jsonl(output_path, record)
                    checkpoint[key] = record
                    all_records.append(record)
    return all_records


def run_step_replays(
    tasks: list[BFCLTask],
    localization_records: list[dict[str, Any]],
    models: list[str],
    run_labels: list[str],
    language_codes: list[str] | None = None,
    task_limit: int | None = None,
    artifact_prefix: str | None = None,
    api_provider: str = "openrouter",
) -> list[dict[str, Any]]:
    loc_index = {
        (record["task_id"], record["language_code"]): record for record in localization_records
    }
    all_records: list[dict[str, Any]] = []
    selected_tasks = tasks[:task_limit] if task_limit is not None else tasks
    selected_languages = language_pairs(language_codes)
    task_hashes = {str(task.prompt_entry["id"]): task_content_sha256(task) for task in selected_tasks}
    for model_key in models:
        for run_label in run_labels:
            seed = seed_from_run_label(run_label)
            handler = build_handler(model_key, temperature=DEFAULT_TEMPERATURE, seed=seed)
            expected_model = _configure_handler_provider(handler, api_provider, model_key)
            for language_code, _language_name in selected_languages:
                fingerprint = _evaluation_fingerprint(
                    stage="replay",
                    tasks=selected_tasks,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    api_provider=api_provider,
                    localized_queries_sha256=_sha256_json({
                        str(task.prompt_entry['id']): loc_index[(str(task.prompt_entry['id']), language_code)]['localized_turns']
                        for task in selected_tasks
                    }),
                )
                output_path = _artifact_output_path(
                    REPLAY_ROOT,
                    f"{model_key}_{language_code}_{run_label}.jsonl",
                    artifact_prefix,
                )
                checkpoint = _load_stage_checkpoint(
                    output_path,
                    stage="replay",
                    fingerprint=fingerprint,
                    task_hashes=task_hashes,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    expected_model=expected_model,
                )
                all_records.extend(checkpoint.values())
                for task in selected_tasks:
                    task_id = str(task.prompt_entry["id"])
                    localization = loc_index[(task_id, language_code)]
                    replay_cases = build_step_replay_cases(
                        task,
                        execution_task_id_prefix=build_execution_id(
                            task.prompt_entry["id"],
                            model_key,
                            run_label,
                            language_code,
                            suffix="replay",
                        ),
                    )
                    for replay_case in replay_cases:
                        key = (
                            replay_case.task_id,
                            language_code,
                            model_key,
                            run_label,
                            replay_case.turn_index,
                            replay_case.step_index,
                        )
                        if key in checkpoint:
                            continue
                        print(
                            f"[replay] model={model_key} run={run_label} "
                            f"lang={language_code} task={replay_case.task_id} "
                            f"turn={replay_case.turn_index} step={replay_case.step_index}",
                            flush=True,
                        )
                        if hasattr(handler, "provider_reported_model_ids"):
                            handler.provider_reported_model_ids = []
                        result, metadata = _run_step_replay_query(
                            handler,
                            task,
                            replay_case,
                            localization["localized_turns"],
                        )
                        candidate_call = _extract_first_candidate_call(handler, result)
                        evaluation = evaluate_step_replay(replay_case, candidate_call)
                        resolved_model_ids = _verify_provider_models(
                            handler, expected_model, model_key
                        )
                        metadata = dict(metadata)
                        metadata["api_provider"] = api_provider
                        metadata["requested_model_name"] = expected_model
                        metadata["provider_reported_model_ids"] = resolved_model_ids
                        record = {
                            "task_id": replay_case.task_id,
                            "category": replay_case.category,
                            "language_code": language_code,
                            "model_key": model_key,
                            "run_label": run_label,
                            "seed": seed,
                            "turn_index": replay_case.turn_index,
                            "step_index": replay_case.step_index,
                            "gold_call": replay_case.gold_call,
                            "candidate_call": candidate_call,
                            "valid": int(evaluation["valid"]),
                            "task_content_sha256": task_hashes[replay_case.task_id],
                            "localized_turns_sha256": _sha256_json(localization['localized_turns']),
                            "evaluation_fingerprint": fingerprint,
                            "api_provider": api_provider,
                            "requested_model_name": expected_model,
                            "provider_reported_model_ids": resolved_model_ids,
                            "metadata": metadata,
                            "evaluation": evaluation,
                        }
                        append_jsonl(output_path, record)
                        checkpoint[key] = record
                        all_records.append(record)
    return all_records


def estimate_k(tasks: list[BFCLTask]) -> dict[str, Any]:
    lengths = [sum(len(turn) for turn in task.ground_truth) for task in tasks]
    mean_k = mean(lengths)
    rounded = max(1, round(mean_k))
    return {"mean_k": mean_k, "rounded_k": rounded, "k_range": [max(1, rounded - 1), rounded, rounded + 1]}


def summarize_cf(
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    tasks: list[BFCLTask],
    n_boot: int = 5000,
    bootstrap_seed: int = 0,
    cluster_unit: str = "underlying_task",
) -> dict[str, Any]:
    if n_boot < 1:
        raise ValueError("n_boot must be a positive integer.")
    if cluster_unit not in {"underlying_task", "task_seed"}:
        raise ValueError("cluster_unit must be 'underlying_task' or 'task_seed'.")
    metrics = load_metrics_module()
    task_lookup = {str(task.prompt_entry["id"]): task for task in tasks}
    k_info = estimate_k(tasks)

    task_records = []
    seen_full_keys: set[tuple[str, str, str, str]] = set()
    seen_replay_keys: set[tuple[str, str, str, str, int, int]] = set()
    replay_by_pair: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for replay in replay_records:
        replay_key = (
            str(replay["task_id"]),
            str(replay["language_code"]),
            str(replay["model_key"]),
            str(replay["run_label"]),
            int(replay["turn_index"]),
            int(replay["step_index"]),
        )
        if replay_key in seen_replay_keys:
            raise ValueError(f"Duplicate replay result key: {replay_key}")
        seen_replay_keys.add(replay_key)
        pair_key = replay_key[:4]
        replay_by_pair.setdefault(pair_key, []).append(replay)

    for run_record in full_run_records:
        task_id = str(run_record["task_id"])
        pair_key = (
            task_id,
            str(run_record["language_code"]),
            str(run_record["model_key"]),
            str(run_record["run_label"]),
        )
        if pair_key in seen_full_keys:
            raise ValueError(f"Duplicate full-trajectory result key: {pair_key}")
        seen_full_keys.add(pair_key)
        if task_id not in task_lookup:
            raise ValueError(f"Full-trajectory row references unselected task {task_id}.")
        matching_replays = replay_by_pair.get(pair_key, [])
        matching_replays.sort(key=lambda item: (item["turn_index"], item["step_index"]))
        task = task_lookup[task_id]
        expected_replay_keys = {
            (turn_index, step_index)
            for turn_index, turn in enumerate(task.ground_truth)
            for step_index, _call in enumerate(turn)
        }
        actual_replay_keys = {
            (int(replay["turn_index"]), int(replay["step_index"]))
            for replay in matching_replays
        }
        if actual_replay_keys != expected_replay_keys:
            raise ValueError(
                f"Full/replay pairing is incomplete or inconsistent for {pair_key}: "
                f"expected {sorted(expected_replay_keys)}, got {sorted(actual_replay_keys)}"
            )
        suffix = task_id.rsplit("_", 1)[-1]
        scenario_id = f"scenario_{suffix}" if suffix.isdigit() else task_id
        task_records.append(
            metrics.TaskRecord(
                task_id=f"{task_id}::{run_record['run_label']}",
                language=run_record["language_code"],
                backbone=run_record["model_key"],
                success=run_record["success"],
                step_validity=[replay["valid"] for replay in matching_replays],
                underlying_task_id=scenario_id,
                task_variant_id=task_id,
            )
        )

    orphan_replay_pairs = set(replay_by_pair).difference(seen_full_keys)
    if orphan_replay_pairs:
        raise ValueError(
            f"Replay rows have no paired full trajectory: {sorted(orphan_replay_pairs)[:5]}"
        )

    cluster_counts_by_backbone: dict[str, int] = {}
    for backbone in sorted({record.backbone for record in task_records}):
        if cluster_unit == "task_seed":
            cluster_ids = {record.task_id for record in task_records if record.backbone == backbone}
        else:
            cluster_ids = {
                record.underlying_task_id or record.task_id
                for record in task_records
                if record.backbone == backbone
            }
        cluster_counts_by_backbone[backbone] = len(cluster_ids)
    insufficient_backbones = {
        backbone: count
        for backbone, count in cluster_counts_by_backbone.items()
        if count < 2
    }
    bootstrap_unavailable_reason = None
    if insufficient_backbones:
        bootstrap_unavailable_reason = (
            f"At least two {cluster_unit} clusters are required per model; "
            f"insufficient cluster counts: {insufficient_backbones}"
        )

    summary = {
        "k": k_info,
        "scope": {
            "tasks": len(tasks),
            "task_ids": [task.prompt_entry["id"] for task in tasks],
            "languages": sorted({record["language_code"] for record in full_run_records}),
            "models": sorted({record["model_key"] for record in full_run_records}),
            "run_labels": sorted({record["run_label"] for record in full_run_records}),
            "task_trials": len(full_run_records),
            "replay_trials": len(replay_records),
            "provider_reported_model_ids": {
                model: sorted(
                    {
                        str(model_id)
                        for record in full_run_records
                        if record.get("model_key") == model
                        for model_id in record.get("provider_reported_model_ids", [])
                    }
                )
                for model in sorted({record["model_key"] for record in full_run_records})
            },
        },
        "point_estimates": {},
        "bootstrap": {},
        "bootstrap_config": {
            "n_boot": n_boot,
            "seed": bootstrap_seed,
            "cluster_unit": cluster_unit,
            "cluster_counts_by_backbone": cluster_counts_by_backbone,
            "status": "unavailable" if bootstrap_unavailable_reason else "available",
            "unavailable_reason": bootstrap_unavailable_reason,
            "tail_interpretation": (
                "Bootstrap tail probabilities are uncalibrated directional diagnostics, "
                "not inferential p-values."
            ),
        },
    }
    for k in k_info["k_range"]:
        point = metrics.compute_cf(task_records, K=k, null="common")
        if bootstrap_unavailable_reason:
            def unavailable_cells() -> dict[str, dict[str, Any]]:
                return {
                    f"{lang}::{backbone}": {
                        **values,
                        "Delta_CI": None,
                        "CF_CI": None,
                        "p_raw": None,
                        "p_holm": None,
                        "bootstrap_tail_probability": None,
                        "holm_adjusted_bootstrap_tail_probability": None,
                        "CF_reportable": bool(
                            values["r_ind"] > 0 and abs(log(values["r_ind"])) >= 0.05
                        ),
                        "compounding": None,
                        "inference_status": "unavailable_insufficient_clusters",
                        "compounding_status": "unavailable_insufficient_clusters",
                        "n_boot": n_boot,
                        "seed": bootstrap_seed,
                        "cluster_unit": cluster_unit,
                        "cluster_count": cluster_counts_by_backbone[backbone],
                        "unavailable_reason": bootstrap_unavailable_reason,
                    }
                    for (lang, backbone), values in point.items()
                    if lang.upper() not in {"EN", "ENGLISH"}
                }

            bootstrap = unavailable_cells()
            position_bootstrap = unavailable_cells()
        else:
            bootstrap = metrics.bootstrap_cf(
                task_records,
                K=k,
                null="common",
                n_boot=n_boot,
                seed=bootstrap_seed,
                cluster_unit=cluster_unit,
            )
            position_bootstrap = metrics.bootstrap_cf(
                task_records,
                K=k,
                null="position",
                n_boot=n_boot,
                seed=bootstrap_seed,
                cluster_unit=cluster_unit,
            )
        summary["point_estimates"][str(k)] = {
            f"{lang}::{backbone}": values for (lang, backbone), values in point.items()
        }
        summary["bootstrap"][str(k)] = {
            "common": {f"{lang}::{backbone}": values for (lang, backbone), values in bootstrap.items()}
            if not bootstrap_unavailable_reason
            else bootstrap,
            "position": {f"{lang}::{backbone}": values for (lang, backbone), values in position_bootstrap.items()}
            if not bootstrap_unavailable_reason
            else position_bootstrap,
            "status": "unavailable" if bootstrap_unavailable_reason else "available",
            "unavailable_reason": bootstrap_unavailable_reason,
        }
    return summary


def write_analysis_report(
    cf_summary: dict[str, Any],
    artifact_prefix: str | None = None,
) -> Path:
    lines = [
        "# BFCL Compounding Analysis Report",
        "",
        f"- BFCL commit: `{BFCL_COMMIT}`",
        f"- Tasks in current slice: `{cf_summary['scope']['tasks']}`",
        f"- Task IDs: `{cf_summary['scope']['task_ids']}`",
        f"- Languages: `{cf_summary['scope']['languages']}`",
        f"- Models: `{cf_summary['scope']['models']}`",
        f"- Run labels: `{cf_summary['scope']['run_labels']}`",
        f"- Full-task trials: `{cf_summary['scope']['task_trials']}`",
        f"- Isolated replay trials: `{cf_summary['scope']['replay_trials']}`",
        f"- Bootstrap: `{cf_summary['bootstrap_config']}`",
        f"- Mean K: `{cf_summary['k']['mean_k']:.2f}`",
        f"- Rounded K: `{cf_summary['k']['rounded_k']}`",
        f"- K range checked: `{cf_summary['k']['k_range']}`",
        "",
        "Bootstrap-tail probabilities (raw and Holm-adjusted) are uncalibrated directional diagnostics, not inferential p-values.",
        "",
        "## CF snapshot",
    ]
    rounded_k = str(cf_summary["k"]["rounded_k"])
    for cell, values in sorted(cf_summary["bootstrap"][rounded_k]["common"].items()):
        if values.get("inference_status") == "unavailable_insufficient_clusters":
            lines.append(
                f"- `{cell}`: scenario-level bootstrap unavailable "
                f"({values['cluster_count']} cluster(s)); point estimate T={values['T']:.3f}, "
                f"Delta={values['Delta']:.3f}. Reason: {values['unavailable_reason']}"
            )
        else:
            lines.append(
                f"- `{cell}`: T={values['T']:.3f}, p={values['p']:.3f}, "
                f"CF={values['CF']}, Delta={values['Delta']:.3f}, "
                f"Holm-adjusted bootstrap-tail diagnostic="
                f"{values.get('holm_adjusted_bootstrap_tail_probability', values.get('p_holm'))}"
            )
    output_path = _artifact_output_path(SUMMARY_ROOT, "report.md", artifact_prefix)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def summarize_existing_artifacts(
    tasks: list[BFCLTask],
    model_keys: list[str],
    language_codes: list[str] | None = None,
    run_labels: list[str] | None = None,
    artifact_prefix: str | None = None,
    n_boot: int = 5000,
    bootstrap_seed: int = 0,
    cluster_unit: str = "underlying_task",
    input_artifact_prefix: str | None = None,
) -> dict[str, Any]:
    run_labels = run_labels or DEFAULT_RUN_LABELS
    full_run_records, replay_records = collect_artifact_records(
        model_keys=model_keys,
        run_labels=run_labels,
        language_codes=language_codes,
        artifact_prefix=input_artifact_prefix,
    )
    cf_summary = summarize_cf(
        full_run_records=full_run_records,
        replay_records=replay_records,
        tasks=tasks,
        n_boot=n_boot,
        bootstrap_seed=bootstrap_seed,
        cluster_unit=cluster_unit,
    )
    write_json(_artifact_output_path(SUMMARY_ROOT, "cf_summary.json", artifact_prefix), cf_summary)
    report_path = write_analysis_report(cf_summary, artifact_prefix=artifact_prefix)
    return {
        "full_runs": len(full_run_records),
        "replays": len(replay_records),
        "report": str(report_path),
        "bootstrap_config": cf_summary["bootstrap_config"],
    }


def _load_complete_stage(
    *,
    stage: str,
    tasks: list[BFCLTask],
    model_keys: list[str],
    run_labels: list[str],
    language_codes: list[str] | None,
    artifact_prefix: str | None,
    api_provider: str,
    localization_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    loc_index = {(r['task_id'], r['language_code']): r for r in localization_records or []}
    task_hashes = {str(task.prompt_entry["id"]): task_content_sha256(task) for task in tasks}
    records: list[dict[str, Any]] = []
    selected_languages = language_pairs(language_codes)
    for model_key in model_keys:
        expected_model = str(PILOT_MODELS[model_key]["model_name"])
        for run_label in run_labels:
            for language_code, _language_name in selected_languages:
                fingerprint = _evaluation_fingerprint(
                    stage=stage,
                    tasks=tasks,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    api_provider=api_provider,
                    localized_queries_sha256=_sha256_json({
                        str(task.prompt_entry['id']): loc_index[(str(task.prompt_entry['id']), language_code)]['localized_turns']
                        for task in tasks
                    }) if localization_records is not None else None,
                )
                directory = RUNS_ROOT if stage == "full" else REPLAY_ROOT
                output_path = _artifact_output_path(
                    directory,
                    f"{model_key}_{language_code}_{run_label}.jsonl",
                    artifact_prefix,
                )
                checkpoint = _load_stage_checkpoint(
                    output_path,
                    stage=stage,
                    fingerprint=fingerprint,
                    task_hashes=task_hashes,
                    model_key=model_key,
                    run_label=run_label,
                    language_code=language_code,
                    expected_model=expected_model,
                )
                if stage == "full":
                    expected_keys = {
                        (str(task.prompt_entry["id"]), language_code, model_key, run_label)
                        for task in tasks
                    }
                else:
                    expected_keys = set()
                    for task in tasks:
                        for case in build_step_replay_cases(task):
                            expected_keys.add(
                                (
                                    case.task_id,
                                    language_code,
                                    model_key,
                                    run_label,
                                    case.turn_index,
                                    case.step_index,
                                )
                            )
                missing = expected_keys.difference(checkpoint)
                extra = set(checkpoint).difference(expected_keys)
                if missing or extra:
                    raise ValueError(
                        f"Stage checkpoint {output_path} is incomplete or contains unexpected "
                        f"rows (missing={len(missing)}, extra={len(extra)})."
                    )
                records.extend(checkpoint.values())
    return records


def run_bfcl_evaluation(
    model_keys: list[str],
    run_labels: list[str] | None = None,
    task_limit: int | None = None,
    per_category_limit: int | None = None,
    language_codes: list[str] | None = None,
    artifact_prefix: str | None = None,
    execute_full_runs: bool = True,
    execute_replays: bool = True,
    force_localization: bool = False,
    task_ids: list[str] | None = None,
    localization_prefix: str | None = None,
    api_provider: str = "openrouter",
    localize_only: bool = False,
    require_human_localization_review: bool = False,
    collection_only: bool = False,
    job_label: str | None = None,
    n_boot: int = 5000,
    bootstrap_seed: int = 0,
    cluster_unit: str = "underlying_task",
) -> dict[str, Any]:
    load_env_file(ROOT_ENV_FILE)
    ensure_project_dirs()

    if task_ids is not None and (task_limit is not None or per_category_limit is not None):
        raise ValueError("Use --task-ids alone, without task-limit or per-category-limit.")
    if localize_only and collection_only:
        raise ValueError("--localize-only and --collection-only cannot be used together.")
    if collection_only and force_localization:
        raise ValueError("Collection-only jobs cannot regenerate or rewrite localization rows.")
    if collection_only and not job_label:
        raise ValueError("--collection-only requires a unique --job-label for metadata isolation.")
    if job_label and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", job_label):
        raise ValueError("job_label must be a safe label of up to 64 letters, digits, '_' or '-'.")

    run_labels = run_labels or DEFAULT_RUN_LABELS
    tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    selected_tasks = select_bfcl_tasks(
        tasks,
        task_limit=task_limit,
        per_category_limit=per_category_limit,
        task_ids=task_ids,
    )

    localization_records = localize_tasks(
        selected_tasks,
        language_codes=language_codes,
        force=force_localization,
        cache_prefix=localization_prefix,
        api_provider=api_provider,
        require_human_review=(require_human_localization_review and not localize_only),
        allow_generation=not collection_only,
    )
    localization_cache = _localization_cache_path(localization_prefix)
    review_prefix = localization_prefix or artifact_prefix or "bfcl"
    localization_review_path = SUMMARY_ROOT / f"{review_prefix}_localization_review.md"
    if collection_only:
        if not localization_review_path.exists():
            raise FileNotFoundError(
                "Collection-only mode expects a prior --localize-only review report; "
                f"missing {localization_review_path}."
            )
    else:
        write_localization_review_report(
            selected_tasks,
            localization_records,
            localization_review_path,
            localization_cache,
        )
    if localize_only:
        return {
            "tasks": len(selected_tasks),
            "task_ids": [str(task.prompt_entry["id"]) for task in selected_tasks],
            "localizations": len(localization_records),
            "localization_cache": str(localization_cache),
            "localization_review": str(localization_review_path),
            "localize_only": True,
        }

    if execute_full_runs:
        full_run_records = run_full_tasks(
            tasks=selected_tasks,
            localization_records=localization_records,
            models=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
            artifact_prefix=artifact_prefix,
            api_provider=api_provider,
        )
    else:
        full_run_records = _load_complete_stage(
            stage="full",
            tasks=selected_tasks,
            model_keys=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
            artifact_prefix=artifact_prefix,
            api_provider=api_provider,
            localization_records=localization_records,
        )

    if execute_replays:
        replay_records = run_step_replays(
            tasks=selected_tasks,
            localization_records=localization_records,
            models=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
            artifact_prefix=artifact_prefix,
            api_provider=api_provider,
        )
    else:
        replay_records = _load_complete_stage(
            stage="replay",
            tasks=selected_tasks,
            model_keys=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
            artifact_prefix=artifact_prefix,
            api_provider=api_provider,
            localization_records=localization_records,
        )

    metadata = {
        "bfcl_commit": BFCL_COMMIT,
        "models": model_keys,
        "run_labels": run_labels,
        "task_limit": task_limit,
        "per_category_limit": per_category_limit,
        "task_ids": [str(task.prompt_entry["id"]) for task in selected_tasks],
        "task_set_sha256": task_set_sha256(selected_tasks),
        "language_codes": [code for code, _name in language_pairs(language_codes)],
        "artifact_prefix": artifact_prefix,
        "localization_prefix": localization_prefix,
        "localization_cache": str(localization_cache),
        "localization_review": str(localization_review_path),
        "api_provider": api_provider,
        "requested_models": {
            model_key: str(PILOT_MODELS[model_key]["model_name"]) for model_key in model_keys
        },
        "execute_full_runs": execute_full_runs,
        "execute_replays": execute_replays,
        "collection_only": collection_only,
        "job_label": job_label,
        "n_boot": n_boot,
        "bootstrap_seed": bootstrap_seed,
        "cluster_unit": cluster_unit,
        "cwd": os.getcwd(),
    }
    metadata_name = f"evaluation_metadata_{job_label}.json" if job_label else "evaluation_metadata.json"
    metadata_path = _artifact_output_path(METADATA_ROOT, metadata_name, artifact_prefix)
    write_json(metadata_path, metadata)
    if collection_only:
        return {
            "tasks": len(selected_tasks),
            "task_ids": [str(task.prompt_entry["id"]) for task in selected_tasks],
            "localizations": len(localization_records),
            "full_runs": len(full_run_records),
            "replays": len(replay_records),
            "metadata": str(metadata_path),
            "collection_only": True,
        }

    cf_summary = summarize_cf(
        full_run_records=full_run_records,
        replay_records=replay_records,
        tasks=selected_tasks,
        n_boot=n_boot,
        bootstrap_seed=bootstrap_seed,
        cluster_unit=cluster_unit,
    )
    write_json(_artifact_output_path(SUMMARY_ROOT, "cf_summary.json", artifact_prefix), cf_summary)
    report_path = write_analysis_report(cf_summary, artifact_prefix=artifact_prefix)

    return {
        "tasks": len(selected_tasks),
        "localizations": len(localization_records),
        "full_runs": len(full_run_records),
        "replays": len(replay_records),
        "report": str(report_path),
        "metadata": str(metadata_path),
        "localization_review": str(localization_review_path),
        "bootstrap_config": cf_summary["bootstrap_config"],
    }


# Backward-compatible alias.
run_bfcl_pilot = run_bfcl_evaluation
