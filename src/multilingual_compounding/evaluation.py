from __future__ import annotations

import copy
import json
import os
import re
import sys
from ast import Call, Name, keyword, literal_eval, parse
from dataclasses import asdict
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    full_run_records: list[dict[str, Any]] = []
    replay_records: list[dict[str, Any]] = []
    selected_languages = language_pairs(language_codes)
    for model_key in model_keys:
        for run_label in run_labels:
            for language_code, _language_name in selected_languages:
                full_run_records.extend(
                    read_jsonl(RUNS_ROOT / f"{model_key}_{language_code}_{run_label}.jsonl")
                )
                replay_records.extend(
                    read_jsonl(REPLAY_ROOT / f"{model_key}_{language_code}_{run_label}.jsonl")
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
) -> list[BFCLTask]:
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
        return directory / f"{artifact_prefix}_{filename}"
    return directory / filename


def localize_tasks(
    tasks: list[BFCLTask],
    language_codes: list[str] | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    output_path = LOCALIZATION_ROOT / "bfcl_multiturn_localizations.jsonl"
    if output_path.exists() and not force:
        return [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    translator = OpenAICompatibleTranslator()
    artifacts: list[dict[str, Any]] = []
    selected_languages = language_pairs(language_codes)
    for task in tasks:
        original_turns = get_original_turn_texts(task)
        for language_code, language_name in selected_languages:
            print(f"[localize] {task.prompt_entry['id']} -> {language_code}", flush=True)
            if language_code == "EN":
                localized_turns = list(original_turns)
                backtranslated_turns = list(original_turns)
            else:
                localized_turns = translator.translate_turns(original_turns, language_name)
                backtranslated_turns = translator.backtranslate_turns(
                    localized_turns, language_name
                )
            artifact = build_localization_artifact(
                task_id=task.prompt_entry["id"],
                language_code=language_code,
                language_name=language_name,
                original_turns=original_turns,
                localized_turns=localized_turns,
                backtranslated_turns=backtranslated_turns,
                ground_truth=task.ground_truth,
            )
            artifacts.append(asdict(artifact))
    write_jsonl(output_path, artifacts)
    return artifacts


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
) -> list[dict[str, Any]]:
    loc_index = {
        (record["task_id"], record["language_code"]): record for record in localization_records
    }
    all_records: list[dict[str, Any]] = []
    selected_tasks = tasks[:task_limit] if task_limit is not None else tasks
    selected_languages = language_pairs(language_codes)
    for model_key in models:
        for run_label in run_labels:
            seed = seed_from_run_label(run_label)
            handler = build_handler(model_key, temperature=DEFAULT_TEMPERATURE, seed=seed)
            for language_code, language_name in selected_languages:
                records_for_file: list[dict[str, Any]] = []
                for task in selected_tasks:
                    print(
                        f"[full-run] model={model_key} run={run_label} "
                        f"lang={language_code} task={task.prompt_entry['id']}",
                        flush=True,
                    )
                    localization = loc_index[(task.prompt_entry["id"], language_code)]
                    prompt_entry = _localized_prompt_entry(task, localization["localized_turns"])
                    prompt_entry["id"] = build_execution_id(
                        task.prompt_entry["id"],
                        model_key,
                        run_label,
                        language_code,
                    )
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
                    record = {
                        "task_id": task.prompt_entry["id"],
                        "category": task.category,
                        "language_code": language_code,
                        "language_name": language_name,
                        "model_key": model_key,
                        "run_label": run_label,
                        "seed": seed,
                        "success": int(evaluation["valid"]),
                        "result": result,
                        "metadata": metadata,
                        "evaluation": evaluation,
                    }
                    records_for_file.append(record)
                    all_records.append(record)
                output_path = RUNS_ROOT / f"{model_key}_{language_code}_{run_label}.jsonl"
                write_jsonl(output_path, records_for_file)
    return all_records


def run_step_replays(
    tasks: list[BFCLTask],
    localization_records: list[dict[str, Any]],
    models: list[str],
    run_labels: list[str],
    language_codes: list[str] | None = None,
    task_limit: int | None = None,
) -> list[dict[str, Any]]:
    loc_index = {
        (record["task_id"], record["language_code"]): record for record in localization_records
    }
    all_records: list[dict[str, Any]] = []
    selected_tasks = tasks[:task_limit] if task_limit is not None else tasks
    selected_languages = language_pairs(language_codes)
    for model_key in models:
        for run_label in run_labels:
            seed = seed_from_run_label(run_label)
            handler = build_handler(model_key, temperature=DEFAULT_TEMPERATURE, seed=seed)
            for language_code, _language_name in selected_languages:
                records_for_file: list[dict[str, Any]] = []
                for task in selected_tasks:
                    localization = loc_index[(task.prompt_entry["id"], language_code)]
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
                        print(
                            f"[replay] model={model_key} run={run_label} "
                            f"lang={language_code} task={replay_case.task_id} "
                            f"turn={replay_case.turn_index} step={replay_case.step_index}",
                            flush=True,
                        )
                        result, metadata = _run_step_replay_query(
                            handler,
                            task,
                            replay_case,
                            localization["localized_turns"],
                        )
                        candidate_call = _extract_first_candidate_call(handler, result)
                        evaluation = evaluate_step_replay(replay_case, candidate_call)
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
                            "metadata": metadata,
                            "evaluation": evaluation,
                        }
                        records_for_file.append(record)
                        all_records.append(record)
                output_path = REPLAY_ROOT / f"{model_key}_{language_code}_{run_label}.jsonl"
                write_jsonl(output_path, records_for_file)
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
) -> dict[str, Any]:
    metrics = load_metrics_module()
    task_lookup = {task.prompt_entry["id"]: task for task in tasks}
    k_info = estimate_k(tasks)

    task_records = []
    for run_record in full_run_records:
        matching_replays = [
            replay
            for replay in replay_records
            if replay["task_id"] == run_record["task_id"]
            and replay["language_code"] == run_record["language_code"]
            and replay["model_key"] == run_record["model_key"]
            and replay["run_label"] == run_record["run_label"]
        ]
        matching_replays.sort(key=lambda item: (item["turn_index"], item["step_index"]))
        task_records.append(
            metrics.TaskRecord(
                task_id=f"{run_record['task_id']}::{run_record['run_label']}",
                language=run_record["language_code"],
                backbone=run_record["model_key"],
                success=run_record["success"],
                step_validity=[replay["valid"] for replay in matching_replays],
            )
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
        },
        "point_estimates": {},
        "bootstrap": {},
    }
    for k in k_info["k_range"]:
        point = metrics.compute_cf(task_records, K=k, null="common")
        bootstrap = metrics.bootstrap_cf(task_records, K=k, null="common", n_boot=200, seed=0)
        position_bootstrap = metrics.bootstrap_cf(
            task_records, K=k, null="position", n_boot=200, seed=0
        )
        summary["point_estimates"][str(k)] = {
            f"{lang}::{backbone}": values for (lang, backbone), values in point.items()
        }
        summary["bootstrap"][str(k)] = {
            "common": {
                f"{lang}::{backbone}": values
                for (lang, backbone), values in bootstrap.items()
            },
            "position": {
                f"{lang}::{backbone}": values
                for (lang, backbone), values in position_bootstrap.items()
            },
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
        f"- Mean K: `{cf_summary['k']['mean_k']:.2f}`",
        f"- Rounded K: `{cf_summary['k']['rounded_k']}`",
        f"- K range checked: `{cf_summary['k']['k_range']}`",
        "",
        "## CF snapshot",
    ]
    rounded_k = str(cf_summary["k"]["rounded_k"])
    for cell, values in sorted(cf_summary["bootstrap"][rounded_k]["common"].items()):
        lines.append(
            f"- `{cell}`: T={values['T']:.3f}, p={values['p']:.3f}, "
            f"CF={values['CF']}, Delta={values['Delta']:.3f}, p_holm={values['p_holm']}"
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
) -> dict[str, Any]:
    run_labels = run_labels or DEFAULT_RUN_LABELS
    full_run_records, replay_records = collect_artifact_records(
        model_keys=model_keys,
        run_labels=run_labels,
        language_codes=language_codes,
    )
    cf_summary = summarize_cf(
        full_run_records=full_run_records,
        replay_records=replay_records,
        tasks=tasks,
    )
    write_json(_artifact_output_path(SUMMARY_ROOT, "cf_summary.json", artifact_prefix), cf_summary)
    report_path = write_analysis_report(cf_summary, artifact_prefix=artifact_prefix)
    return {
        "full_runs": len(full_run_records),
        "replays": len(replay_records),
        "report": str(report_path),
    }


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
) -> dict[str, Any]:
    load_env_file(ROOT_ENV_FILE)
    ensure_project_dirs()

    run_labels = run_labels or DEFAULT_RUN_LABELS
    tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    selected_tasks = select_bfcl_tasks(
        tasks,
        task_limit=task_limit,
        per_category_limit=per_category_limit,
    )

    localization_records = localize_tasks(
        selected_tasks,
        language_codes=language_codes,
        force=force_localization,
    )
    if execute_full_runs:
        full_run_records = run_full_tasks(
            tasks=selected_tasks,
            localization_records=localization_records,
            models=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
        )
    else:
        full_run_records, _unused_replays = collect_artifact_records(
            model_keys=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
        )

    if execute_replays:
        replay_records = run_step_replays(
            tasks=selected_tasks,
            localization_records=localization_records,
            models=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
        )
    else:
        _unused_full_runs, replay_records = collect_artifact_records(
            model_keys=model_keys,
            run_labels=run_labels,
            language_codes=language_codes,
        )

    metadata = {
        "bfcl_commit": BFCL_COMMIT,
        "models": model_keys,
        "run_labels": run_labels,
        "task_limit": task_limit,
        "per_category_limit": per_category_limit,
        "language_codes": [code for code, _name in language_pairs(language_codes)],
        "artifact_prefix": artifact_prefix,
        "execute_full_runs": execute_full_runs,
        "execute_replays": execute_replays,
        "cwd": os.getcwd(),
    }
    write_json(_artifact_output_path(METADATA_ROOT, "evaluation_metadata.json", artifact_prefix), metadata)
    cf_summary = summarize_cf(
        full_run_records=full_run_records,
        replay_records=replay_records,
        tasks=selected_tasks,
    )
    write_json(_artifact_output_path(SUMMARY_ROOT, "cf_summary.json", artifact_prefix), cf_summary)
    report_path = write_analysis_report(cf_summary, artifact_prefix=artifact_prefix)

    return {
        "tasks": len(selected_tasks),
        "localizations": len(localization_records),
        "full_runs": len(full_run_records),
        "replays": len(replay_records),
        "report": str(report_path),
    }


# Backward-compatible alias.
run_bfcl_pilot = run_bfcl_evaluation
