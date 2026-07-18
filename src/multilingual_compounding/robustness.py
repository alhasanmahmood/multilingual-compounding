from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .bfcl_vendor import BFCLTask
from .evaluation import summarize_cf


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
            if values["p_holm"] < 0.05 and values["Delta"] < 0
        ]
        results[language_code] = {
            "remaining_languages": cf_summary["scope"]["languages"],
            "max_directional_cell": max_directional_cell,
            "significant_cells": significant_cells,
        }
    return results


def summarize_seed_variance(
    tasks: list[BFCLTask],
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
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
    return {
        "run_labels": run_labels,
        "per_label_summaries": per_label_summary,
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
    lines = [
        "# E6 Robustness Report",
        "",
        "## Localization Controls",
        "",
        f"- Localization records: `{localization['total_records']}`",
        f"- Invariance passes: `{localization['invariance_passes']} / {localization['total_records']}`",
        f"- Fidelity rating counts: `{localization['rating_counts']}`",
        f"- Records kept at fidelity >= `{localization['min_fidelity']}`: `{localization['kept_records']}`",
        f"- Records removed by the low-fidelity filter: `{localization['removed_records']}`",
        "",
        "## K Sensitivity",
        "",
        f"- K range checked: `{summary['k_sensitivity']['k_range']}`",
        "",
        "## Leave-One-Language-Out",
        "",
    ]
    for language_code, values in sorted(summary["leave_one_language_out"].items()):
        lines.append(
            f"- Hold out `{language_code}`: max directional cell=`{values['max_directional_cell']}`, "
            f"significant cells=`{values['significant_cells']}`"
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
