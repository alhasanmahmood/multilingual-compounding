from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.env import load_env_file  # noqa: E402
from multilingual_compounding.paths import ROOT_ENV_FILE, SUMMARY_ROOT  # noqa: E402
from multilingual_compounding.bfcl_vendor import load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import (  # noqa: E402
    collect_artifact_records,
    select_bfcl_tasks,
)
from multilingual_compounding.metrics import TaskRecord, bootstrap_cf, compute_cf  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    PILOT_TEST_CATEGORIES,
    resolve_language_codes,
    resolve_model_keys,
    supported_model_keys,
)


DEFAULT_MODELS = ["gemini", "claude_sonnet46"]
DEFAULT_RUN_LABELS = ["pilot_seed0", "pilot_seed1", "expanded_seed0", "expanded_seed1"]
DEFAULT_K_VALUES = [9, 10, 11]
MAIN_SUMMARY_PATH = SUMMARY_ROOT / "main_results_cf_summary.json"
OUTPUT_SUMMARY_PATH = SUMMARY_ROOT / "task_sensitivity_summary.json"
OUTPUT_REPORT_PATH = SUMMARY_ROOT / "task_sensitivity_report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare task-seed and underlying-task uncertainty from saved BFCL artifacts."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help=f"Models in the saved run. Supported keys: {', '.join(supported_model_keys())}.",
    )
    parser.add_argument("--run-labels", nargs="+", default=DEFAULT_RUN_LABELS)
    parser.add_argument("--language-codes", nargs="+", default=None)
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Exact BFCL task IDs to analyze. This overrides category/task limits.",
    )
    parser.add_argument("--per-category-limit", type=int, default=1)
    parser.add_argument(
        "--input-artifact-prefix",
        default=None,
        help="Prefix on source run and replay JSONL files.",
    )
    parser.add_argument("--n-boot", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--k-values", nargs="+", type=int, default=DEFAULT_K_VALUES)
    parser.add_argument("--min-log-rind", type=float, default=0.05)
    parser.add_argument(
        "--main-summary-path",
        type=Path,
        default=MAIN_SUMMARY_PATH,
        help="Point-estimate summary used for the invariance check (defaults to the existing main summary).",
    )
    parser.add_argument("--summary-path", type=Path, default=OUTPUT_SUMMARY_PATH)
    parser.add_argument("--report-path", type=Path, default=OUTPUT_REPORT_PATH)
    return parser.parse_args()


def _run_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        record["model_key"],
        record["language_code"],
        record["task_id"],
        record["run_label"],
    )


def build_task_records(
    full_run_records: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    tasks: list[Any],
    model_keys: list[str],
    language_codes: list[str],
    run_labels: list[str],
) -> tuple[list[TaskRecord], dict[str, Any]]:
    """Validate complete pairing and convert saved trajectories to metric rows."""
    task_by_id = {str(task.prompt_entry["id"]): task for task in tasks}
    task_ids = set(task_by_id)
    scenario_family_by_task = {}
    for task_id in task_ids:
        match = re.search(r"_(\d+)$", task_id)
        if match is None:
            raise ValueError(f"Task ID has no numeric scenario suffix: {task_id}")
        scenario_family_by_task[task_id] = f"scenario_{match.group(1)}"
    labels_by_model = {
        model: sorted(
            {
                record["run_label"]
                for record in full_run_records
                if record["model_key"] == model and record["run_label"] in run_labels
            }
        )
        for model in model_keys
    }
    missing_model_labels = [model for model, labels in labels_by_model.items() if not labels]
    if missing_model_labels:
        raise ValueError(f"No saved runs found for requested models: {missing_model_labels}")
    expected_runs = {
        (model, language, task_id, run_label)
        for model in model_keys
        for language, task_id, run_label in itertools.product(
            language_codes, sorted(task_ids), labels_by_model[model]
        )
    }
    full_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in full_run_records:
        key = _run_key(record)
        if key in full_by_key:
            raise ValueError(f"Duplicate full trajectory record for {key}")
        full_by_key[key] = record
    observed_runs = set(full_by_key)
    missing_runs = sorted(expected_runs - observed_runs)
    unexpected_runs = sorted(observed_runs - expected_runs)
    if missing_runs or unexpected_runs:
        raise ValueError(
            "Saved full-run artifacts do not match the requested complete design: "
            f"missing={missing_runs[:5]}, unexpected={unexpected_runs[:5]}"
        )

    runs_by_model_task_seed: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for model, language, task_id, run_label in observed_runs:
        runs_by_model_task_seed[(model, task_id, run_label)].add(language)
    incomplete_language_pairs = {
        key: sorted(set(language_codes) - languages)
        for key, languages in runs_by_model_task_seed.items()
        if languages != set(language_codes) or "EN" not in languages
    }
    if incomplete_language_pairs:
        raise ValueError(
            "Each task, model, and seed must include a paired English baseline and all "
            f"requested languages: {list(incomplete_language_pairs.items())[:5]}"
        )

    replay_by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for replay in replay_records:
        replay_by_key[_run_key(replay)].append(replay)
    unexpected_replay_keys = sorted(set(replay_by_key) - expected_runs)
    if unexpected_replay_keys:
        raise ValueError(f"Unexpected isolated replay records: {unexpected_replay_keys[:5]}")

    task_records: list[TaskRecord] = []
    for key in sorted(expected_runs):
        model, language, task_id, run_label = key
        task = task_by_id[task_id]
        matched_replays = replay_by_key.get(key, [])
        expected_replays = sum(len(turn) for turn in task.ground_truth)
        if len(matched_replays) != expected_replays:
            raise ValueError(
                f"Expected {expected_replays} isolated replays for {key}, "
                f"found {len(matched_replays)}"
            )
        matched_replays.sort(key=lambda item: (item["turn_index"], item["step_index"]))
        task_records.append(
            TaskRecord(
                task_id=f"{task_id}::{run_label}",
                language=language,
                backbone=model,
                success=int(full_by_key[key]["success"]),
                step_validity=[int(replay["valid"]) for replay in matched_replays],
                underlying_task_id=scenario_family_by_task[task_id],
                task_variant_id=task_id,
            )
        )

    if len(task_records) != len(expected_runs):
        raise ValueError(f"Expected {len(expected_runs)} records, built {len(task_records)}")
    diagnostics = {
        "expected_full_runs": len(expected_runs),
        "observed_full_runs": len(full_run_records),
        "expected_replays": sum(len(turn) for task in tasks for turn in task.ground_truth)
        * len(language_codes)
        * sum(len(labels) for labels in labels_by_model.values()),
        "observed_replays": len(replay_records),
        "task_seed_clusters_by_model": {
            model: len(task_ids) * len(labels) for model, labels in labels_by_model.items()
        },
        "underlying_task_clusters_by_model": {
            model: len(set(scenario_family_by_task.values())) for model in model_keys
        },
        "scenario_family_to_task_variants": {
            family: sorted(
                task_id for task_id, task_family in scenario_family_by_task.items()
                if task_family == family
            )
            for family in sorted(set(scenario_family_by_task.values()))
        },
        "run_labels_by_model": labels_by_model,
        "english_pairing": "complete for each task, model, and run label",
        "replay_count_check": "every full trajectory has all expected isolated replays",
    }
    return task_records, diagnostics


def _sign(value: float) -> str:
    if value < -1e-12:
        return "negative"
    if value > 1e-12:
        return "positive"
    return "zero"


def _cf_reportable(values: dict[str, Any], min_log_rind: float) -> bool:
    return abs(float(np.log(values["r_ind"]))) >= min_log_rind


def summarize_leave_one_task_out(
    records: list[TaskRecord],
    k_values: list[int],
    nulls: tuple[str, ...] = ("common", "position"),
    min_log_rind: float = 0.05,
) -> dict[str, Any]:
    """Measure influence of each category-specific BFCL task variant.

    The category variants may share an underlying scenario. Removing one
    variant therefore leaves its sibling variants in the sample and is an
    influence analysis, not a leave-one-independent-scenario-out estimate.
    """
    variant_ids = sorted(
        {record.task_variant_id or record.task_id.split("::", 1)[0] for record in records}
    )
    output: dict[str, Any] = {}
    for k in k_values:
        output[str(k)] = {}
        for null in nulls:
            full = compute_cf(records, K=k, null=null)
            omissions: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
            for variant_id in variant_ids:
                reduced = [
                    record
                    for record in records
                    if (record.task_variant_id or record.task_id.split("::", 1)[0])
                    != variant_id
                ]
                omissions[variant_id] = compute_cf(reduced, K=k, null=null)

            cells: dict[str, Any] = {}
            for cell, full_values in full.items():
                delta_by_omission = {
                    variant_id: float(omissions[variant_id][cell]["Delta"])
                    for variant_id in variant_ids
                }
                full_sign = _sign(float(full_values["Delta"]))
                omission_signs = {
                    variant_id: _sign(value) for variant_id, value in delta_by_omission.items()
                }
                full_reportable = _cf_reportable(full_values, min_log_rind)
                reportable_by_omission = {
                    variant_id: _cf_reportable(omissions[variant_id][cell], min_log_rind)
                    for variant_id in variant_ids
                }
                reportable_cf = {
                    variant_id: (
                        float(omissions[variant_id][cell]["CF"])
                        if reportable_by_omission[variant_id]
                        else None
                    )
                    for variant_id in variant_ids
                }
                finite_cfs = [value for value in reportable_cf.values() if value is not None]
                cells[f"{cell[0]}::{cell[1]}"] = {
                    "full": {
                        "CF": float(full_values["CF"]),
                        "Delta": float(full_values["Delta"]),
                        "r_ind": float(full_values["r_ind"]),
                        "CF_reportable": full_reportable,
                    },
                    "leave_one_task_variant_out": {
                        variant_id: {
                            "CF": reportable_cf[variant_id],
                            "Delta": delta_by_omission[variant_id],
                            "r_ind": float(omissions[variant_id][cell]["r_ind"]),
                            "CF_reportable": reportable_by_omission[variant_id],
                        }
                        for variant_id in variant_ids
                    },
                    "Delta_range": [
                        float(min(delta_by_omission.values())),
                        float(max(delta_by_omission.values())),
                    ],
                    "Delta_signs": sorted(set(omission_signs.values())),
                    "Delta_sign_instability_vs_full": any(
                        sign != full_sign for sign in omission_signs.values()
                    ),
                    "CF_reportable_count_leave_one_out": sum(reportable_by_omission.values()),
                    "CF_reportability_instability_vs_full": any(
                        flag != full_reportable for flag in reportable_by_omission.values()
                    ),
                    "CF_range_when_reportable": (
                        [float(min(finite_cfs)), float(max(finite_cfs))]
                        if finite_cfs
                        else None
                    ),
                }
            output[str(k)][null] = {
                "full_point_estimates": {
                    f"{cell[0]}::{cell[1]}": {
                        "CF": float(values["CF"]),
                        "Delta": float(values["Delta"]),
                        "r_ind": float(values["r_ind"]),
                        "CF_reportable": _cf_reportable(values, min_log_rind),
                    }
                    for cell, values in full.items()
                },
                "cells": cells,
            }
    return output


def run_sensitivity(
    task_records: list[TaskRecord],
    k_values: list[int],
    n_boot: int,
    bootstrap_seed: int,
    min_log_rind: float,
) -> dict[str, Any]:
    bootstrap_summary: dict[str, Any] = {}
    cluster_counts_by_unit = {
        cluster_unit: {
            model: len(
                {
                    (
                        record.task_id
                        if cluster_unit == "task_seed"
                        else (record.underlying_task_id or record.task_id)
                    )
                    for record in task_records
                    if record.backbone == model
                }
            )
            for model in sorted({record.backbone for record in task_records})
        }
        for cluster_unit in ("underlying_task", "task_seed")
    }
    for k in k_values:
        bootstrap_summary[str(k)] = {}
        for null in ("common", "position"):
            bootstrap_summary[str(k)][null] = {}
            for cluster_unit in ("underlying_task", "task_seed"):
                cluster_counts = cluster_counts_by_unit[cluster_unit]
                insufficient_models = {
                    model: count for model, count in cluster_counts.items() if count < 2
                }
                if insufficient_models:
                    bootstrap_summary[str(k)][null][cluster_unit] = {
                        "status": "unavailable",
                        "cluster_count_by_model": cluster_counts,
                        "reason": (
                            f"At least one model has fewer than two {cluster_unit} clusters "
                            "so a bootstrap variance estimate is unavailable."
                        ),
                        "insufficient_models": insufficient_models,
                        "n_boot_requested": n_boot,
                        "seed": bootstrap_seed,
                    }
                    continue
                values = bootstrap_cf(
                    task_records,
                    K=k,
                    null=null,
                    n_boot=n_boot,
                    seed=bootstrap_seed,
                    min_log_rind=min_log_rind,
                    cluster_unit=cluster_unit,
                )
                bootstrap_summary[str(k)][null][cluster_unit] = {
                    f"{language}::{model}": result
                    for (language, model), result in values.items()
                }
    return {
        "bootstrap_comparison": bootstrap_summary,
        "leave_one_task_variant_out": summarize_leave_one_task_out(
            task_records, k_values, min_log_rind=min_log_rind
        ),
    }


def _compare_main_point_estimates(
    task_records: list[TaskRecord], k_values: list[int], main_summary_path: Path
) -> dict[str, Any]:
    if not main_summary_path.exists():
        return {"status": "not_checked", "reason": f"Missing {main_summary_path}"}
    previous = json.loads(main_summary_path.read_text(encoding="utf-8"))
    checks = []
    for k in k_values:
        stored = previous.get("point_estimates", {}).get(str(k), {})
        computed = compute_cf(task_records, K=k, null="common")
        for cell, values in computed.items():
            key = f"{cell[0]}::{cell[1]}"
            old = stored.get(key)
            if old is None:
                checks.append({"k": k, "cell": key, "status": "missing_in_main_summary"})
                continue
            def field_matches(field: str) -> bool:
                old_value = old.get(field)
                new_value = values[field]
                if old_value is None:
                    return not np.isfinite(float(new_value))
                try:
                    old_number = float(old_value)
                except (TypeError, ValueError):
                    return False
                if not np.isfinite(old_number) or not np.isfinite(float(new_value)):
                    return not np.isfinite(old_number) and not np.isfinite(float(new_value))
                return bool(np.isclose(old_number, float(new_value), atol=1e-12))

            checks.append(
                {
                    "k": k,
                    "cell": key,
                    "status": "match"
                    if all(
                        field_matches(field)
                        for field in ("p", "T", "T_ind", "r_obs", "r_ind", "CF", "Delta")
                    )
                    else "mismatch",
                }
            )
    statuses = {item["status"] for item in checks}
    return {
        "status": "match" if statuses == {"match"} else "mismatch",
        "checked_values": len(checks),
        "checks": checks,
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _format_interval(values: Any, digits: int = 3) -> str:
    if values is None:
        return "not reportable"
    return f"[{values[0]:.{digits}f}, {values[1]:.{digits}f}]"


def _render_report(summary: dict[str, Any]) -> str:
    scope = summary["scope"]
    bootstrap_by_k = summary["bootstrap_comparison"]
    report_k = "10" if "10" in bootstrap_by_k else sorted(
        bootstrap_by_k, key=lambda value: int(value)
    )[0]
    lines = [
        "# BFCL Task-Cluster Sensitivity Report",
        "",
        "This offline analysis resamples saved BFCL task records. It does not add model calls or benchmark tasks.",
        "",
        f"- BFCL tasks: {scope['tasks']} ({', '.join(scope['task_ids'])})",
        f"- Languages: {', '.join(scope['languages'])}",
        f"- Models: {', '.join(scope['models'])}",
        f"- Full trajectories / isolated replays: {scope['full_runs']} / {scope['replays']}",
        f"- Bootstrap resamples and seed: {summary['settings']['n_boot']} / {summary['settings']['bootstrap_seed']}",
        "- Cluster counts per model: "
        + "; ".join(
            f"{model}: {count} variant-seed clusters, {scope['underlying_task_clusters_by_model'][model]} underlying scenario families"
            for model, count in scope["task_seed_clusters_by_model"].items()
        ),
        f"- Scenario-family grouping: {scope['scenario_family_to_task_variants']}",
        f"- Existing point-estimate check: {summary['point_estimate_invariance_check']['status']}",
        "",
        "Underlying-scenario bootstrap estimates are the primary uncertainty analysis when at least two scenario clusters are available. Task-seed bootstrap results are conditional sensitivity diagnostics over the selected task variants and seeds, not independent-scenario inference. A one-scenario design cannot estimate scenario-cluster variance. Bootstrap tail probabilities are not calibrated inferential p-values, so neither raw nor Holm-adjusted tails support significance claims. Variant holdouts report point-estimate sensitivity without significance tests.",
        "",
        "## K sweep summary",
        "",
        "The table counts how many analyzed non-English model cells change Delta sign or CF reportability after at least one selected task variant is removed.",
        "",
        "| K | Null | Delta sign changes | CF reportability changes |",
        "|---:|---|---:|---:|",
    ]
    for k, nulls in summary["leave_one_task_variant_out"].items():
        for null, results in nulls.items():
            cells = {
                key: value
                for key, value in results["cells"].items()
                if not key.startswith("EN::")
            }
            sign_count = sum(item["Delta_sign_instability_vs_full"] for item in cells.values())
            cf_count = sum(item["CF_reportability_instability_vs_full"] for item in cells.values())
            lines.append(f"| {k} | {null} | {sign_count}/{len(cells)} | {cf_count}/{len(cells)} |")

    lines.extend(["", f"## Cluster-unit comparison at K={report_k}", ""])
    lines.extend([
        "| Null | Cluster unit | Status | Language/model cells |",
        "|---|---|---|---:|",
    ])
    for null, units in bootstrap_by_k[report_k].items():
        for cluster_unit in ("underlying_task", "task_seed"):
            result = units[cluster_unit]
            if result.get("status") == "unavailable":
                status = f"unavailable: {result['reason']}"
                cell_count = 0
            else:
                status = "estimated"
                cell_count = len(result)
            lines.append(f"| {null} | {cluster_unit} | {status} | {cell_count} |")
    lines.extend([
        "",
        "Scenario-cluster intervals use the distinct underlying scenario IDs shown above. Task-seed intervals condition on the selected variants and seeds. Tail values in both groups remain directional diagnostics only.",
    ])

    common = bootstrap_by_k[report_k].get("common", {})
    for cluster_unit in ("underlying_task", "task_seed"):
        result = common.get(cluster_unit)
        if result is None:
            continue
        lines.extend(["", f"### {cluster_unit} estimates under the common null", ""])
        if result.get("status") == "unavailable":
            lines.append(
                f"Unavailable with cluster counts {result['cluster_count_by_model']}: {result['reason']}"
            )
            continue
        lines.extend([
            "| Cell | CF | Delta | CF 95% CI | Delta 95% CI | Raw tail diagnostic | Holm-adjusted tail diagnostic |",
            "|---|---:|---:|---|---|---:|---:|",
        ])
        for cell, values in sorted(result.items()):
            cf_text = f"{values['CF']:.3f}" if values.get("CF") is not None else "not reportable"
            raw_tail = values.get("bootstrap_tail_probability")
            holm_tail = values.get("holm_adjusted_bootstrap_tail_probability")
            lines.append(
                f"| {cell} | {cf_text} | {values['Delta']:.3f} | "
                f"{_format_interval(values.get('CF_CI'))} | "
                f"{_format_interval(values.get('Delta_CI'))} | "
                f"{raw_tail if raw_tail is not None else 'unavailable'} | "
                f"{holm_tail if holm_tail is not None else 'unavailable'} |"
            )

    loto_key = report_k
    if loto_key in summary["leave_one_task_variant_out"]:
        common_loto = summary["leave_one_task_variant_out"][loto_key].get("common", {})
        cells = common_loto.get("cells", {})
        lines.extend(["", f"## Leave-one-task-variant-out at K={report_k}", ""])
        for cell, loto in sorted(cells.items()):
            lines.append(
                f"- `{cell}`: Delta-sign changes={loto['Delta_sign_instability_vs_full']}; "
                f"CF-reportability changes={loto['CF_reportability_instability_vs_full']}; "
                f"Delta range={_format_interval(loto['Delta_range'])}; "
                f"reportable CF range={_format_interval(loto['CF_range_when_reportable'])}."
            )
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe scripts/run_task_sensitivity.py "
            f"--n-boot {summary['settings']['n_boot']} --bootstrap-seed {summary['settings']['bootstrap_seed']} "
            + ("--task-ids " + " ".join(summary["scope"]["task_ids"]) + " " if summary["scope"].get("task_ids") else "")
            + ("--input-artifact-prefix " + summary["settings"]["input_artifact_prefix"] if summary["settings"].get("input_artifact_prefix") else ""),
            "```",
            "",
            "The JSON records all cells, both nulls, results for both cluster units, point-estimate invariance checks, and each leave-one-task-variant-out estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.n_boot < 1:
        raise SystemExit("--n-boot must be positive")
    load_env_file(ROOT_ENV_FILE)
    model_keys = resolve_model_keys(args.models)
    language_codes = resolve_language_codes(args.language_codes)
    tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    tasks = select_bfcl_tasks(
        tasks,
        per_category_limit=args.per_category_limit if args.task_ids is None else None,
        task_ids=args.task_ids,
    )
    if not tasks:
        raise SystemExit("No BFCL tasks selected")
    full_runs, replays = collect_artifact_records(
        model_keys=model_keys,
        run_labels=args.run_labels,
        language_codes=language_codes,
        artifact_prefix=args.input_artifact_prefix,
    )
    records, pairing_diagnostics = build_task_records(
        full_runs,
        replays,
        tasks,
        model_keys,
        language_codes,
        args.run_labels,
    )
    selected_k = sorted(set(args.k_values))
    if any(k < 1 for k in selected_k):
        raise SystemExit("Every K value must be positive")

    sensitivity = run_sensitivity(
        records,
        k_values=selected_k,
        n_boot=args.n_boot,
        bootstrap_seed=args.bootstrap_seed,
        min_log_rind=args.min_log_rind,
    )
    summary = {
        "metadata": {
            "analysis": "scenario_cluster_diagnostics_and_leave_one_task_variant_out",
            "bootstrap_cluster_primary": "underlying_task",
            "bootstrap_cluster_sensitivity": "task_seed",
            "inference_status": "uncalibrated_tail_diagnostic",
            "nulls": ["common", "position"],
            "task_selection": (
                "explicit task IDs"
                if args.task_ids
                else f"first {args.per_category_limit} tasks per BFCL category"
            ),
            "min_log_rind": args.min_log_rind,
        },
        "settings": {
            "n_boot": args.n_boot,
            "bootstrap_seed": args.bootstrap_seed,
            "k_values": selected_k,
            "models": model_keys,
            "language_codes": language_codes,
            "run_labels": args.run_labels,
            "input_artifact_prefix": args.input_artifact_prefix,
            "task_selection": (
                "explicit_task_ids"
                if args.task_ids
                else f"first_{args.per_category_limit}_tasks_per_category"
            ),
        },
        "scope": {
            "tasks": len(tasks),
            "task_ids": [str(task.prompt_entry["id"]) for task in tasks],
            "languages": language_codes,
            "models": model_keys,
            "run_labels": args.run_labels,
            "full_runs": len(full_runs),
            "replays": len(replays),
            **pairing_diagnostics,
        },
        "point_estimate_invariance_check": _compare_main_point_estimates(
            records, selected_k, args.main_summary_path
        ),
        **sensitivity,
    }
    if summary["point_estimate_invariance_check"]["status"] == "mismatch":
        raise ValueError("Computed point estimates do not match existing main summary")

    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(
        json.dumps(_json_ready(summary), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(_render_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary": str(args.summary_path),
                "report": str(args.report_path),
                "full_runs": len(full_runs),
                "replays": len(replays),
                "point_estimate_check": summary["point_estimate_invariance_check"]["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
