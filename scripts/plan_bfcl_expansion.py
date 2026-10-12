from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.bfcl_vendor import BFCLTask, load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import collect_artifact_records  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    PILOT_MODELS,
    BFCL_COMMIT,
    PILOT_TEST_CATEGORIES,
    language_pairs,
)


TARGET_GOLD_CALLS = 10
BASELINE_TASK_IDS = [f"{category}_0" for category in PILOT_TEST_CATEGORIES]
REFERENCE_RUN_LABELS = {
    "gemini": ["pilot_seed0", "pilot_seed1"],
    "claude_sonnet46": ["expanded_seed0", "expanded_seed1"],
}
REFERENCE_PRICES_USD_PER_MILLION = {
    "gemini": {"input": 0.50, "output": 3.00},
    "claude_sonnet46": {"input": 3.00, "output": 15.00},
}
PRICING_SNAPSHOT_DATE = "2026-10-10"


def gold_call_count(task: BFCLTask) -> int:
    return sum(len(turn) for turn in task.ground_truth)


def _natural_task_number(task_id: str) -> int:
    try:
        return int(task_id.rsplit("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Task id does not end in a numeric index: {task_id}") from exc


def select_horizon_matched_tasks(
    tasks: list[BFCLTask], tasks_per_category: int = 5
) -> list[BFCLTask]:
    if tasks_per_category not in {2, 5}:
        raise ValueError("tasks_per_category must be 2 or 5 for the prepared collection plans.")
    by_id = {str(task.prompt_entry["id"]): task for task in tasks}

    # Numeric suffixes identify shared scenarios across category variants.
    # Select one variant per scenario, before observing any model outcomes.
    scenario_ids = sorted({
        _natural_task_number(str(task.prompt_entry["id"])) for task in tasks
    })
    eligible = []
    for scenario in scenario_ids:
        variants = [by_id.get(f"{category}_{scenario}") for category in PILOT_TEST_CATEGORIES]
        if any(task is None for task in variants):
            continue
        lengths = [gold_call_count(task) for task in variants]
        if len(set(lengths)) == 1 and 8 <= lengths[0] <= TARGET_GOLD_CALLS:
            eligible.append((lengths[0], scenario))
    eligible.sort(key=lambda pair: (-pair[0], pair[1]))
    required = tasks_per_category * len(PILOT_TEST_CATEGORIES)
    if len(eligible) < required:
        raise ValueError(f"Only {len(eligible)} complete 8-10-call scenarios are available.")
    selected: list[BFCLTask] = []
    for index, (_length, scenario) in enumerate(eligible[:required]):
        category = PILOT_TEST_CATEGORIES[index % len(PILOT_TEST_CATEGORIES)]
        selected.append(by_id[f"{category}_{scenario}"])
    return selected


def _numeric_values(value: Any) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, list):
        return [number for item in value for number in _numeric_values(item)]
    return []


def _cache_token_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.casefold()
            if "cache" in lowered and "token" in lowered:
                keys.append(key)
            keys.extend(_cache_token_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_cache_token_keys(item))
    return keys


def _stage_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = 0.0
    output_tokens = 0.0
    calls = 0
    cache_keys: set[str] = set()
    for record in records:
        metadata = record.get("metadata", {})
        inputs = _numeric_values(metadata.get("input_token_count", []))
        outputs = _numeric_values(metadata.get("output_token_count", []))
        latencies = _numeric_values(metadata.get("latency", []))
        input_tokens += sum(inputs)
        output_tokens += sum(outputs)
        calls += len(latencies) or len(inputs)
        cache_keys.update(_cache_token_keys(metadata))
    return {
        "records": len(records),
        "api_calls": calls,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cache_token_fields": sorted(cache_keys),
    }


def reference_usage(tasks: list[BFCLTask]) -> dict[str, Any]:
    selected_ids = {str(task.prompt_entry["id"]) for task in tasks}
    usage: dict[str, Any] = {}
    for model_key, run_labels in REFERENCE_RUN_LABELS.items():
        full, replay = collect_artifact_records(
            model_keys=[model_key],
            run_labels=run_labels,
            language_codes=[code for code, _ in language_pairs(None)],
        )
        full = [record for record in full if str(record.get("task_id")) in selected_ids]
        replay = [record for record in replay if str(record.get("task_id")) in selected_ids]
        usage[model_key] = {"full": _stage_usage(full), "replay": _stage_usage(replay)}
    return usage


def _project_tokens(reference: dict[str, Any], scale: float, replay_scale: float) -> dict[str, int]:
    return {
        "input_tokens": int(
            reference["full"]["input_tokens"] * scale + reference["replay"]["input_tokens"] * replay_scale
        ),
        "output_tokens": int(
            reference["full"]["output_tokens"] * scale + reference["replay"]["output_tokens"] * replay_scale
        ),
        "full_api_calls_estimate": int(
            (reference["full"]["api_calls"] * scale) + 0.5
        ),
        "replay_api_calls_exact": int(round(reference["replay"]["records"] * replay_scale)),
    }


def build_expansion_plan(tasks_per_category: int = 5) -> dict[str, Any]:
    all_tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    selected = select_horizon_matched_tasks(all_tasks, tasks_per_category)
    languages = [code for code, _ in language_pairs(None)]
    models = ["gemini", "claude_sonnet46"]
    seeds = ["seed0", "seed1"]
    categories: dict[str, Any] = {}
    for category in PILOT_TEST_CATEGORIES:
        available = [task for task in all_tasks if task.category == category]
        candidates = sorted(
            [task for task in available if gold_call_count(task) == TARGET_GOLD_CALLS],
            key=lambda task: _natural_task_number(str(task.prompt_entry["id"])),
        )
        chosen = [task for task in selected if task.category == category]
        categories[category] = {
            "available_10_gold_call_tasks": len(candidates),
            "selected": [
                {
                    "task_id": str(task.prompt_entry["id"]),
                    "gold_calls": gold_call_count(task),
                    "historical_anchor": str(task.prompt_entry["id"]) in BASELINE_TASK_IDS,
                }
                for task in chosen
            ],
            "at_least_five_10_call_tasks_available": len(candidates) >= 5,
        }

    total_tasks = len(selected)
    historical_task_count = len(BASELINE_TASK_IDS)
    # Use task counts for a conservative price projection. Shorter gold
    # sequences need not imply proportionally fewer full-trajectory tokens.
    scale = total_tasks / historical_task_count
    replay_scale = sum(gold_call_count(task) for task in selected) / (historical_task_count * TARGET_GOLD_CALLS)
    usage = reference_usage([task for task in all_tasks if str(task.prompt_entry["id"]) in BASELINE_TASK_IDS])
    projected: dict[str, Any] = {}
    projected_cost = 0.0
    for model_key in models:
        projection = _project_tokens(usage[model_key], scale, replay_scale)
        prices = REFERENCE_PRICES_USD_PER_MILLION[model_key]
        estimate_usd = (
            projection["input_tokens"] * prices["input"]
            + projection["output_tokens"] * prices["output"]
        ) / 1_000_000
        projected_cost += estimate_usd
        projected[model_key] = {
            **projection,
            "estimated_usd_before_localization": round(estimate_usd, 2),
            "reference_usage": usage[model_key],
            "prices_usd_per_million": prices,
        }

    full_trajectories_per_model = total_tasks * len(languages) * len(seeds)
    replay_calls_per_model = sum(gold_call_count(task) for task in selected) * len(languages) * len(seeds)
    translation_pairs = total_tasks * (len(languages) - 1)
    return {
        "plan_version": 2,
        "pricing_snapshot_date": PRICING_SNAPSHOT_DATE,
        "bfcl_commit": BFCL_COMMIT,
        "tasks_per_category": tasks_per_category,
        "target_gold_calls_per_task": TARGET_GOLD_CALLS,
        "tasks": total_tasks,
        "task_ids": [str(task.prompt_entry["id"]) for task in selected],
        "historical_category_variants": historical_task_count,
        "historical_unique_scenarios": 1,
        "unique_scenarios": total_tasks,
        "fresh_collection": True,
        "selected_horizon_distribution": {
            str(length): sum(gold_call_count(task) == length for task in selected)
            for length in sorted({gold_call_count(task) for task in selected})
        },
        "mean_gold_calls": sum(gold_call_count(task) for task in selected) / total_tasks,
        "selection_rule": "Complete scenario families with 8-10 gold calls; descending gold-call count then numeric scenario id; one variant per family assigned round-robin across categories.",
        "selection_limitations": "A horizon-selected descriptive slice. Category and scenario are not independently crossed, so category contrasts are confounded by scenario assignment.",
        "categories": categories,
        "all_categories_have_at_least_five_10_call_tasks": all(
            item["at_least_five_10_call_tasks_available"] for item in categories.values()
        ),
        "languages": languages,
        "models": {
            model_key: {
                "requested_model_name": PILOT_MODELS[model_key]["model_name"],
                "run_labels": ["expansion_seed0", "expansion_seed1"],
            }
            for model_key in models
        },
        "full_trajectories_per_model_estimate": full_trajectories_per_model,
        "full_trajectories_total_estimate": full_trajectories_per_model * len(models),
        "replay_requests_per_model_exact": replay_calls_per_model,
        "replay_requests_total_exact": replay_calls_per_model * len(models),
        "non_english_task_language_pairs": translation_pairs,
        "translation_requests_estimate": translation_pairs * 2,
        "translation_usage_cost_included": False,
        "token_and_cost_projection": {
            "scope": "fresh runs for every selected task, model, language, and seed",
            "scale_from_existing_four_task_artifacts": scale,
            "replay_scale_from_gold_call_volume": replay_scale,
            "by_model": projected,
            "total_estimated_usd_before_localization": round(projected_cost, 2),
            "cache_tokens": "No cache-token usage fields were present in saved records.",
            "limitation": (
                "Full token/request estimates scale historical usage by the number of trajectories; "
                "replay tokens scale by gold-call volume. New task text and model behavior can change actual usage. "
                "Replay request counts are exact for this plan."
            ),
        },
        "artifact_prefix": "newstudy20261010",
        "localization_prefix": "newstudy20261010",
        "localization_cache_review_required_before_collection": True,
        "provider": "openrouter",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a deterministic horizon-matched BFCL expansion plan and cost projection."
    )
    parser.add_argument(
        "--tasks-per-category",
        type=int,
        choices=[2, 5],
        default=5,
        help="Choose the fresh 8-task or 20-task cohort.",
    )
    args = parser.parse_args()
    print(json.dumps(build_expansion_plan(args.tasks_per_category), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
