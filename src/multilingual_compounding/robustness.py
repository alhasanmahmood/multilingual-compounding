from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any

from .bfcl_vendor import BFCLTask
from .evaluation import get_original_turn_texts, seed_from_run_label, summarize_cf, task_content_sha256


SOURCE_QUOTED_PATTERN = re.compile(r"(?<!\w)'([^'\n]+)'(?!\w)|\"([^\"\n]+)\"")


def _localized_turns_sha256(turns: list[str]) -> str:
    serialized = json.dumps(turns, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def validate_reviewed_localizations(
    localization_records: list[dict[str, Any]],
    tasks: list[BFCLTask],
    language_codes: list[str],
) -> dict[str, Any]:
    """Validate AI-reviewed translations and exact source-literal preservation.

    English rows are accepted only when the stored target is exactly the source.
    Non-English rows must have a current AI review hash and no unresolved issues.
    This deliberately does not use the machine fidelity/invariance fields as a gate.
    """
    task_by_id = {str(task.prompt_entry["id"]): task for task in tasks}
    expected = {
        (task_id, language)
        for task_id in task_by_id
        for language in language_codes
    }
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for record in localization_records:
        key = (str(record.get("task_id", "")), str(record.get("language_code", "")))
        if key not in expected:
            continue
        if key in indexed:
            raise ValueError(f"Duplicate localization row for {key}")
        indexed[key] = record

    missing_rows = sorted(expected - indexed.keys())
    if missing_rows:
        raise ValueError(f"Missing reviewed localization rows: {missing_rows[:8]}")

    review_status_counts: Counter[str] = Counter()
    human_review_status_counts: Counter[str] = Counter()
    quoted_literals_checked = 0
    english_identity_rows = 0
    for (task_id, language), record in indexed.items():
        task = task_by_id[task_id]
        source_turns = get_original_turn_texts(task)
        target_turns = record.get("localized_turns")
        if not isinstance(target_turns, list) or any(not isinstance(turn, str) for turn in target_turns):
            raise ValueError(f"Localized turns must be a list of strings for {task_id}/{language}")
        if len(target_turns) != len(source_turns):
            raise ValueError(
                f"Turn alignment mismatch for {task_id}/{language}: "
                f"source={len(source_turns)} target={len(target_turns)}"
            )
        for turn_index, (source_turn, target_turn) in enumerate(zip(source_turns, target_turns)):
            if bool(source_turn.strip()) != bool(target_turn.strip()):
                raise ValueError(
                    f"Empty-turn alignment mismatch for {task_id}/{language} at turn {turn_index}"
                )
            for match in SOURCE_QUOTED_PATTERN.finditer(source_turn):
                literal = match.group(1) or match.group(2)
                quoted_literals_checked += 1
                if literal not in target_turn:
                    raise ValueError(
                        f"Quoted source literal {literal!r} missing from {task_id}/{language} "
                        f"turn {turn_index}"
                    )

        if language == "EN":
            if target_turns != source_turns:
                raise ValueError(f"English localization must equal source text for {task_id}")
            english_identity_rows += 1
        else:
            review = record.get("ai_review") or {}
            status = review.get("status")
            if status not in {"reviewed", "corrected"}:
                raise ValueError(f"Non-English localization is not AI-reviewed: {task_id}/{language}")
            if review.get("unresolved_issues") != []:
                raise ValueError(f"AI review has unresolved issues for {task_id}/{language}")
            if review.get("localized_turns_sha256") != _localized_turns_sha256(target_turns):
                raise ValueError(f"AI review target hash is stale for {task_id}/{language}")
            if review.get("source_task_sha256") != task_content_sha256(task):
                raise ValueError(f"AI review source hash is stale for {task_id}/{language}")
            review_status_counts[status] += 1

        human_status = (record.get("human_review") or {}).get("status", "missing")
        human_review_status_counts[str(human_status)] += 1

    return {
        "validated_records": len(indexed),
        "english_identity_rows": english_identity_rows,
        "ai_review_status_counts": dict(sorted(review_status_counts.items())),
        "human_review_status_counts": dict(sorted(human_review_status_counts.items())),
        "source_quoted_literals_checked": quoted_literals_checked,
    }


def filter_to_complete_task_intersection(
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    tasks: list[BFCLTask],
    model_keys: list[str],
    language_codes: list[str],
    run_labels: list[str],
) -> dict[str, Any]:
    """Keep only tasks complete for each model's requested paired seeds and replays.

    This makes the English controls share the same task set as each translated
    language and prevents seed/model subsets from changing the scenario mix.
    Historical cohorts use model-specific label families (for example, the
    Gemini runs use ``pilot_seed*`` while Claude uses ``expanded_seed*``), so
    completeness is checked against the requested labels present for each model
    rather than requiring every model to have every global label.
    """
    tasks_by_id = {str(task.prompt_entry["id"]): task for task in tasks}
    requested_labels = list(dict.fromkeys(run_labels))
    full_keys: set[tuple[str, str, str, str]] = set()
    available_labels_by_model: dict[str, set[str]] = {model: set() for model in model_keys}
    for record in full_run_records:
        key = (
            str(record["model_key"]),
            str(record["language_code"]),
            str(record["task_id"]),
            str(record["run_label"]),
        )
        if key in full_keys:
            raise ValueError(f"Duplicate full-run key while building task intersection: {key}")
        full_keys.add(key)
        if key[0] in available_labels_by_model and key[3] in requested_labels:
            available_labels_by_model[key[0]].add(key[3])

    expected_seed_ids = {
        seed
        for seed in (seed_from_run_label(label) for label in requested_labels)
        if seed is not None
    }
    labels_by_model: dict[str, list[str]] = {}
    for model in model_keys:
        model_labels = [label for label in requested_labels if label in available_labels_by_model[model]]
        model_seeds = {
            seed
            for seed in (seed_from_run_label(label) for label in model_labels)
            if seed is not None
        }
        if not model_labels:
            raise ValueError(f"No requested full-run labels are available for model {model}")
        if expected_seed_ids and model_seeds != expected_seed_ids:
            raise ValueError(
                f"Model {model} has seed IDs {sorted(model_seeds)}, expected matched seed IDs "
                f"{sorted(expected_seed_ids)} from requested labels"
            )
        labels_by_model[model] = model_labels

    replay_positions: dict[tuple[str, str, str, str], set[tuple[int, int]]] = defaultdict(set)
    for record in replay_records:
        key = (
            str(record["model_key"]),
            str(record["language_code"]),
            str(record["task_id"]),
            str(record["run_label"]),
        )
        position = (int(record["turn_index"]), int(record["step_index"]))
        if position in replay_positions[key]:
            raise ValueError(f"Duplicate replay position while building task intersection: {key}/{position}")
        replay_positions[key].add(position)

    retained_task_ids: list[str] = []
    excluded: dict[str, list[str]] = {}
    for task_id, task in tasks_by_id.items():
        reasons: list[str] = []
        expected_positions = {
            (turn_index, step_index)
            for turn_index, turn in enumerate(task.ground_truth)
            for step_index, _call in enumerate(turn)
        }
        for model in model_keys:
            for language in language_codes:
                for label in labels_by_model[model]:
                    key = (model, language, task_id, label)
                    if key not in full_keys:
                        reasons.append(f"missing_full:{model}/{language}/{label}")
                        continue
                    if replay_positions.get(key, set()) != expected_positions:
                        reasons.append(f"incomplete_replays:{model}/{language}/{label}")
        if reasons:
            excluded[task_id] = reasons
        else:
            retained_task_ids.append(task_id)

    if not retained_task_ids:
        raise ValueError("No task is complete across all requested models, languages, seeds, and replay positions")
    retained = set(retained_task_ids)
    return {
        "task_ids": retained_task_ids,
        "tasks": [task for task in tasks if str(task.prompt_entry["id"]) in retained],
        "full_run_records": [record for record in full_run_records if str(record["task_id"]) in retained],
        "replay_records": [record for record in replay_records if str(record["task_id"]) in retained],
        "run_labels_by_model": labels_by_model,
        "excluded_task_reasons": excluded,
    }


def summarize_localization_robustness(
    localization_records: list[dict[str, Any]],
    min_fidelity: int = 3,
    require_invariance: bool = True,
) -> dict[str, Any]:
    total = len(localization_records)
    invariance_passes = sum(1 for record in localization_records if record["invariance_pass"])
    rating_counts = Counter(record["machine_fidelity_rating"] for record in localization_records)
    kept_records = [
        record
        for record in localization_records
        if record["machine_fidelity_rating"] >= min_fidelity
        and (record["invariance_pass"] or not require_invariance)
    ]
    removed_records = total - len(kept_records)
    return {
        "total_records": total,
        "invariance_passes": invariance_passes,
        "invariance_rate": invariance_passes / total if total else None,
        "rating_counts": dict(rating_counts),
        "min_fidelity": min_fidelity,
        "require_invariance": require_invariance,
        "kept_records": len(kept_records),
        "removed_records": removed_records,
        "kept_pairs": sorted(
            {(record["task_id"], record["language_code"]) for record in kept_records}
        ),
    }


def filter_records_by_localization(
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    localization_records: list[dict[str, Any]],
    *,
    min_fidelity: int = 3,
    require_invariance: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed_pairs = {
        (record["task_id"], record["language_code"])
        for record in localization_records
        if record["machine_fidelity_rating"] >= min_fidelity
        and (record["invariance_pass"] or not require_invariance)
    }
    filtered_full = [
        record
        for record in full_run_records
        if (record["task_id"], record["language_code"]) in allowed_pairs
    ]
    filtered_replays = [
        record
        for record in replay_records
        if (record["task_id"], record["language_code"]) in allowed_pairs
    ]
    return filtered_full, filtered_replays


def summarize_leave_one_language_out(
    tasks: list[BFCLTask],
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    *,
    n_boot: int = 5_000,
    bootstrap_seed: int = 0,
    cluster_unit: str = "underlying_task",
) -> dict[str, Any]:
    non_english_languages = sorted(
        {record["language_code"] for record in full_run_records if record["language_code"] != "EN"}
    )
    results: dict[str, Any] = {}
    for language_code in non_english_languages:
        held_out_full = [
            record for record in full_run_records if record["language_code"] != language_code
        ]
        held_out_replays = [
            record for record in replay_records if record["language_code"] != language_code
        ]
        cf_summary = summarize_cf(
            full_run_records=held_out_full,
            replay_records=held_out_replays,
            tasks=tasks,
            n_boot=n_boot,
            bootstrap_seed=bootstrap_seed,
            cluster_unit=cluster_unit,
        )
        rounded_k = str(cf_summary["k"]["rounded_k"])
        common_bootstrap = cf_summary["bootstrap"][rounded_k]["common"]
        directional_cells = {
            cell: values for cell, values in common_bootstrap.items() if values["Delta"] < 0
        }
        max_directional_cell = None
        if directional_cells:
            max_directional_cell = min(
                directional_cells.items(),
                key=lambda item: item[1]["Delta"],
            )[0]
        significant_cells = [
            cell
            for cell, values in common_bootstrap.items()
            if values.get("p_holm") is not None and values["p_holm"] < 0.05 and values["Delta"] < 0
        ]
        results[language_code] = {
            "remaining_languages": cf_summary["scope"]["languages"],
            "max_directional_cell": max_directional_cell,
            "significant_cells": significant_cells,
            "inference_status": cf_summary.get("bootstrap_settings", {}).get("inference_status", "descriptive_only"),
        }
    return results


def summarize_seed_variance(
    tasks: list[BFCLTask],
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    *,
    n_boot: int = 5_000,
    bootstrap_seed: int = 0,
    cluster_unit: str = "underlying_task",
) -> dict[str, Any]:
    run_labels = sorted({record["run_label"] for record in full_run_records})
    per_label_summary: dict[str, dict[str, Any]] = {}
    for run_label in run_labels:
        run_full = [record for record in full_run_records if record["run_label"] == run_label]
        run_replays = [record for record in replay_records if record["run_label"] == run_label]
        if not run_full or not run_replays:
            continue
        per_label_summary[run_label] = summarize_cf(
            full_run_records=run_full,
            replay_records=run_replays,
            tasks=tasks,
            n_boot=n_boot,
            bootstrap_seed=bootstrap_seed,
            cluster_unit=cluster_unit,
        )

    rounded_k_by_label = {
        run_label: str(summary["k"]["rounded_k"]) for run_label, summary in per_label_summary.items()
    }
    cells_by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for run_label, summary in per_label_summary.items():
        rounded_k = rounded_k_by_label[run_label]
        cells_by_label[run_label] = summary["bootstrap"][rounded_k]["common"]

    all_cells = sorted({cell for cells in cells_by_label.values() for cell in cells})
    by_cell: dict[str, Any] = {}
    for cell in all_cells:
        values_by_run = {
            run_label: cells[cell]
            for run_label, cells in cells_by_label.items()
            if cell in cells
        }
        if len(values_by_run) < 2:
            continue
        p_values = [values["p"] for values in values_by_run.values()]
        t_values = [values["T"] for values in values_by_run.values()]
        delta_values = [values["Delta"] for values in values_by_run.values()]
        cf_values = [values["CF"] for values in values_by_run.values() if values["CF"] == values["CF"]]
        by_cell[cell] = {
            "run_labels": sorted(values_by_run),
            "p_range": [float(min(p_values)), float(max(p_values))],
            "T_range": [float(min(t_values)), float(max(t_values))],
            "Delta_range": [float(min(delta_values)), float(max(delta_values))],
            "CF_range": [float(min(cf_values)), float(max(cf_values))] if cf_values else None,
        }
    # Pilot/expanded are collection labels, not distinct decoding seeds.
    # Group by the actual seed while retaining each model's own task rows.
    seeds = sorted({seed_from_run_label(label) for label in run_labels} - {None})
    per_seed_summary = {}
    for seed in seeds:
        seed_full = [r for r in full_run_records if seed_from_run_label(r["run_label"]) == seed]
        seed_replays = [r for r in replay_records if seed_from_run_label(r["run_label"]) == seed]
        if seed_full and seed_replays:
            per_seed_summary[str(seed)] = summarize_cf(
                full_run_records=seed_full,
                replay_records=seed_replays,
                tasks=tasks,
                n_boot=n_boot,
                bootstrap_seed=bootstrap_seed,
                cluster_unit=cluster_unit,
            )
    return {
        "run_labels": run_labels,
        "per_label_summaries": per_label_summary,
        "per_seed_summaries": per_seed_summary,
        "seed_grouping": "Group collection labels by their actual decoding seed number, separately within each backbone.",
        "by_cell": by_cell,
    }


def summarize_k_sensitivity(cf_summary: dict[str, Any]) -> dict[str, Any]:
    cells = sorted(
        {
            cell
            for values in cf_summary["bootstrap"].values()
            for cell in values["common"].keys()
        }
    )
    by_cell: dict[str, Any] = {}
    for cell in cells:
        cell_values = {}
        for k, values in cf_summary["bootstrap"].items():
            if cell not in values["common"]:
                continue
            common_values = values["common"][cell]
            position_values = values["position"].get(cell, {})
            cell_values[k] = {
                "common": {
                    "CF": common_values["CF"],
                    "Delta": common_values["Delta"],
                    "p_holm": common_values["p_holm"],
                },
                "position": {
                    "CF": position_values.get("CF"),
                    "Delta": position_values.get("Delta"),
                    "p_holm": position_values.get("p_holm"),
                },
            }
        by_cell[cell] = cell_values
    return {"k_range": cf_summary["k"]["k_range"], "by_cell": by_cell}


def build_robustness_report(summary: dict[str, Any]) -> str:
    localization = summary["localization"]
    scope = summary.get("scope", {})
    if localization.get("policy") == "reviewed":
        diagnostic = localization["automatic_heuristic_diagnostic"]
        localization_lines = [
            "## Localization Controls",
            "",
            f"- Policy: `{localization['policy']}`; validated rows retained: `{localization['retained_records']} / {localization['total_records']}`",
            f"- AI review status counts: `{localization['ai_review_status_counts']}`; English source/target identity rows: `{localization['english_identity_rows']}`",
            f"- Exact quoted source literals checked: `{localization['source_quoted_literals_checked']}`",
            f"- Human review status counts: `{localization['human_review_status_counts']}`",
            f"- Automatic heuristic diagnostic only: invariance passes `{diagnostic['invariance_passes']} / {localization['total_records']}`, rating counts `{diagnostic['rating_counts']}`",
            f"- Legacy combined heuristic would retain `{diagnostic['combined_heuristic_passes']}` and remove `{diagnostic['combined_heuristic_removed']}` rows; it did not filter this analysis.",
            "",
        ]
    else:
        fidelity_passes = sum(
            count for rating, count in localization["rating_counts"].items()
            if int(rating) >= localization["min_fidelity"]
        )
        localization_lines = [
            "## Localization Controls",
            "",
            f"- Localization records: `{localization['total_records']}`",
            f"- Machine invariance heuristic passes: `{localization['invariance_passes']} / {localization['total_records']}`",
            f"- Fidelity rating counts: `{localization['rating_counts']}`; ratings at or above threshold: `{fidelity_passes}`",
            f"- Records passing the combined fidelity and invariance filter: `{localization['kept_records']}`",
            f"- Records removed by the combined localization filter: `{localization['removed_records']}`",
            "",
        ]
    lines = [
        "# E6 Robustness Report",
        "",
        "## Analysis Scope",
        "",
        f"- Localization policy: `{summary.get('localization_policy', 'legacy')}`",
        f"- Tasks represented in filtered rows: `{scope.get('actual_tasks', scope.get('tasks', 'unknown'))}`",
        f"- Full trajectories and replays: `{scope.get('full_runs', 'unknown')}` and `{scope.get('replays', 'unknown')}`",
        f"- Task intersection policy: `{summary.get('task_intersection', {}).get('policy', 'not recorded')}`",
        "",
        *localization_lines,
        "## K Sensitivity",
        "",
        f"- K range checked: `{summary['k_sensitivity']['k_range']}`",
        "- Bootstrap tail values are uncalibrated directional diagnostics, not inferential p-values.",
        "",
        "## Leave-One-Language-Out",
        "",
    ]
    for language_code, values in sorted(summary["leave_one_language_out"].items()):
        lines.append(
            f"- Hold out `{language_code}`: max directional cell=`{values['max_directional_cell']}`, "
            f"significant cells=`{values['significant_cells']}`, status=`{values.get('inference_status', 'descriptive_only')}`"
        )
    lines.extend(
        [
            "",
            "## Seed Variance",
            "",
            f"- Run labels considered: `{summary['seed_variance']['run_labels']}`",
        ]
    )
    for cell, values in sorted(summary["seed_variance"]["by_cell"].items()):
        lines.append(
            f"- `{cell}`: p_range=`{values['p_range']}`, T_range=`{values['T_range']}`, "
            f"Delta_range=`{values['Delta_range']}`, CF_range=`{values['CF_range']}`"
        )
    lines.extend(
        [
            "",
            "## Environment Holdout",
            "",
            f"- Status: `{summary['environment_holdout']['status']}`",
            f"- Reason: {summary['environment_holdout']['reason']}",
            "",
        ]
    )
    return "\n".join(lines)
