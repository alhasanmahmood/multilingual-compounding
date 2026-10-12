"""Validate and summarize the completed, saved BFCL expansion without API calls.

The completion gate checks every selected trajectory and critical-step replay
against the fixed plan, current localization cache, BFCL source, and provider
identity before any offline analysis is launched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.bfcl_vendor import BFCLTask, load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import (  # noqa: E402
    _evaluation_fingerprint,
    _localization_fingerprint,
    _sha256_json,
    _validate_localization_record,
    task_content_sha256,
)
from multilingual_compounding.paths import (  # noqa: E402
    LOCALIZATION_ROOT,
    REPLAY_ROOT,
    RUNS_ROOT,
    SUMMARY_ROOT,
)
from multilingual_compounding.settings import (  # noqa: E402
    BFCL_COMMIT,
    PILOT_MODELS,
    PILOT_TEST_CATEGORIES,
    language_pairs,
)


EXPECTED_TASK_COUNT = 20
EXPECTED_LANGUAGES = ("EN", "AR", "TR", "ZH", "HI", "JA", "ES", "SW")
EXPECTED_MODELS = ("gemini", "claude_sonnet46")
EXPECTED_RUN_LABELS = ("expansion_seed0", "expansion_seed1")
PREFIX_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def _safe_prefix(value: str, label: str) -> str:
    if not PREFIX_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a safe prefix of up to 64 letters, digits, '_' or '-'.")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_manifest_sha256(manifest: list[dict[str, Any]]) -> str:
    """Keep the frozen v1 digest identical on Windows and POSIX checkouts."""
    legacy = [dict(row, path=str(row["path"]).replace("/", "\\")) for row in manifest]
    return _sha256_json(legacy)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read stable JSON file {path}: {exc}") from exc


def _read_jsonl_with_hash(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise
    if data and not data.endswith(b"\n"):
        raise ValueError(f"Artifact has an incomplete trailing JSONL line: {path}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Artifact is not complete UTF-8 JSONL: {path}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"Blank JSONL row at {path}:{line_number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL row at {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"JSONL row is not an object at {path}:{line_number}")
        records.append(record)
    return records, _sha256_bytes(data)


def _category_ordered_ids(plan: dict[str, Any]) -> list[str]:
    try:
        return [
            str(row["task_id"])
            for category in plan["categories"].values()
            for row in category["selected"]
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError("Plan has an invalid categories/selected structure.") from exc


def validate_fixed_plan(plan: dict[str, Any], all_tasks: list[BFCLTask]) -> list[BFCLTask]:
    """Validate the fixed 20-task expansion and return its collection order."""
    ids = _category_ordered_ids(plan)
    expected_categories = set(PILOT_TEST_CATEGORIES)
    if set(plan.get("categories", {})) != expected_categories:
        raise ValueError(f"Plan categories must be exactly {sorted(expected_categories)}.")
    if plan.get("tasks") != EXPECTED_TASK_COUNT or len(ids) != EXPECTED_TASK_COUNT:
        raise ValueError(f"Plan must contain exactly {EXPECTED_TASK_COUNT} selected tasks.")
    if len(set(ids)) != EXPECTED_TASK_COUNT:
        raise ValueError("Plan contains duplicate task IDs.")
    if set(plan.get("task_ids", [])) != set(ids) or len(plan.get("task_ids", [])) != EXPECTED_TASK_COUNT:
        raise ValueError("Plan task_ids do not match the category-selected task IDs.")
    suffixes: list[int] = []
    assigned_category: dict[str, str] = {}
    for category_name, category in plan["categories"].items():
        if len(category.get("selected", [])) != 5:
            raise ValueError(f"Category {category_name} must contribute exactly five tasks.")
        for row in category["selected"]:
            task_id = str(row.get("task_id", ""))
            prefix, separator, suffix = task_id.rpartition("_")
            if not separator or not suffix.isdigit():
                raise ValueError(f"Task ID lacks a numeric scenario suffix: {task_id}")
            if prefix != category_name:
                raise ValueError(f"Task {task_id} is assigned under the wrong category {category_name}.")
            suffixes.append(int(suffix))
            assigned_category[task_id] = category_name
    if len(set(suffixes)) != EXPECTED_TASK_COUNT:
        raise ValueError("The expansion must contain 20 distinct underlying scenario suffixes.")
    if plan.get("unique_scenarios") != EXPECTED_TASK_COUNT:
        raise ValueError("Plan unique_scenarios must equal 20.")
    if tuple(plan.get("languages", [])) != EXPECTED_LANGUAGES:
        raise ValueError(f"Plan languages must be {list(EXPECTED_LANGUAGES)} in the fixed order.")
    if tuple(plan.get("models", {}).keys()) != EXPECTED_MODELS:
        raise ValueError(f"Plan models must be {list(EXPECTED_MODELS)} in the fixed order.")
    if plan.get("provider") != "openrouter":
        raise ValueError("Expansion plan provider must be openrouter.")
    if plan.get("bfcl_commit") != BFCL_COMMIT:
        raise ValueError("Plan BFCL commit does not match the checked-out benchmark source.")

    by_id = {str(task.prompt_entry["id"]): task for task in all_tasks}
    missing = [task_id for task_id in ids if task_id not in by_id]
    if missing:
        raise ValueError(f"Plan contains task IDs missing from the pinned BFCL source: {missing[:5]}")
    selected = [by_id[task_id] for task_id in ids]
    for task in selected:
        task_id = str(task.prompt_entry["id"])
        if task.category != assigned_category[task_id]:
            raise ValueError(f"BFCL category mismatch for {task_id}: {task.category}")

    gold_calls = 0
    observed_horizons: Counter[int] = Counter()
    row_by_id = {
        str(row["task_id"]): row
        for category in plan["categories"].values()
        for row in category["selected"]
    }
    for task in selected:
        task_id = str(task.prompt_entry["id"])
        count = sum(len(turn) for turn in task.ground_truth)
        if not 8 <= count <= 10:
            raise ValueError(f"Selected task {task_id} has an unexpected {count}-call horizon.")
        if row_by_id[task_id].get("gold_calls") != count:
            raise ValueError(f"Plan gold_calls does not match pinned ground truth for {task_id}.")
        gold_calls += count
        observed_horizons[count] += 1
    expected_horizon_distribution = {str(k): observed_horizons[k] for k in sorted(observed_horizons)}
    if plan.get("selected_horizon_distribution") != expected_horizon_distribution:
        raise ValueError("Plan horizon distribution does not match pinned BFCL ground truth.")

    if plan.get("full_trajectories_total_estimate") != EXPECTED_TASK_COUNT * 8 * 2 * 2:
        raise ValueError("Plan full-trajectory estimate is not 640.")
    expected_replays = gold_calls * len(EXPECTED_LANGUAGES) * len(EXPECTED_MODELS) * len(EXPECTED_RUN_LABELS)
    if expected_replays != 5952 or plan.get("replay_requests_total_exact") != expected_replays:
        raise ValueError("Plan replay count does not match 5,952 pinned gold-call positions.")
    for model_key, model_info in plan["models"].items():
        if model_info.get("requested_model_name") != PILOT_MODELS[model_key]["model_name"]:
            raise ValueError(f"Requested model identity in plan does not match settings for {model_key}.")
        if tuple(model_info.get("run_labels", [])) != EXPECTED_RUN_LABELS:
            raise ValueError(f"Model {model_key} must have exactly the two expansion seed labels.")
    return selected


def validate_localization_records(
    plan: dict[str, Any],
    tasks: list[BFCLTask],
    rows: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    expected_keys = {
        (str(task.prompt_entry["id"]), language)
        for task in tasks
        for language in plan["languages"]
    }
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("task_id")), str(row.get("language_code")))
        if key in keyed:
            raise ValueError(f"Duplicate localization key: {key}")
        keyed[key] = row
    missing = expected_keys - set(keyed)
    extra = set(keyed) - expected_keys
    if missing or extra:
        raise ValueError(f"Localization matrix incomplete or orphaned: missing={len(missing)}, extra={len(extra)}")

    task_by_id = {str(task.prompt_entry["id"]): task for task in tasks}
    languages = dict(language_pairs(plan["languages"]))
    source_hashes: dict[str, str] = {}
    translation_models: set[str] = set()
    translation_provider_ids: set[str] = set()
    for (task_id, language), row in keyed.items():
        task = task_by_id[task_id]
        expected_source_hash = task_content_sha256(task)
        if row.get("task_content_sha256") != expected_source_hash:
            raise ValueError(f"Localization source hash mismatch for {task_id}/{language}.")
        if row.get("language_name") != languages[language]:
            raise ValueError(f"Localization language name mismatch for {task_id}/{language}.")
        _validate_localization_record(row, task, language)
        translation_model = str(row.get("translation_model") or "")
        if not translation_model:
            raise ValueError(f"Localization row lacks translation_model for {task_id}/{language}.")
        if row.get("api_provider") != plan["provider"]:
            raise ValueError(f"Localization provider mismatch for {task_id}/{language}.")
        expected_localization_fingerprint = _localization_fingerprint(
            task,
            language,
            languages[language],
            translation_model,
            plan["provider"],
        )
        if row.get("localization_fingerprint") != expected_localization_fingerprint:
            raise ValueError(f"Localization settings fingerprint mismatch for {task_id}/{language}.")
        source_hashes[task_id] = expected_source_hash
        translation_models.add(translation_model)
        translation_provider_ids.update(str(value) for value in row.get("provider_reported_model_ids", []))

        if language != "EN":
            current_turns_hash = _sha256_json(row["localized_turns"])
            human_review = row.get("human_review") or {}
            human_ok = (
                human_review.get("status") == "approved"
                and bool(str(human_review.get("reviewer", "")).strip())
                and bool(str(human_review.get("reviewed_at", "")).strip())
            )
            ai_review = row.get("ai_review") or {}
            if ai_review.get("unresolved_issues"):
                raise ValueError(f"Unresolved AI localization issues remain for {task_id}/{language}.")
            ai_ok = (
                ai_review.get("status") in {"reviewed", "corrected"}
                and ai_review.get("localized_turns_sha256") == current_turns_hash
                and ai_review.get("source_task_sha256") == expected_source_hash
            )
            if not (human_ok or ai_ok):
                raise ValueError(f"Localization review is absent, stale, or unresolved for {task_id}/{language}.")
    if len(translation_models) != 1:
        raise ValueError(f"Localization translation model is inconsistent: {sorted(translation_models)}")
    return keyed, {
        "rows": len(keyed),
        "expected_rows": len(expected_keys),
        "source_hashes_verified": len(keyed),
        "distinct_source_tasks": len(source_hashes),
        "target_turn_hashes": len(keyed),
        "translation_models": sorted(translation_models),
        "translation_provider_reported_model_ids": sorted(translation_provider_ids),
    }


def _full_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("task_id")),
        str(record.get("language_code")),
        str(record.get("model_key")),
        str(record.get("run_label")),
    )


def _replay_key(record: dict[str, Any]) -> tuple[str, str, str, str, int, int]:
    try:
        turn_index = record["turn_index"]
        step_index = record["step_index"]
        if type(turn_index) is not int or type(step_index) is not int:
            raise TypeError("indices must be integers")
        return (
            str(record.get("task_id")),
            str(record.get("language_code")),
            str(record.get("model_key")),
            str(record.get("run_label")),
            turn_index,
            step_index,
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Replay row has invalid turn/step indices: {record}") from exc


def validate_artifact_records(
    plan: dict[str, Any],
    tasks: list[BFCLTask],
    localizations: dict[tuple[str, str], dict[str, Any]],
    full_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify exact row coverage, hashes, provider IDs, and gold-call positions."""
    task_by_id = {str(task.prompt_entry["id"]): task for task in tasks}
    task_ids = list(task_by_id)
    models = list(plan["models"])
    languages = list(plan["languages"])
    labels_by_model = {
        model: list(plan["models"][model]["run_labels"])
        for model in models
    }
    expected_full = {
        (task_id, language, model, label)
        for task_id in task_ids
        for language in languages
        for model in models
        for label in labels_by_model[model]
    }
    expected_gold = {
        (str(task.prompt_entry["id"]), turn_index, step_index): call
        for task in tasks
        for turn_index, turn in enumerate(task.ground_truth)
        for step_index, call in enumerate(turn)
    }
    expected_replay = {
        (task_id, language, model, label, turn_index, step_index)
        for task_id, turn_index, step_index in expected_gold
        for language in languages
        for model in models
        for label in labels_by_model[model]
    }
    full_keys = [_full_key(row) for row in full_records]
    replay_keys = [_replay_key(row) for row in replay_records]
    full_counts = Counter(full_keys)
    replay_counts = Counter(replay_keys)
    duplicate_full = [key for key, count in full_counts.items() if count > 1]
    duplicate_replay = [key for key, count in replay_counts.items() if count > 1]
    if duplicate_full or duplicate_replay:
        raise ValueError(f"Duplicate artifact keys: full={duplicate_full[:3]}, replay={duplicate_replay[:3]}")
    missing_full = expected_full - set(full_keys)
    extra_full = set(full_keys) - expected_full
    missing_replay = expected_replay - set(replay_keys)
    extra_replay = set(replay_keys) - expected_replay
    if missing_full or extra_full or missing_replay or extra_replay:
        raise ValueError(
            "Collection is incomplete or contains orphan rows: "
            f"full missing/extra={len(missing_full)}/{len(extra_full)}, "
            f"replay missing/extra={len(missing_replay)}/{len(extra_replay)}"
        )

    expected_models = {
        model: str(plan["models"][model]["requested_model_name"])
        for model in models
    }
    localized_hashes = {
        key: _sha256_json(row["localized_turns"])
        for key, row in localizations.items()
    }
    query_hash_by_language = {
        language: _sha256_json({
            task_id: localizations[(task_id, language)]["localized_turns"]
            for task_id in task_ids
        })
        for language in languages
    }
    fingerprint_cache: dict[tuple[str, str, str, str, str], str] = {}
    for stage in ("full", "replay"):
        for model in models:
            for label in labels_by_model[model]:
                for language in languages:
                    fingerprint_cache[(stage, model, label, language, plan["provider"])] = _evaluation_fingerprint(
                        stage=stage,
                        tasks=tasks,
                        model_key=model,
                        run_label=label,
                        language_code=language,
                        api_provider=plan["provider"],
                        localized_queries_sha256=query_hash_by_language[language],
                    )

    all_rows = [("full", row) for row in full_records] + [("replay", row) for row in replay_records]
    provider_ids_by_model: dict[str, set[str]] = {model: set() for model in models}
    for stage, row in all_rows:
        task_id = str(row["task_id"])
        task = task_by_id[task_id]
        language = str(row["language_code"])
        model = str(row["model_key"])
        label = str(row["run_label"])
        key = (task_id, language)
        if row.get("category") != task.category:
            raise ValueError(f"Raw artifact category mismatch for {task_id}/{language}/{model}/{label}.")
        if row.get("task_content_sha256") != task_content_sha256(task):
            raise ValueError(f"Raw artifact source hash mismatch for {task_id}/{language}/{model}/{label}.")
        if row.get("localized_turns_sha256") != localized_hashes[key]:
            raise ValueError(f"Raw artifact target hash does not match current cache for {task_id}/{language}/{model}/{label}.")
        if row.get("api_provider") != plan["provider"]:
            raise ValueError(f"Raw artifact provider mismatch for {task_id}/{language}/{model}/{label}.")
        if row.get("requested_model_name") != expected_models[model]:
            raise ValueError(f"Requested model mismatch for {task_id}/{language}/{model}/{label}.")
        model_ids = row.get("provider_reported_model_ids")
        if not isinstance(model_ids, list) or not model_ids:
            raise ValueError(f"Provider-reported model identity is missing for {task_id}/{language}/{model}/{label}.")
        if any(str(model_id).casefold() != expected_models[model].casefold() for model_id in model_ids):
            raise ValueError(f"Provider-reported model identity mismatch for {task_id}/{language}/{model}/{label}: {model_ids}")
        provider_ids_by_model[model].update(str(model_id) for model_id in model_ids)
        expected_fingerprint = fingerprint_cache[(stage, model, label, language, plan["provider"])]
        if row.get("evaluation_fingerprint") != expected_fingerprint:
            raise ValueError(f"Evaluation fingerprint mismatch for {stage} {task_id}/{language}/{model}/{label}.")
        if stage == "full":
            if row.get("success") not in (0, 1, False, True):
                raise ValueError(f"Full trajectory success flag is invalid for {task_id}/{language}/{model}/{label}.")
        else:
            replay_id = _replay_key(row)
            gold_key = (replay_id[0], replay_id[4], replay_id[5])
            if row.get("gold_call") != expected_gold[gold_key]:
                raise ValueError(
                    f"Replay gold call mismatch at {gold_key}: expected {expected_gold[gold_key]!r}, "
                    f"found {row.get('gold_call')!r}"
                )
            if row.get("valid") not in (0, 1, False, True):
                raise ValueError(f"Replay validity flag is invalid for {replay_id}.")

    gold_counts = Counter(sum(len(turn) for turn in task.ground_truth) for task in tasks)
    return {
        "full_trajectories": len(full_records),
        "expected_full_trajectories": len(expected_full),
        "full_duplicates": 0,
        "full_orphans": 0,
        "replays": len(replay_records),
        "expected_replays": len(expected_replay),
        "replay_duplicates": 0,
        "replay_orphans": 0,
        "unique_task_scenarios": len({task_id.rpartition("_")[2] for task_id in task_ids}),
        "gold_call_positions_per_task": {
            str(task.prompt_entry["id"]): sum(len(turn) for turn in task.ground_truth)
            for task in tasks
        },
        "gold_call_horizon_distribution": {str(k): gold_counts[k] for k in sorted(gold_counts)},
        "source_task_hash_matches": len(full_records) + len(replay_records),
        "current_localization_hash_matches": len(full_records) + len(replay_records),
        "provider_reported_model_ids": {
            model: sorted(ids) for model, ids in provider_ids_by_model.items()
        },
    }


def _check_collection_state(prefix: str) -> dict[str, Any] | None:
    state_path = SUMMARY_ROOT / f"{prefix}_collection_status.json"
    if not state_path.exists():
        return None
    state = _read_json(state_path)
    jobs = state.get("jobs", []) if isinstance(state, dict) else []
    unfinished = [job.get("label", "unknown") for job in jobs if job.get("status") != "completed"]
    if state.get("status") != "completed" or unfinished:
        raise ValueError(
            f"Collection is still running or incomplete (status={state.get('status')!r}, "
            f"unfinished_jobs={unfinished[:8]}). Refusing to analyze live data."
        )
    return {
        "status": state.get("status"),
        "jobs": len(jobs),
        "completed_jobs": sum(job.get("status") == "completed" for job in jobs),
        "plan_sha256": state.get("plan_sha256"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
    }


def _expected_artifact_paths(prefix: str, tasks: list[BFCLTask], plan: dict[str, Any]) -> tuple[dict[Path, tuple[str, str, str]], dict[Path, tuple[str, str, str]]]:
    full_paths: dict[Path, tuple[str, str, str]] = {}
    replay_paths: dict[Path, tuple[str, str, str]] = {}
    for model in plan["models"]:
        for language in plan["languages"]:
            for label in plan["models"][model]["run_labels"]:
                name = f"{prefix}_{model}_{language}_{label}.jsonl"
                full_paths[RUNS_ROOT / name] = (model, language, label)
                replay_paths[REPLAY_ROOT / name] = (model, language, label)
    return full_paths, replay_paths


def _load_raw_stage(
    stage_name: str,
    expected_files: dict[Path, tuple[str, str, str]],
    prefix: str,
    expected_rows_per_file: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    directory = RUNS_ROOT if stage_name == "full" else REPLAY_ROOT
    actual_files = set(directory.glob(f"{prefix}_*.jsonl"))
    expected_set = set(expected_files)
    missing = expected_set - actual_files
    extra = actual_files - expected_set
    if missing or extra:
        missing_names = [path.name for path in sorted(missing)[:4]]
        extra_names = [path.name for path in sorted(extra)[:4]]
        raise ValueError(
            f"{stage_name} artifact files incomplete or orphaned: "
            f"missing={len(missing)} {missing_names}, extra={len(extra)} {extra_names}"
        )
    records: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for path, identity in sorted(expected_files.items()):
        rows, digest = _read_jsonl_with_hash(path)
        if len(rows) != expected_rows_per_file:
            raise ValueError(
                f"{stage_name} file {path.name} has {len(rows)} rows, expected {expected_rows_per_file}."
            )
        model, language, label = identity
        for row in rows:
            row_identity = (str(row.get("model_key")), str(row.get("language_code")), str(row.get("run_label")))
            if row_identity != identity:
                raise ValueError(f"Artifact row identity {row_identity} disagrees with file {path.name}.")
        records.extend(rows)
        manifest.append({
            "stage": stage_name,
            "path": path.relative_to(ROOT).as_posix(),
            "rows": len(rows),
            "sha256": digest,
            "model_key": model,
            "language_code": language,
            "run_label": label,
        })
    return records, manifest


def validate_completed_collection(plan_path: Path) -> dict[str, Any]:
    plan_bytes = plan_path.read_bytes()
    plan = _read_json(plan_path)
    prefix = _safe_prefix(str(plan.get("artifact_prefix", "")), "Artifact prefix")
    localization_prefix = _safe_prefix(str(plan.get("localization_prefix", "")), "Localization prefix")
    collection_state = _check_collection_state(prefix)
    if collection_state is not None and collection_state.get("plan_sha256") != _sha256_bytes(plan_bytes):
        raise ValueError("Completed collection status belongs to a different plan hash.")
    all_tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    tasks = validate_fixed_plan(plan, all_tasks)

    cache_path = LOCALIZATION_ROOT / f"{localization_prefix}_bfcl_multiturn_localizations.jsonl"
    localization_rows, localization_sha256 = _read_jsonl_with_hash(cache_path)
    localizations, localization_validation = validate_localization_records(plan, tasks, localization_rows)

    full_paths, replay_paths = _expected_artifact_paths(prefix, tasks, plan)
    expected_replays_per_file = sum(sum(len(turn) for turn in task.ground_truth) for task in tasks)
    full_records, full_manifest = _load_raw_stage("full", full_paths, prefix, len(tasks))
    replay_records, replay_manifest = _load_raw_stage("replay", replay_paths, prefix, expected_replays_per_file)
    record_validation = validate_artifact_records(plan, tasks, localizations, full_records, replay_records)
    file_manifest = full_manifest + replay_manifest
    provenance = {
        "plan_path": plan_path.relative_to(ROOT).as_posix() if plan_path.is_relative_to(ROOT) else "<external-plan>",
        "plan_sha256": _sha256_bytes(plan_bytes),
        "bfcl_commit": BFCL_COMMIT,
        "artifact_prefix": prefix,
        "localization_prefix": localization_prefix,
        "localization_cache_path": cache_path.relative_to(ROOT).as_posix(),
        "localization_cache_sha256": localization_sha256,
        "collection_state": collection_state,
        "api_provider": plan["provider"],
        "requested_model_names": {
            model: info["requested_model_name"] for model, info in plan["models"].items()
        },
        "localization_translation_models": localization_validation["translation_models"],
        "localization_provider_reported_model_ids": localization_validation["translation_provider_reported_model_ids"],
        "raw_file_count": len(file_manifest),
        "raw_file_manifest_sha256": _raw_manifest_sha256(file_manifest),
        "raw_file_manifest_hash_format": "v1: relative paths normalized to Windows separators for the legacy digest",
        "raw_files": file_manifest,
    }
    return {
        "status": "complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "tasks": len(tasks),
            "unique_scenarios": record_validation["unique_task_scenarios"],
            "categories": len(plan["categories"]),
            "tasks_per_category": {category: len(data["selected"]) for category, data in plan["categories"].items()},
            "languages": list(plan["languages"]),
            "models": list(plan["models"]),
            "run_labels": sorted({label for item in plan["models"].values() for label in item["run_labels"]}),
            "localization_rows": localization_validation["rows"],
            "gold_call_positions": sum(record_validation["gold_call_positions_per_task"].values()),
            "full_trajectories": record_validation["full_trajectories"],
            "replays": record_validation["replays"],
        },
        "validation": {
            "localizations": localization_validation,
            "artifacts": record_validation,
            "all_expected_keys_present": True,
            "duplicate_keys": 0,
            "orphan_keys": 0,
            "provider_identities_match": True,
            "source_and_target_hashes_match": True,
            "gold_call_positions_match": True,
        },
        "provenance": provenance,
    }


def _output_paths(output_prefix: str) -> dict[str, Path]:
    _safe_prefix(output_prefix, "Output prefix")
    return {
        "cf_summary": SUMMARY_ROOT / f"{output_prefix}_cf_summary.json",
        "cf_report": SUMMARY_ROOT / f"{output_prefix}_report.md",
        "decomposition_summary": SUMMARY_ROOT / f"{output_prefix}_decomposition_summary.json",
        "decomposition_report": SUMMARY_ROOT / f"{output_prefix}_decomposition_report.md",
        "robustness_summary": SUMMARY_ROOT / f"{output_prefix}_robustness_summary.json",
        "robustness_report": SUMMARY_ROOT / f"{output_prefix}_robustness_report.md",
        "sensitivity_summary": SUMMARY_ROOT / f"{output_prefix}_task_sensitivity_summary.json",
        "sensitivity_report": SUMMARY_ROOT / f"{output_prefix}_task_sensitivity_report.md",
        "audit": SUMMARY_ROOT / f"{output_prefix}_collection_audit.json",
        "overview": SUMMARY_ROOT / f"{output_prefix}_overview.md",
    }


def _analysis_commands(plan_path: Path, output_prefix: str, n_boot: int, bootstrap_seed: int) -> list[list[str]]:
    plan = _read_json(plan_path)
    task_ids = _category_ordered_ids(plan)
    models = list(plan["models"])
    labels = [EXPECTED_RUN_LABELS[0], EXPECTED_RUN_LABELS[1]]
    languages = list(plan["languages"])
    common = [
        "--models", *models,
        "--task-ids", *task_ids,
        "--run-labels", *labels,
        "--language-codes", *languages,
    ]
    input_prefix = str(plan["artifact_prefix"])
    cmds = [
        [sys.executable, str(ROOT / "scripts/run_compounding_analysis.py"), *common,
         "--artifact-prefix", output_prefix, "--input-artifact-prefix", input_prefix,
         "--n-boot", str(n_boot), "--bootstrap-seed", str(bootstrap_seed),
         "--cluster-unit", "underlying_task"],
        [sys.executable, str(ROOT / "scripts/run_decomposition_analysis.py"), *common,
         "--artifact-prefix", f"{output_prefix}_decomposition", "--input-artifact-prefix", input_prefix],
        [sys.executable, str(ROOT / "scripts/run_robustness_analysis.py"), *common,
         "--artifact-prefix", f"{output_prefix}_robustness", "--input-artifact-prefix", input_prefix,
         "--localization-prefix", str(plan["localization_prefix"]), "--localization-policy", "reviewed",
         "--n-boot", str(n_boot),
         "--bootstrap-seed", str(bootstrap_seed), "--cluster-unit", "underlying_task"],
        [sys.executable, str(ROOT / "scripts/run_task_sensitivity.py"), *common,
         "--input-artifact-prefix", input_prefix, "--main-summary-path",
         str(SUMMARY_ROOT / f"{output_prefix}_cf_summary.json"),
         "--summary-path", str(SUMMARY_ROOT / f"{output_prefix}_task_sensitivity_summary.json"),
         "--report-path", str(SUMMARY_ROOT / f"{output_prefix}_task_sensitivity_report.md"),
         "--n-boot", str(n_boot), "--bootstrap-seed", str(bootstrap_seed),
         "--k-values", "8", "9", "10"],
    ]
    return cmds


def _require_new_outputs(paths: dict[str, Path]) -> None:
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite prior analysis artifacts. Choose another --output-prefix. "
            f"Existing files: {existing}"
        )


def _load_analysis_json(path: Path) -> dict[str, Any]:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Analysis summary is not a JSON object: {path}")
    return data


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def build_overview(
    audit: dict[str, Any],
    output_prefix: str,
    paths: dict[str, Path],
    commands: list[list[str]],
) -> str:
    cf = _load_analysis_json(paths["cf_summary"])
    decomposition = _load_analysis_json(paths["decomposition_summary"])
    robustness = _load_analysis_json(paths["robustness_summary"])
    sensitivity = _load_analysis_json(paths["sensitivity_summary"])
    expected_scope = audit["counts"]
    for name, data in (("CF", cf), ("decomposition", decomposition), ("task sensitivity", sensitivity)):
        scope = data.get("scope", {})
        full_count = scope.get("task_trials", scope.get("full_runs"))
        replay_count = scope.get("replay_trials", scope.get("replays"))
        if scope.get("tasks") != expected_scope["tasks"] or full_count != expected_scope["full_trajectories"] or replay_count != expected_scope["replays"]:
            raise ValueError(f"{name} summary scope does not match the validated expansion artifacts.")
    robustness_scope = robustness.get("scope", {})
    if (
        not isinstance(robustness_scope.get("full_runs"), int)
        or not isinstance(robustness_scope.get("replays"), int)
        or not 0 <= robustness_scope["full_runs"] <= expected_scope["full_trajectories"]
        or not 0 <= robustness_scope["replays"] <= expected_scope["replays"]
        or not set(robustness_scope.get("models", [])) <= set(expected_scope["models"])
        or not set(robustness_scope.get("run_labels", [])) <= set(expected_scope["run_labels"])
    ):
        raise ValueError("Robustness filtered scope is invalid or exceeds the validated collection.")

    selected_k = str(cf["k"]["rounded_k"])
    point_rows = cf["point_estimates"][selected_k]
    bootstrap_rows = cf["bootstrap"][selected_k]["common"]
    non_english_cells = sorted(cell for cell in point_rows if not cell.startswith("EN::"))
    lines = [
        "# Completed BFCL Expansion Overview",
        "",
        "This report summarizes saved model outputs only. It makes no new model or translation API calls.",
        "",
        f"- Collection status: `{audit['status']}`",
        f"- Selected BFCL tasks: `{expected_scope['tasks']}` across `{expected_scope['unique_scenarios']}` unique numeric scenario IDs",
        f"- Categories: `{expected_scope['categories']}`; tasks per category: `{expected_scope['tasks_per_category']}`",
        f"- Critical gold-call positions per task: `{audit['validation']['artifacts']['gold_call_positions_per_task']}`",
        f"- Total gold-call positions: `{expected_scope['gold_call_positions']}`",
        f"- Full trajectories and isolated replays: `{expected_scope['full_trajectories']}` and `{expected_scope['replays']}`",
        f"- Languages: `{', '.join(expected_scope['languages'])}`; models: `{', '.join(expected_scope['models'])}`; run labels: `{', '.join(expected_scope['run_labels'])}`",
        f"- Localization rows checked: `{expected_scope['localization_rows']}`",
        f"- Provider-reported evaluation model IDs: `{audit['validation']['artifacts']['provider_reported_model_ids']}`",
        f"- Raw artifact manifest SHA-256: `{audit['provenance']['raw_file_manifest_sha256']}`",
        f"- Plan SHA-256: `{audit['provenance']['plan_sha256']}`; localization cache SHA-256: `{audit['provenance']['localization_cache_sha256']}`",
        f"- CF point-estimate snapshot uses K=`{selected_k}` (mean horizon `{cf['k']['mean_k']:.2f}`); bootstrap unit is `{cf['bootstrap_config']['cluster_unit']}` with `{cf['bootstrap_config']['n_boot']}` resamples.",
        "- Bootstrap tail values are uncalibrated directional diagnostics, not inferential p-values.",
        "- The plan assigns one unique scenario per category-specific task; category and scenario are not independently crossed, so category contrasts remain descriptive and confounded by scenario assignment.",
        "",
        "## New compounding point estimates",
        "",
        "| Language | Model | T | Delta | r_ind | CF | CF reportable | CF 95% CI | Delta 95% CI |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for cell in non_english_cells:
        values = point_rows[cell]
        boot = bootstrap_rows.get(cell, {})
        lang, model = cell.split("::", 1)
        cf_value = _finite_or_none(values.get("CF"))
        cf_text = f"{cf_value:.4f}" if cf_value is not None else "not reportable"
        interval_cf = boot.get("CF_CI")
        interval_delta = boot.get("Delta_CI")
        ci_cf = "unavailable" if not interval_cf else f"[{interval_cf[0]:.4f}, {interval_cf[1]:.4f}]"
        ci_delta = "unavailable" if not interval_delta else f"[{interval_delta[0]:.4f}, {interval_delta[1]:.4f}]"
        rind = float(values["r_ind"])
        reportable = boot.get("CF_reportable", rind > 0 and abs(math.log(rind)) >= 0.05)
        lines.append(
            f"| {lang} | {model} | {float(values['T']):.4f} | {float(values['Delta']):.4f} | "
            f"{float(values['r_ind']):.4f} | {cf_text} | {reportable} | {ci_cf} | {ci_delta} |"
        )

    lines.extend(["", "## Leave-one-task-variant-out stability", ""])
    for k in sorted(sensitivity.get("leave_one_task_variant_out", {}), key=int):
        cells = sensitivity["leave_one_task_variant_out"][k]["common"]["cells"]
        non_en = {key: value for key, value in cells.items() if not key.startswith("EN::")}
        sign_changes = [key for key, value in non_en.items() if value["Delta_sign_instability_vs_full"]]
        cf_changes = [key for key, value in non_en.items() if value["CF_reportability_instability_vs_full"]]
        lines.append(
            f"- K={k}: Delta sign changed after at least one task omission in `{len(sign_changes)}/{len(non_en)}` non-English model/language cells; CF reportability changed in `{len(cf_changes)}/{len(non_en)}` cells."
        )
    lines.extend([
        "",
        "These are influence diagnostics over the selected 20 task variants. They do not estimate a category effect.",
        "",
        "## Offline analyses",
        "",
        f"- CF summary/report: `{paths['cf_summary'].relative_to(ROOT)}`, `{paths['cf_report'].relative_to(ROOT)}`",
        f"- Decomposition summary/report: `{paths['decomposition_summary'].relative_to(ROOT)}`, `{paths['decomposition_report'].relative_to(ROOT)}`",
        f"- Robustness summary/report: `{paths['robustness_summary'].relative_to(ROOT)}`, `{paths['robustness_report'].relative_to(ROOT)}`",
        f"- Task-sensitivity summary/report: `{paths['sensitivity_summary'].relative_to(ROOT)}`, `{paths['sensitivity_report'].relative_to(ROOT)}`",
        f"- Localization-robustness filtered scope: `{robustness_scope['full_runs']}` full trajectories and `{robustness_scope['replays']}` replays across `{robustness_scope.get('languages', [])}`.",
        "",
        "Reproduction commands used:",
        "",
        "```powershell",
    ])
    lines.extend(_portable_command(command) for command in commands)
    lines.extend(["```", ""])
    return "\n".join(lines)


def _portable_command(command: list[str]) -> str:
    """Display a runnable repository-root command without workstation paths."""
    values = ["python"]
    for value in command[1:]:
        candidate = Path(value)
        values.append(candidate.relative_to(ROOT).as_posix() if candidate.is_absolute() and candidate.is_relative_to(ROOT) else value)
    return " ".join(_quote_arg(value) for value in values)


def _quote_arg(value: str) -> str:
    if not value or re.search(r"[\s&()\[\]{}]", value):
        return "'" + value.replace("'", "''") + "'"
    return value


def run_offline_analyses(
    audit: dict[str, Any],
    plan_path: Path,
    output_prefix: str,
    n_boot: int,
    bootstrap_seed: int,
) -> tuple[dict[str, Path], list[list[str]], str]:
    paths = _output_paths(output_prefix)
    _require_new_outputs(paths)
    commands = _analysis_commands(plan_path, output_prefix, n_boot, bootstrap_seed)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    for command in commands:
        print("Running offline analysis: " + " ".join(_quote_arg(arg) for arg in command), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    overview = build_overview(audit, output_prefix, paths, commands)
    paths["audit"].write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["overview"].write_text(overview, encoding="utf-8")
    return paths, commands, overview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "analysis/bfcl/newstudy20261010_plan.json")
    parser.add_argument("--output-prefix", default="newstudy20261010_expansion")
    parser.add_argument("--n-boot", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument(
        "--run-analyses",
        action="store_true",
        help="After the integrity gate passes, run the four offline summary CLIs and write audit/overview files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.n_boot < 1:
        raise SystemExit("--n-boot must be positive")
    _safe_prefix(args.output_prefix, "Output prefix")
    audit = validate_completed_collection(args.plan)
    print(json.dumps({"status": audit["status"], "counts": audit["counts"], "provenance": {
        key: value for key, value in audit["provenance"].items() if key != "raw_files"
    }}, ensure_ascii=False, indent=2), flush=True)
    if args.run_analyses:
        paths, _commands, _overview = run_offline_analyses(
            audit,
            args.plan,
            args.output_prefix,
            args.n_boot,
            args.bootstrap_seed,
        )
        print(json.dumps({"audit": str(paths["audit"]), "overview": str(paths["overview"])}, indent=2))


if __name__ == "__main__":
    main()
