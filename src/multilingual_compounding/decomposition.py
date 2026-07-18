from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any

from .bfcl_vendor import BFCLTask

ENGLISH_LANGUAGE_CODE = "EN"


@dataclass(frozen=True)
class TaskStepReference:
    flat_index: int
    turn_index: int
    step_index: int
    gold_call: str


@dataclass(frozen=True)
class TaskReference:
    task_id: str
    steps: tuple[TaskStepReference, ...]
    all_function_names: frozenset[str]

    def gold_step(self, flat_index: int) -> TaskStepReference | None:
        if 0 <= flat_index < len(self.steps):
            return self.steps[flat_index]
        return None

    def prefix_function_names(self, flat_index: int) -> set[str]:
        return {
            _parse_function_call(step.gold_call)[0]
            for step in self.steps[:flat_index]
            if _parse_function_call(step.gold_call)[0] is not None
        }

    def future_function_names(self, flat_index: int) -> set[str]:
        return {
            _parse_function_call(step.gold_call)[0]
            for step in self.steps[flat_index + 1 :]
            if _parse_function_call(step.gold_call)[0] is not None
        }


def _parse_function_call(call_text: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if not call_text:
        return None, None
    try:
        parsed = ast.parse(call_text, mode="eval")
        call_node = parsed.body
        if not isinstance(call_node, ast.Call) or not isinstance(call_node.func, ast.Name):
            return None, None
        arguments: dict[str, Any] = {}
        for keyword in call_node.keywords:
            if keyword.arg is None:
                return None, None
            arguments[keyword.arg] = ast.literal_eval(keyword.value)
        return call_node.func.id, arguments
    except Exception:
        return None, None


def _normalize_function_call(call_text: str | None) -> str | None:
    function_name, arguments = _parse_function_call(call_text)
    if function_name is None or arguments is None:
        return call_text
    serialized_args = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{function_name}({serialized_args})"


def build_task_reference(task: BFCLTask) -> TaskReference:
    flat_steps: list[TaskStepReference] = []
    function_names: set[str] = set()
    flat_index = 0
    for turn_index, gold_turn in enumerate(task.ground_truth):
        for step_index, gold_call in enumerate(gold_turn):
            flat_steps.append(
                TaskStepReference(
                    flat_index=flat_index,
                    turn_index=turn_index,
                    step_index=step_index,
                    gold_call=gold_call,
                )
            )
            function_name, _arguments = _parse_function_call(gold_call)
            if function_name is not None:
                function_names.add(function_name)
            flat_index += 1
    return TaskReference(
        task_id=task.prompt_entry["id"],
        steps=tuple(flat_steps),
        all_function_names=frozenset(function_names),
    )


def build_task_reference_map(tasks: list[BFCLTask]) -> dict[str, TaskReference]:
    return {task.prompt_entry["id"]: build_task_reference(task) for task in tasks}


def _classify_stage(
    *,
    gold_call: str | None,
    candidate_call: str | None,
    task_reference: TaskReference,
    gold_flat_index: int,
    error_type: str | None,
) -> tuple[str, str]:
    gold_name, gold_args = _parse_function_call(gold_call)
    candidate_name, candidate_args = _parse_function_call(candidate_call)

    if not candidate_call or error_type == "replay:no_call" or candidate_name is None:
        return "intent_selection", "no_call"

    if gold_name is None:
        return "intent_selection", "unknown_gold_call"

    if candidate_name == gold_name:
        if candidate_args == gold_args and error_type == "multi_turn:instance_state_mismatch":
            return "sequencing_planning", "wrong_context"
        if candidate_args == gold_args:
            return "argument_parameter", "unexpected_same_call_mismatch"
        return "argument_parameter", "wrong_arguments"

    if (
        candidate_name in task_reference.prefix_function_names(gold_flat_index)
        or candidate_name in task_reference.future_function_names(gold_flat_index)
    ):
        return "sequencing_planning", "wrong_order_or_context"

    if error_type == "multi_turn:instance_state_mismatch":
        return "sequencing_planning", "wrong_order_or_context"

    return "intent_selection", "wrong_function"


def _flatten_decoded_result(decoded_result: Any) -> list[dict[str, Any]]:
    flat_calls: list[dict[str, Any]] = []
    if not isinstance(decoded_result, list):
        return flat_calls
    for turn_index, turn in enumerate(decoded_result):
        if not isinstance(turn, list):
            continue
        for emitted_index, emitted_step in enumerate(turn):
            if not isinstance(emitted_step, list):
                continue
            for call_text in emitted_step:
                if isinstance(call_text, str):
                    flat_calls.append(
                        {
                            "turn_index": turn_index,
                            "emitted_index": emitted_index,
                            "call": call_text,
                            "normalized_call": _normalize_function_call(call_text),
                        }
                    )
    return flat_calls


def _align_actual_trace(
    task_reference: TaskReference,
    decoded_result: Any,
) -> dict[str, Any]:
    actual_calls = _flatten_decoded_result(decoded_result)
    gold_index = 0
    detours: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    normalized_gold = [_normalize_function_call(step.gold_call) for step in task_reference.steps]
    for actual_index, actual_call in enumerate(actual_calls):
        current_gold = task_reference.gold_step(gold_index)
        expected_normalized = normalized_gold[gold_index] if gold_index < len(normalized_gold) else None
        if current_gold is not None and actual_call["normalized_call"] == expected_normalized:
            matches.append(
                {
                    "actual_index": actual_index,
                    "gold_flat_index": gold_index,
                    "call": actual_call["call"],
                    "gold_call": current_gold.gold_call,
                }
            )
            gold_index += 1
            continue

        stage, failure_type = _classify_stage(
            gold_call=current_gold.gold_call if current_gold is not None else None,
            candidate_call=actual_call["call"],
            task_reference=task_reference,
            gold_flat_index=min(gold_index, max(len(task_reference.steps) - 1, 0)),
            error_type="multi_turn:off_reference_trace",
        )
        detours.append(
            {
                "actual_index": actual_index,
                "gold_flat_index": gold_index,
                "call": actual_call["call"],
                "gold_call": current_gold.gold_call if current_gold is not None else None,
                "stage": stage,
                "failure_type": failure_type,
            }
        )

    return {
        "actual_calls": actual_calls,
        "matched_calls": matches,
        "detours": detours,
        "completed_gold_steps": gold_index,
        "fully_aligned": gold_index == len(task_reference.steps),
    }


def _build_replay_summary(
    replay_records: list[dict[str, Any]],
    task_reference_map: dict[str, TaskReference],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    by_trial: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in replay_records:
        trial_key = (
            record["task_id"],
            record["language_code"],
            record["model_key"],
            record["run_label"],
        )
        by_trial[trial_key].append(record)

    summaries: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for trial_key, records in by_trial.items():
        records.sort(key=lambda item: (item["turn_index"], item["step_index"]))
        task_reference = task_reference_map[trial_key[0]]
        stage_counts: Counter[str] = Counter()
        failure_type_counts: Counter[str] = Counter()
        invalid_records = []
        for flat_index, record in enumerate(records):
            if record["valid"]:
                continue
            stage, failure_type = _classify_stage(
                gold_call=record["gold_call"],
                candidate_call=record.get("candidate_call"),
                task_reference=task_reference,
                gold_flat_index=flat_index,
                error_type=record["evaluation"].get("error_type"),
            )
            invalid_records.append(
                {
                    "flat_index": flat_index,
                    "turn_index": record["turn_index"],
                    "step_index": record["step_index"],
                    "gold_call": record["gold_call"],
                    "candidate_call": record.get("candidate_call"),
                    "stage": stage,
                    "failure_type": failure_type,
                    "error_type": record["evaluation"].get("error_type"),
                }
            )
            stage_counts[stage] += 1
            failure_type_counts[failure_type] += 1

        valid_count = sum(record["valid"] for record in records)
        summaries[trial_key] = {
            "task_id": trial_key[0],
            "language_code": trial_key[1],
            "model_key": trial_key[2],
            "run_label": trial_key[3],
            "replay_total_steps": len(records),
            "replay_valid_steps": valid_count,
            "replay_validity_rate": valid_count / len(records) if records else 0.0,
            "first_invalid_flat_index": invalid_records[0]["flat_index"] if invalid_records else None,
            "invalid_records": invalid_records,
            "stage_counts": dict(stage_counts),
            "failure_type_counts": dict(failure_type_counts),
        }
    return summaries


def _build_trajectory_rows(
    full_run_records: list[dict[str, Any]],
    replay_summary: dict[tuple[str, str, str, str], dict[str, Any]],
    task_reference_map: dict[str, TaskReference],
) -> list[dict[str, Any]]:
    trajectory_rows: list[dict[str, Any]] = []
    for run_record in full_run_records:
        task_reference = task_reference_map[run_record["task_id"]]
        alignment = _align_actual_trace(task_reference, run_record["evaluation"].get("decoded_result"))
        trial_key = (
            run_record["task_id"],
            run_record["language_code"],
            run_record["model_key"],
            run_record["run_label"],
        )
        replay_info = replay_summary.get(trial_key, {})
        has_detour = bool(alignment["detours"])
        trajectory_rows.append(
            {
                "task_id": run_record["task_id"],
                "language_code": run_record["language_code"],
                "model_key": run_record["model_key"],
                "run_label": run_record["run_label"],
                "seed": run_record.get("seed"),
                "success": run_record["success"],
                "has_detour": has_detour,
                "detour_count": len(alignment["detours"]),
                "first_detour_stage": alignment["detours"][0]["stage"] if has_detour else None,
                "first_detour_failure_type": (
                    alignment["detours"][0]["failure_type"] if has_detour else None
                ),
                "first_detour_gold_flat_index": (
                    alignment["detours"][0]["gold_flat_index"] if has_detour else None
                ),
                "recovered": int(has_detour and run_record["success"] == 1),
                "propagated_to_failure": int(has_detour and run_record["success"] == 0),
                "replay_validity_rate": replay_info.get("replay_validity_rate"),
                "replay_valid_steps": replay_info.get("replay_valid_steps"),
                "replay_total_steps": replay_info.get("replay_total_steps"),
                "first_invalid_flat_index": replay_info.get("first_invalid_flat_index"),
            }
        )
    return trajectory_rows


def _share(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values())
    if total == 0:
        return {}
    return {key: value / total for key, value in counter.items()}


def _aggregate_stage_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stage_counter: Counter[str] = Counter()
    failure_counter: Counter[str] = Counter()
    invalid_step_total = 0
    for row in rows:
        invalid_records = row.get("invalid_records", [])
        invalid_step_total += len(invalid_records)
        for invalid_record in invalid_records:
            stage_counter[invalid_record["stage"]] += 1
            failure_counter[invalid_record["failure_type"]] += 1
    return {
        "invalid_step_total": invalid_step_total,
        "stage_counts": dict(stage_counter),
        "stage_shares": _share(stage_counter),
        "failure_type_counts": dict(failure_counter),
        "failure_type_shares": _share(failure_counter),
    }


def _aggregate_trajectory_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    detour_rows = [row for row in rows if row["has_detour"]]
    if not detour_rows:
        return {
            "runs": len(rows),
            "runs_with_detour": 0,
            "propagation_rate": None,
            "recovery_rate": None,
            "mean_replay_validity": None,
        }
    return {
        "runs": len(rows),
        "runs_with_detour": len(detour_rows),
        "propagation_rate": sum(row["propagated_to_failure"] for row in detour_rows)
        / len(detour_rows),
        "recovery_rate": sum(row["recovered"] for row in detour_rows) / len(detour_rows),
        "mean_replay_validity": mean(
            row["replay_validity_rate"] for row in detour_rows if row["replay_validity_rate"] is not None
        ),
    }


def _matched_trajectory_rates(
    english_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    english_detours = [row for row in english_rows if row["has_detour"]]
    comparison_detours = [row for row in comparison_rows if row["has_detour"]]
    english_bins: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    comparison_bins: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)

    for row in english_detours:
        if row["replay_valid_steps"] is None or row["replay_total_steps"] is None:
            continue
        english_bins[(row["replay_valid_steps"], row["replay_total_steps"])].append(row)
    for row in comparison_detours:
        if row["replay_valid_steps"] is None or row["replay_total_steps"] is None:
            continue
        comparison_bins[(row["replay_valid_steps"], row["replay_total_steps"])].append(row)

    shared_bins = sorted(set(english_bins) & set(comparison_bins))
    if not shared_bins:
        return {
            "shared_validity_bins": [],
            "weighted_pairs": 0,
            "english_propagation_rate": None,
            "comparison_propagation_rate": None,
            "english_recovery_rate": None,
            "comparison_recovery_rate": None,
        }

    english_prop_total = 0.0
    comparison_prop_total = 0.0
    english_recovery_total = 0.0
    comparison_recovery_total = 0.0
    total_weight = 0
    for validity_bin in shared_bins:
        english_group = english_bins[validity_bin]
        comparison_group = comparison_bins[validity_bin]
        weight = min(len(english_group), len(comparison_group))
        if weight == 0:
            continue
        total_weight += weight
        english_prop_total += weight * (
            sum(row["propagated_to_failure"] for row in english_group) / len(english_group)
        )
        comparison_prop_total += weight * (
            sum(row["propagated_to_failure"] for row in comparison_group) / len(comparison_group)
        )
        english_recovery_total += weight * (
            sum(row["recovered"] for row in english_group) / len(english_group)
        )
        comparison_recovery_total += weight * (
            sum(row["recovered"] for row in comparison_group) / len(comparison_group)
        )

    if total_weight == 0:
        return {
            "shared_validity_bins": shared_bins,
            "weighted_pairs": 0,
            "english_propagation_rate": None,
            "comparison_propagation_rate": None,
            "english_recovery_rate": None,
            "comparison_recovery_rate": None,
        }

    return {
        "shared_validity_bins": [list(item) for item in shared_bins],
        "weighted_pairs": total_weight,
        "english_propagation_rate": english_prop_total / total_weight,
        "comparison_propagation_rate": comparison_prop_total / total_weight,
        "english_recovery_rate": english_recovery_total / total_weight,
        "comparison_recovery_rate": comparison_recovery_total / total_weight,
    }


def summarize_decomposition(
    *,
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    tasks: list[BFCLTask],
) -> dict[str, Any]:
    task_reference_map = build_task_reference_map(tasks)
    replay_summary = _build_replay_summary(replay_records, task_reference_map)
    trajectory_rows = _build_trajectory_rows(full_run_records, replay_summary, task_reference_map)

    replay_rows = list(replay_summary.values())
    english_replay_rows = [row for row in replay_rows if row["language_code"] == ENGLISH_LANGUAGE_CODE]
    non_english_replay_rows = [row for row in replay_rows if row["language_code"] != ENGLISH_LANGUAGE_CODE]
    english_trajectory_rows = [
        row for row in trajectory_rows if row["language_code"] == ENGLISH_LANGUAGE_CODE
    ]
    non_english_trajectory_rows = [
        row for row in trajectory_rows if row["language_code"] != ENGLISH_LANGUAGE_CODE
    ]

    cells: dict[str, Any] = {}
    by_cell_replay: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_cell_trajectory: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in replay_rows:
        by_cell_replay[(row["model_key"], row["language_code"])].append(row)
    for row in trajectory_rows:
        by_cell_trajectory[(row["model_key"], row["language_code"])].append(row)

    for cell in sorted(set(by_cell_replay) | set(by_cell_trajectory)):
        model_key, language_code = cell
        cell_key = f"{model_key}::{language_code}"
        cells[cell_key] = {
            "replay": _aggregate_stage_rows(by_cell_replay[cell]),
            "trajectory": _aggregate_trajectory_rows(by_cell_trajectory[cell]),
        }

    summary = {
        "scope": {
            "tasks": len(tasks),
            "task_ids": [task.prompt_entry["id"] for task in tasks],
            "languages": sorted({record["language_code"] for record in full_run_records}),
            "models": sorted({record["model_key"] for record in full_run_records}),
            "run_labels": sorted({record["run_label"] for record in full_run_records}),
            "task_trials": len(full_run_records),
            "replay_trials": len(replay_records),
        },
        "aggregates": {
            "english": {
                "replay": _aggregate_stage_rows(english_replay_rows),
                "trajectory": _aggregate_trajectory_rows(english_trajectory_rows),
            },
            "non_english": {
                "replay": _aggregate_stage_rows(non_english_replay_rows),
                "trajectory": _aggregate_trajectory_rows(non_english_trajectory_rows),
            },
            "matched_validity": _matched_trajectory_rates(
                english_rows=english_trajectory_rows,
                comparison_rows=non_english_trajectory_rows,
            ),
        },
        "cells": cells,
        "trajectory_rows": trajectory_rows,
    }
    return summary


def build_decomposition_report(summary: dict[str, Any]) -> str:
    english = summary["aggregates"]["english"]
    non_english = summary["aggregates"]["non_english"]
    matched = summary["aggregates"]["matched_validity"]

    lines = [
        "# E4 Decomposition Report",
        "",
        "## Scope",
        "",
        f"- Tasks: `{summary['scope']['tasks']}`",
        f"- Task IDs: `{summary['scope']['task_ids']}`",
        f"- Models: `{summary['scope']['models']}`",
        f"- Languages: `{summary['scope']['languages']}`",
        f"- Run labels: `{summary['scope']['run_labels']}`",
        f"- Full-task trials: `{summary['scope']['task_trials']}`",
        f"- Replay trials: `{summary['scope']['replay_trials']}`",
        "",
        "## Aggregate Stage Mix",
        "",
        f"- EN invalid replay steps: `{english['replay']['invalid_step_total']}`",
        f"- non-EN invalid replay steps: `{non_english['replay']['invalid_step_total']}`",
        f"- EN stage shares: `{english['replay']['stage_shares']}`",
        f"- non-EN stage shares: `{non_english['replay']['stage_shares']}`",
        "",
        "## Trajectory Effects",
        "",
        f"- EN propagation rate: `{english['trajectory']['propagation_rate']}`",
        f"- EN recovery rate: `{english['trajectory']['recovery_rate']}`",
        f"- non-EN propagation rate: `{non_english['trajectory']['propagation_rate']}`",
        f"- non-EN recovery rate: `{non_english['trajectory']['recovery_rate']}`",
        "",
        "## Matched-Validity Trajectory Effects",
        "",
        f"- Shared replay-validity bins: `{matched['shared_validity_bins']}`",
        f"- Weighted matched pairs: `{matched['weighted_pairs']}`",
        f"- EN matched propagation rate: `{matched['english_propagation_rate']}`",
        f"- non-EN matched propagation rate: `{matched['comparison_propagation_rate']}`",
        f"- EN matched recovery rate: `{matched['english_recovery_rate']}`",
        f"- non-EN matched recovery rate: `{matched['comparison_recovery_rate']}`",
        "",
        "## Cell Highlights",
        "",
    ]
    for cell_key, cell_summary in sorted(summary["cells"].items()):
        lines.extend(
            [
                f"### `{cell_key}`",
                "",
                f"- Replay stage shares: `{cell_summary['replay']['stage_shares']}`",
                f"- Replay failure-type shares: `{cell_summary['replay']['failure_type_shares']}`",
                f"- Propagation rate: `{cell_summary['trajectory']['propagation_rate']}`",
                f"- Recovery rate: `{cell_summary['trajectory']['recovery_rate']}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"
