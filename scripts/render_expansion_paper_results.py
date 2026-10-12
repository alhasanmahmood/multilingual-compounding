"""Render paper-ready artifacts from a completed offline BFCL expansion.

This helper consumes only the completion audit and summaries produced by
``scripts/analyze_completed_expansion.py``. It makes no API calls and does not
edit the manuscript source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFIX = "newstudy20261010_expansion"
PREFIX_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
K_VALUES = (8, 9, 10)
NULLS = ("common", "position")
CLUSTER_UNITS = ("underlying_task", "task_seed")


def _safe_prefix(prefix: str) -> str:
    if not PREFIX_RE.fullmatch(prefix):
        raise ValueError("Output prefix must contain 1 to 64 letters, digits, underscores, or hyphens.")
    return prefix


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON input {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_paths(prefix: str, analysis_dir: Path) -> dict[str, Path]:
    suffixes = {
        "audit": "collection_audit.json",
        "cf": "cf_summary.json",
        "cf_report": "report.md",
        "decomposition": "decomposition_summary.json",
        "decomposition_report": "decomposition_report.md",
        "robustness": "robustness_summary.json",
        "robustness_report": "robustness_report.md",
        "sensitivity": "task_sensitivity_summary.json",
        "sensitivity_report": "task_sensitivity_report.md",
        "overview": "overview.md",
    }
    return {key: analysis_dir / f"{prefix}_{suffix}" for key, suffix in suffixes.items()}


def _output_paths(prefix: str, analysis_dir: Path, paper_dir: Path) -> dict[str, Path]:
    return {
        "table": paper_dir / f"{prefix}_results_table.tex",
        "plot_data": paper_dir / f"{prefix}_cf_sensitivity_plot_data.csv",
        "note": analysis_dir / f"{prefix}_paper_results_note.md",
    }


def _require_input_bundle(paths: dict[str, Path]) -> None:
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Expansion results are not ready. The completion audit, all offline summaries, "
            "their reports, and the pipeline overview must exist. Missing: " + ", ".join(missing)
        )
    empty_reports = [
        str(paths[key])
        for key in ("cf_report", "decomposition_report", "robustness_report", "sensitivity_report", "overview")
        if not paths[key].read_text(encoding="utf-8").strip()
    ]
    if empty_reports:
        raise ValueError("Offline analysis reports are empty: " + ", ".join(empty_reports))


def _require_count(counts: dict[str, Any], name: str) -> int:
    value = counts.get(name)
    if type(value) is not int or value < 0:
        raise ValueError(f"Completion audit count {name!r} must be a nonnegative integer.")
    return value


def _validate_audit(audit: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if audit.get("status") != "complete":
        raise ValueError("Completion audit status is not 'complete'.")
    counts = audit.get("counts")
    validation = audit.get("validation")
    if not isinstance(counts, dict) or not isinstance(validation, dict):
        raise ValueError("Completion audit lacks counts or validation evidence.")
    if _require_count(counts, "tasks") != 20 or _require_count(counts, "unique_scenarios") != 20:
        raise ValueError("This renderer requires the completed 20-task, 20-scenario expansion.")
    if _require_count(counts, "categories") <= 0:
        raise ValueError("Completion audit reports no categories.")
    tasks_per_category = counts.get("tasks_per_category")
    if not isinstance(tasks_per_category, dict) or sum(tasks_per_category.values()) != counts["tasks"]:
        raise ValueError("Completion audit category counts do not sum to the task count.")

    required_true = (
        "all_expected_keys_present",
        "provider_identities_match",
        "source_and_target_hashes_match",
        "gold_call_positions_match",
    )
    if any(validation.get(key) is not True for key in required_true):
        raise ValueError("Completion audit did not pass all expected-key, identity, hash, and gold-position checks.")
    if validation.get("duplicate_keys") != 0 or validation.get("orphan_keys") != 0:
        raise ValueError("Completion audit contains duplicate or orphan keys.")
    localizations = validation.get("localizations")
    artifacts = validation.get("artifacts")
    if not isinstance(localizations, dict) or not isinstance(artifacts, dict):
        raise ValueError("Completion audit lacks localization or artifact validation details.")
    if localizations.get("rows") != counts.get("localization_rows"):
        raise ValueError("Localization count does not agree with the completion audit.")
    if artifacts.get("full_trajectories") != counts.get("full_trajectories"):
        raise ValueError("Full-trajectory count does not agree with the completion audit.")
    if artifacts.get("replays") != counts.get("replays"):
        raise ValueError("Replay count does not agree with the completion audit.")
    if artifacts.get("unique_task_scenarios") != counts.get("unique_scenarios"):
        raise ValueError("Validated scenario count does not agree with the completion audit.")
    positions = artifacts.get("gold_call_positions_per_task")
    if not isinstance(positions, dict) or len(positions) != counts["tasks"]:
        raise ValueError("Completion audit lacks the per-task gold-position map.")
    task_ids = [str(task_id) for task_id in positions]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("Completion audit repeats a task ID.")
    if sum(positions.values()) != counts.get("gold_call_positions"):
        raise ValueError("Per-task gold-position counts do not sum to the audit total.")
    for name in ("localization_rows", "gold_call_positions", "full_trajectories", "replays"):
        if _require_count(counts, name) <= 0:
            raise ValueError(f"Completion audit reports no {name}.")
    for name in ("languages", "models", "run_labels"):
        values = counts.get(name)
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError(f"Completion audit has an invalid {name} list.")
    return counts, task_ids


def _validate_scope(
    name: str,
    scope: Any,
    counts: dict[str, Any],
    task_ids: list[str],
    *,
    full_key: str,
    replay_key: str,
) -> None:
    if not isinstance(scope, dict):
        raise ValueError(f"{name} summary lacks a scope object.")
    if scope.get("tasks") != counts["tasks"]:
        raise ValueError(f"{name} summary task count differs from the completion audit.")
    if set(scope.get("task_ids", [])) != set(task_ids) or len(scope.get("task_ids", [])) != len(task_ids):
        raise ValueError(f"{name} summary task IDs differ from the completion audit.")
    for field in ("languages", "models", "run_labels"):
        if set(scope.get(field, [])) != set(counts[field]):
            raise ValueError(f"{name} summary {field} differ from the completion audit.")
    if scope.get(full_key) != counts["full_trajectories"]:
        raise ValueError(f"{name} summary trajectory count differs from the completion audit.")
    if scope.get(replay_key) != counts["replays"]:
        raise ValueError(f"{name} summary replay count differs from the completion audit.")


def _validate_inputs(
    audit: dict[str, Any],
    cf: dict[str, Any],
    decomposition: dict[str, Any],
    robustness: dict[str, Any],
    sensitivity: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    counts, task_ids = _validate_audit(audit)
    _validate_scope("CF", cf.get("scope"), counts, task_ids, full_key="task_trials", replay_key="replay_trials")
    _validate_scope(
        "Decomposition", decomposition.get("scope"), counts, task_ids,
        full_key="task_trials", replay_key="replay_trials",
    )
    _validate_scope(
        "Task sensitivity", sensitivity.get("scope"), counts, task_ids,
        full_key="full_runs", replay_key="replays",
    )

    robust_scope = robustness.get("scope")
    if not isinstance(robust_scope, dict):
        raise ValueError("Robustness summary lacks a scope object.")
    for count_key, audit_key in (("full_runs", "full_trajectories"), ("replays", "replays")):
        value = robust_scope.get(count_key)
        if type(value) is not int or not 0 <= value <= counts[audit_key]:
            raise ValueError(f"Robustness summary {count_key} exceeds the validated collection.")
    for field in ("languages", "models", "run_labels"):
        if not set(robust_scope.get(field, [])) <= set(counts[field]):
            raise ValueError(f"Robustness summary {field} exceed the validated collection.")

    cf_k = cf.get("k")
    if not isinstance(cf_k, dict) or cf_k.get("rounded_k") != 9:
        raise ValueError("CF summary does not identify K=9 as its main rounded horizon.")
    if not set(K_VALUES) <= {int(k) for k in cf_k.get("k_range", [])}:
        raise ValueError("CF summary does not contain the required K=8/9/10 sweep.")
    cf_point = cf.get("point_estimates")
    cf_bootstrap = cf.get("bootstrap")
    config = cf.get("bootstrap_config")
    if not isinstance(cf_point, dict) or not isinstance(cf_bootstrap, dict) or not isinstance(config, dict):
        raise ValueError("CF summary lacks point estimates or bootstrap results.")
    if config.get("cluster_unit") != "underlying_task":
        raise ValueError("Primary CF summary must use underlying-task scenario clusters.")
    if config.get("status") != "available":
        raise ValueError("Primary scenario-cluster CF bootstrap is unavailable.")
    if type(config.get("n_boot")) is not int or config["n_boot"] < 1:
        raise ValueError("Primary CF summary has an invalid bootstrap resample count.")
    expected_cells = {f"{language}::{model}" for language in counts["languages"] for model in counts["models"]}
    non_english_cells = {
        cell for cell in expected_cells
        if not cell.split("::", 1)[0].upper().startswith("EN")
    }

    metadata = sensitivity.get("metadata")
    settings = sensitivity.get("settings")
    scope = sensitivity.get("scope")
    if not isinstance(metadata, dict) or not isinstance(settings, dict) or not isinstance(scope, dict):
        raise ValueError("Task-sensitivity summary lacks metadata, settings, or scope.")
    if metadata.get("bootstrap_cluster_primary") != "underlying_task":
        raise ValueError("Sensitivity summary does not identify underlying-task primary clustering.")
    if metadata.get("bootstrap_cluster_sensitivity") != "task_seed":
        raise ValueError("Sensitivity summary does not include task-seed clustering.")
    if set(settings.get("k_values", [])) != set(K_VALUES):
        raise ValueError("Sensitivity summary must include exactly K=8, 9, and 10.")
    if settings.get("n_boot") != config.get("n_boot") or settings.get("bootstrap_seed") != config.get("seed"):
        raise ValueError("CF and task-sensitivity bootstrap settings do not match.")
    if settings.get("models") != counts["models"]:
        raise ValueError("Task-sensitivity model input order differs from the audited plan order.")
    invariance = sensitivity.get("point_estimate_invariance_check")
    if not isinstance(invariance, dict) or invariance.get("status") != "match":
        raise ValueError("Task-sensitivity point estimates did not pass the invariance check.")
    checks = invariance.get("checks")
    if not isinstance(checks, list) or not checks or any(row.get("status") != "match" for row in checks):
        raise ValueError("Task-sensitivity point-estimate check contains missing or mismatched cells.")
    if invariance.get("checked_values") != len(checks):
        raise ValueError("Task-sensitivity point-estimate check count is inconsistent.")

    family_map = scope.get("scenario_family_to_task_variants")
    if not isinstance(family_map, dict) or len(family_map) != counts["unique_scenarios"]:
        raise ValueError("Sensitivity summary does not contain all underlying scenario families.")
    variants: list[str] = []
    for family, family_variants in family_map.items():
        if not isinstance(family_variants, list) or len(family_variants) != 1:
            raise ValueError(f"Scenario family {family!r} is not one-to-one with a selected task variant.")
        variants.extend(str(item) for item in family_variants)
    if set(variants) != set(task_ids) or len(variants) != len(task_ids):
        raise ValueError("Scenario-family mapping does not match the audited task set one-to-one.")

    if not isinstance(sensitivity.get("bootstrap_comparison"), dict):
        raise ValueError("Sensitivity summary lacks bootstrap comparisons.")
    if not isinstance(sensitivity.get("leave_one_task_variant_out"), dict):
        raise ValueError("Sensitivity summary lacks leave-one-scenario-out results.")
    for k in K_VALUES:
        key = str(k)
        if key not in cf_point or key not in cf_bootstrap:
            raise ValueError(f"CF summary lacks K={k} results.")
        if set(cf_point[key]) != expected_cells:
            raise ValueError(f"CF summary K={k} point-estimate cells do not match the audited scope.")
        if key not in sensitivity["bootstrap_comparison"] or key not in sensitivity["leave_one_task_variant_out"]:
            raise ValueError(f"Sensitivity summary lacks K={k} results.")
        for null in NULLS:
            if null not in cf_bootstrap[key] or null not in sensitivity["bootstrap_comparison"][key]:
                raise ValueError(f"K={k} lacks {null}-null bootstrap results.")
            if set(cf_bootstrap[key][null]) != non_english_cells:
                raise ValueError(f"CF summary K={k}, {null} bootstrap cells do not match the audited non-English scope.")
            if null not in sensitivity["leave_one_task_variant_out"][key]:
                raise ValueError(f"K={k} lacks {null}-null leave-one-scenario results.")
            units = sensitivity["bootstrap_comparison"][key][null]
            if any(unit not in units for unit in CLUSTER_UNITS):
                raise ValueError(f"K={k}, {null} lacks one of the required cluster units.")
            loto = sensitivity["leave_one_task_variant_out"][key][null]
            if not isinstance(loto.get("cells"), dict) or not isinstance(loto.get("full_point_estimates"), dict):
                raise ValueError(f"K={k}, {null} leave-one-scenario results are incomplete.")
            if set(loto["full_point_estimates"]) != set(cf_point[key]):
                raise ValueError(f"K={k}, {null} sensitivity point-estimate cells differ from CF summary.")
            if set(loto["cells"]) != set(cf_point[key]):
                raise ValueError(f"K={k}, {null} leave-one-scenario cells differ from CF summary.")
            primary_boot = units["underlying_task"]
            if isinstance(primary_boot, dict) and primary_boot.get("status") != "unavailable":
                if set(primary_boot) != non_english_cells:
                    raise ValueError(f"K={k}, {null} scenario bootstrap cells do not match the audited non-English scope.")
            seed_boot = units["task_seed"]
            if isinstance(seed_boot, dict) and seed_boot.get("status") != "unavailable":
                if set(seed_boot) != non_english_cells:
                    raise ValueError(f"K={k}, {null} task-seed bootstrap cells do not match the audited non-English scope.")
            for cell in non_english_cells:
                _validate_point_pair(
                    cf_bootstrap[key][null][cell],
                    loto["full_point_estimates"][cell],
                    k=k,
                    null=null,
                    cell=cell,
                )
                _validate_bootstrap_metadata(
                    cf_bootstrap[key][null][cell],
                    cluster_unit="underlying_task",
                    cluster_counts=config["cluster_counts_by_backbone"],
                    n_boot=config["n_boot"],
                    seed=config["seed"],
                    cell=cell,
                    source="CF summary",
                )
                for cluster_unit, results in units.items():
                    if isinstance(results, dict) and results.get("status") == "unavailable":
                        continue
                    _validate_bootstrap_metadata(
                        results[cell],
                        cluster_unit=cluster_unit,
                        cluster_counts=(
                            scope["underlying_task_clusters_by_model"]
                            if cluster_unit == "underlying_task"
                            else scope["task_seed_clusters_by_model"]
                        ),
                        n_boot=settings["n_boot"],
                        seed=settings["bootstrap_seed"],
                        cell=cell,
                        source="task-sensitivity summary",
                    )
            for cell, result in loto["cells"].items():
                omissions = result.get("leave_one_task_variant_out")
                if not isinstance(omissions, dict) or set(omissions) != set(task_ids):
                    raise ValueError(
                        f"K={k}, {null}, {cell} lacks leave-one-out estimates for the complete task set."
                    )
            if null == "common":
                _validate_common_point_estimates(cf_point[key], loto["full_point_estimates"], k)

    if config.get("cluster_counts_by_backbone") != scope.get("underlying_task_clusters_by_model"):
        raise ValueError("CF and sensitivity scenario-cluster counts do not agree.")
    if any(value < 2 for value in config["cluster_counts_by_backbone"].values()):
        raise ValueError("At least one model has too few scenario clusters for scenario bootstrap intervals.")
    return counts, task_ids


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_common_point_estimates(main: dict[str, Any], sensitivity: dict[str, Any], k: int) -> None:
    for cell, values in main.items():
        other = sensitivity.get(cell)
        if not isinstance(other, dict):
            raise ValueError(f"K={k} common sensitivity estimate is missing {cell}.")
        for measure in ("CF", "Delta"):
            a = _finite(values.get(measure))
            b = _finite(other.get(measure))
            if a is None and b is None:
                continue
            if a is None or b is None or not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError(f"K={k} common {measure} changed between main and sensitivity summaries for {cell}.")


def _validate_point_pair(
    main: dict[str, Any],
    sensitivity: dict[str, Any],
    *,
    k: int,
    null: str,
    cell: str,
) -> None:
    for measure in ("CF", "Delta"):
        main_value = _finite(main.get(measure))
        sensitivity_value = _finite(sensitivity.get(measure))
        if main_value is None and sensitivity_value is None:
            continue
        if main_value is None or sensitivity_value is None or not math.isclose(
            main_value, sensitivity_value, rel_tol=1e-10, abs_tol=1e-10
        ):
            raise ValueError(f"K={k}, {null} {measure} point estimate differs between summaries for {cell}.")


def _validate_bootstrap_metadata(
    result: dict[str, Any],
    *,
    cluster_unit: str,
    cluster_counts: dict[str, int],
    n_boot: int,
    seed: int,
    cell: str,
    source: str,
) -> None:
    model = cell.split("::", 1)[1]
    if (
        result.get("cluster_unit") != cluster_unit
        or result.get("cluster_count") != cluster_counts.get(model)
        or result.get("n_boot") != n_boot
        or result.get("seed") != seed
    ):
        raise ValueError(f"{source} bootstrap metadata is inconsistent for {cell} ({cluster_unit}).")


def _interval(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None, None
    return _finite(value[0]), _finite(value[1])


def _format_number(value: Any, digits: int = 3) -> str:
    number = _finite(value)
    return "NA" if number is None else f"{number:.{digits}f}"


def _format_interval(value: Any, *, latex: bool = False) -> str:
    low, high = _interval(value)
    if low is None or high is None:
        return "unavailable" if not latex else "--"
    left, right = f"{low:.3f}", f"{high:.3f}"
    return f"[{left}, {right}]"


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _render_latex_table(prefix: str, cf: dict[str, Any], counts: dict[str, Any]) -> str:
    k = "9"
    points = cf["point_estimates"][k]
    boot = cf["bootstrap"][k]["common"]
    non_english = sorted(cell for cell in points if not cell.split("::", 1)[0].upper().startswith("EN"))
    languages = sorted({cell.split("::", 1)[0] for cell in non_english})
    models = sorted({cell.split("::", 1)[1] for cell in non_english})
    rows = [
        "% Generated from the completed offline expansion summaries. Review before manuscript use.",
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        (
            r"\caption{K=9 compounding estimates for "
            f"{len(languages)} non-English languages and {len(models)} models. "
            r"Intervals are 95\% scenario-cluster bootstrap percentile intervals.}"
        ),
        rf"\label{{tab:{_latex_escape(prefix)}_results}}",
        r"\begin{tabular}{llrrrr}",
        r"\hline",
        "Language & Model & $\\Delta$ & CF & $\\Delta$ interval & CF interval " + r"\\",
        r"\hline",
    ]
    for cell in non_english:
        language, model = cell.split("::", 1)
        values = points[cell]
        boot_values = boot.get(cell, {})
        cf_val = _finite(values.get("CF"))
        reportable = boot_values.get("CF_reportable")
        cf_text = _format_number(cf_val) if reportable is True and cf_val is not None else "NR"
        rows.append(
            f"{_latex_escape(language)} & {_latex_escape(model)} & {_format_number(values.get('Delta'))} & "
            f"{cf_text} & {_format_interval(boot_values.get('Delta_CI'), latex=True)} & "
            f"{_format_interval(boot_values.get('CF_CI'), latex=True)} \\\\"
        )
    rows.extend([r"\hline", r"\end{tabular}", r"\end{table}", ""])
    if counts["unique_scenarios"] < 2:
        raise ValueError("Cannot render scenario-cluster intervals with fewer than two scenarios.")
    return "\n".join(rows)


def _make_plot_csv(
    sensitivity: dict[str, Any],
    cf: dict[str, Any],
) -> tuple[str, dict[tuple[int, str, str], dict[str, Any]]]:
    scope = sensitivity["scope"]
    languages = [language for language in scope["languages"] if not str(language).upper().startswith("EN")]
    models = scope["models"]
    rows: list[dict[str, Any]] = []
    cell_status: dict[tuple[int, str, str], dict[str, Any]] = {}
    headers = [
        "K", "null", "cluster_unit", "language", "model", "Delta", "CF",
        "Delta_CI_low", "Delta_CI_high", "CF_CI_low", "CF_CI_high",
        "CF_reportable", "bootstrap_status", "bootstrap_source", "cluster_count", "n_boot", "seed",
        "unavailable_reason",
    ]
    for k in K_VALUES:
        key = str(k)
        for null in NULLS:
            loto = sensitivity["leave_one_task_variant_out"][key][null]["full_point_estimates"]
            expected_cells = {f"{language}::{model}" for language in languages for model in models}
            if not expected_cells <= set(loto):
                raise ValueError(f"K={k}, {null} point estimates are missing non-English model/language cells.")
            for cluster_unit in CLUSTER_UNITS:
                if cluster_unit == "underlying_task":
                    bootstrap = cf["bootstrap"][key][null]
                    source_name = "cf_summary"
                else:
                    bootstrap = sensitivity["bootstrap_comparison"][key][null][cluster_unit]
                    source_name = "task_sensitivity_summary"
                unavailable = isinstance(bootstrap, dict) and bootstrap.get("status") == "unavailable"
                for language in languages:
                    for model in models:
                        cell = f"{language}::{model}"
                        point = loto[cell]
                        if unavailable:
                            result = {}
                            status = "unavailable"
                            reason = str(bootstrap.get("reason", "Scenario or task-seed bootstrap unavailable."))
                            cluster_count = bootstrap.get("cluster_count_by_model", {}).get(model)
                            n_boot = bootstrap.get("n_boot_requested", sensitivity["settings"].get("n_boot"))
                            seed = bootstrap.get("seed", sensitivity["settings"].get("bootstrap_seed"))
                        else:
                            result = bootstrap.get(cell)
                            if not isinstance(result, dict):
                                raise ValueError(f"K={k}, {null}, {cluster_unit} bootstrap lacks {cell}.")
                            status = str(result.get("inference_status", "available"))
                            reason = str(result.get("unavailable_reason", ""))
                            cluster_count = result.get("cluster_count")
                            n_boot = result.get("n_boot", sensitivity["settings"].get("n_boot"))
                            seed = result.get("seed", sensitivity["settings"].get("bootstrap_seed"))
                        delta_ci = _interval(result.get("Delta_CI"))
                        cf_ci = _interval(result.get("CF_CI"))
                        record = {
                            "K": k,
                            "null": null,
                            "cluster_unit": cluster_unit,
                            "language": language,
                            "model": model,
                            "Delta": _finite(point.get("Delta")),
                            "CF": _finite(point.get("CF")),
                            "Delta_CI_low": delta_ci[0],
                            "Delta_CI_high": delta_ci[1],
                            "CF_CI_low": cf_ci[0],
                            "CF_CI_high": cf_ci[1],
                            "CF_reportable": point.get("CF_reportable"),
                            "bootstrap_status": status,
                            "bootstrap_source": source_name,
                            "cluster_count": cluster_count,
                            "n_boot": n_boot,
                            "seed": seed,
                            "unavailable_reason": reason,
                        }
                        rows.append(record)
                available = 0 if unavailable else len(expected_cells)
                cell_status[(k, null, cluster_unit)] = {
                    "available_cells": available,
                    "total_cells": len(expected_cells),
                    "status": "unavailable" if unavailable else "available",
                    "reason": str(bootstrap.get("reason", "")) if unavailable else "",
                }

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(value) for key, value in row.items()})
    return output.getvalue(), cell_status


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".12g")
    return value


def _decomposition_rows(decomposition: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    try:
        aggregates = decomposition["aggregates"]
        return [
            (label, aggregates[key]["replay"], aggregates[key]["trajectory"])
            for label, key in (("English", "english"), ("Non-English", "non_english"))
        ]
    except (KeyError, TypeError) as exc:
        raise ValueError("Decomposition summary lacks required replay and trajectory aggregates.") from exc


def _check_decomposition(decomposition: dict[str, Any]) -> None:
    for label, replay, trajectory in _decomposition_rows(decomposition):
        if type(replay.get("invalid_step_total")) is not int:
            raise ValueError(f"{label} decomposition invalid-step count is missing.")
        for key in ("stage_counts", "failure_type_counts"):
            mapping = replay.get(key)
            if not isinstance(mapping, dict) or any(type(value) is not int or value < 0 for value in mapping.values()):
                raise ValueError(f"{label} decomposition has invalid {key}.")
        for key in ("runs", "runs_with_detour"):
            if type(trajectory.get(key)) is not int:
                raise ValueError(f"{label} decomposition trajectory count {key} is missing.")


def _sign(value: Any) -> int:
    number = _finite(value)
    if number is None or number == 0:
        return 0
    return 1 if number > 0 else -1


def _leave_one_scenario_summary(sensitivity: dict[str, Any], k: int = 9) -> dict[str, Any]:
    loto = sensitivity["leave_one_task_variant_out"][str(k)]["common"]
    cells = loto["cells"]
    variant_to_family = {
        str(variant): str(family)
        for family, variants in sensitivity["scope"]["scenario_family_to_task_variants"].items()
        for variant in variants
    }
    non_english = {cell: value for cell, value in cells.items() if not cell.split("::", 1)[0].upper().startswith("EN")}
    affected: dict[str, dict[str, int]] = {}
    changed_sign_cells = set()
    changed_reportability_cells = set()
    for cell, values in non_english.items():
        full = values["full"]
        for variant_id, omitted in values["leave_one_task_variant_out"].items():
            scenario_id = variant_to_family.get(variant_id, variant_id)
            counts = affected.setdefault(scenario_id, {"delta_sign_cells": 0, "cf_reportability_cells": 0})
            if _sign(full.get("Delta")) != _sign(omitted.get("Delta")):
                counts["delta_sign_cells"] += 1
                changed_sign_cells.add(cell)
            if full.get("CF_reportable") != omitted.get("CF_reportable"):
                counts["cf_reportability_cells"] += 1
                changed_reportability_cells.add(cell)
    return {
        "cell_count": len(non_english),
        "changed_sign_cells": len(changed_sign_cells),
        "changed_reportability_cells": len(changed_reportability_cells),
        "affected_scenarios": {
            scenario: result
            for scenario, result in sorted(affected.items())
            if result["delta_sign_cells"] or result["cf_reportability_cells"]
        },
    }


def _cell_range(values: list[Any]) -> str:
    finite = [value for item in values if (value := _finite(item)) is not None]
    if not finite:
        return "unavailable"
    return f"[{min(finite):.3f}, {max(finite):.3f}]"


def _sensitivity_point_ranges(sensitivity: dict[str, Any]) -> list[tuple[int, str, int, str, str]]:
    output = []
    languages = [lang for lang in sensitivity["scope"]["languages"] if not str(lang).upper().startswith("EN")]
    models = sensitivity["scope"]["models"]
    for k in K_VALUES:
        for null in NULLS:
            points = sensitivity["leave_one_task_variant_out"][str(k)][null]["full_point_estimates"]
            cells = [points[f"{lang}::{model}"] for lang in languages for model in models]
            reportable_cf = [row.get("CF") for row in cells if row.get("CF_reportable") is True]
            delta_range = _cell_range([row.get("Delta") for row in cells])
            cf_range = _cell_range(reportable_cf)
            reportable_count = sum(row.get("CF_reportable") is True for row in cells)
            output.append((k, null, reportable_count, delta_range, cf_range))
    return output


def _render_note(
    prefix: str,
    paths: dict[str, Path],
    input_paths: dict[str, Path],
    audit: dict[str, Any],
    cf: dict[str, Any],
    decomposition: dict[str, Any],
    robustness: dict[str, Any],
    sensitivity: dict[str, Any],
    counts: dict[str, Any],
    task_ids: list[str],
    cell_status: dict[tuple[int, str, str], dict[str, Any]],
) -> str:
    del robustness  # Its scope is validated, while this note reports primary E3 and E4 findings.
    config = cf["bootstrap_config"]
    selected = cf["point_estimates"]["9"]
    boot = cf["bootstrap"]["9"]["common"]
    non_english = sorted(cell for cell in selected if not cell.split("::", 1)[0].upper().startswith("EN"))
    loo = _leave_one_scenario_summary(sensitivity, 9)
    clusters = config["cluster_counts_by_backbone"]
    task_seed_clusters = sensitivity["scope"]["task_seed_clusters_by_model"]
    main_model_order = list(counts["models"])
    sensitivity_draw_order = sorted(sensitivity["settings"]["models"])
    lines = [
        f"# Offline manuscript results for `{prefix}`",
        "",
        "Generated from the passed completion audit and the completed offline summary bundle. This helper made no API calls and did not edit the manuscript source.",
        "",
        "## Validated collection counts",
        "",
        "| Quantity | Observed count |",
        "|---|---:|",
        f"| Selected tasks | {counts['tasks']} |",
        f"| Unique scenarios | {counts['unique_scenarios']} |",
        f"| Categories | {counts['categories']} |",
        f"| Tasks by category | `{json.dumps(counts['tasks_per_category'], sort_keys=True)}` |",
        f"| Languages | {len(counts['languages'])} ({', '.join(counts['languages'])}) |",
        f"| Model backbones | {len(counts['models'])} ({', '.join(counts['models'])}) |",
        f"| Run labels | {len(counts['run_labels'])} ({', '.join(counts['run_labels'])}) |",
        f"| Localization rows checked | {counts['localization_rows']} |",
        f"| Gold-call positions | {counts['gold_call_positions']} |",
        f"| Full trajectories | {counts['full_trajectories']} |",
        f"| Isolated replays | {counts['replays']} |",
        "",
        f"The offline summaries cover the same {len(task_ids)} task IDs, languages, backbones, run labels, trajectories, and replay rows. The main CF summary reports K={cf['k']['rounded_k']} from a mean horizon of {_format_number(cf['k']['mean_k'], 2)}.",
        "",
        "## K=9 main estimates under the common null",
        "",
        "The LaTeX table contains the per-cell estimates. CF is marked NR when the summary marks it non-reportable. The reported 95% intervals use the 2.5th and 97.5th bootstrap percentiles over the selected underlying scenarios.",
        "",
        "| Language | Model | Delta | CF | Delta interval | CF interval | CF reportable |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for cell in non_english:
        language, model = cell.split("::", 1)
        point, interval = selected[cell], boot.get(cell, {})
        reportable = interval.get("CF_reportable")
        cf_value = _format_number(point.get("CF")) if reportable is True else "NR"
        lines.append(
            f"| {language} | {model} | {_format_number(point.get('Delta'))} | {cf_value} | "
            f"{_format_interval(interval.get('Delta_CI'))} | {_format_interval(interval.get('CF_CI'))} | {reportable} |"
        )
    lines.extend([
        "",
        f"Primary bootstrap settings: {config['n_boot']} resamples, seed {config['seed']}, cluster unit `{config['cluster_unit']}`. Scenario clusters by backbone: `{json.dumps(clusters, sort_keys=True)}`.",
        "",
        "## K and null sensitivity",
        "",
        "The point ranges below summarize the non-English model/language cells for each K and null. Per-cell point estimates and both underlying-task and task-seed bootstrap intervals are in the accompanying CSV. These ranges summarize cells, not a population-level effect.",
        "",
        "| K | Null | CF-reportable cells | Delta range across cells | CF range among reportable cells | Underlying-task bootstrap cells | Task-seed bootstrap cells |",
        "|---:|---|---:|---|---|---:|---:|",
    ])
    for k, null, reportable_count, delta_range, cf_range in _sensitivity_point_ranges(sensitivity):
        primary = cell_status[(k, null, "underlying_task")]
        seed = cell_status[(k, null, "task_seed")]
        primary_text = f"{primary['available_cells']}/{primary['total_cells']} ({primary['status']})"
        seed_text = f"{seed['available_cells']}/{seed['total_cells']} ({seed['status']})"
        lines.append(f"| {k} | {null} | {reportable_count} | {delta_range} | {cf_range} | {primary_text} | {seed_text} |")
    lines.extend([
        "",
        f"Underlying-task interval rows use the primary CF summary; task-seed rows use the task-sensitivity summary. Both summaries record the same resample count and seed. The main CF records follow plan/CLI model order {', '.join(main_model_order)}, while sensitivity sorts the task/model tuples, consuming backbone draws in {', '.join(sensitivity_draw_order)} order. The bootstrap_cf function advances one seeded RNG across backbones in record insertion order, so a shared seed does not guarantee the same per-backbone resamples. The reported intervals are therefore sourced and labeled separately, not presented as identical across summaries. Underlying-task intervals describe variability across this selected scenario set, not confirmatory population inference. Task-seed intervals are conditional on selected tasks and seeds. Bootstrap tail values are uncalibrated directional diagnostics, so this note makes no significance claim.",
        "",
        "## E4 decomposition counts",
        "",
        "Stage and failure-type maps below report exact invalid replay-step counts from the decomposition summary. Trajectory counts come from the same summary.",
        "",
        "| Group | Invalid replay steps | Stage counts | Failure-type counts | Trajectory runs | Runs with detour |",
        "|---|---:|---|---|---:|---:|",
    ])
    for label, replay, trajectory in _decomposition_rows(decomposition):
        stages = json.dumps(replay["stage_counts"], sort_keys=True, ensure_ascii=False)
        failures = json.dumps(replay["failure_type_counts"], sort_keys=True, ensure_ascii=False)
        lines.append(
            f"| {label} | {replay['invalid_step_total']} | `{stages}` | `{failures}` | "
            f"{trajectory['runs']} | {trajectory['runs_with_detour']} |"
        )
    lines.extend([
        "",
        "## Leave-one-scenario influence at K=9",
        "",
        f"Across {loo['cell_count']} non-English model/language cells, omitting at least one selected scenario changed the Delta sign in {loo['changed_sign_cells']} of {loo['cell_count']} cells and changed CF reportability in {loo['changed_reportability_cells']} of {loo['cell_count']} cells.",
        f"Scenarios that changed at least one cell: `{json.dumps(loo['affected_scenarios'], sort_keys=True)}`. Each audited task maps one-to-one to a scenario family. Task-seed clusters by backbone: `{json.dumps(task_seed_clusters, sort_keys=True)}`.",
        "",
        "These leave-one-scenario results are influence diagnostics over the selected scenarios. They are not significance tests.",
        "",
        "## Reproducibility and outputs",
        "",
        f"- Completion audit: `{input_paths['audit'].as_posix()}` (SHA-256 `{_sha256(input_paths['audit'])}`).",
        f"- CF summary: `{input_paths['cf'].as_posix()}` (SHA-256 `{_sha256(input_paths['cf'])}`).",
        f"- Decomposition summary: `{input_paths['decomposition'].as_posix()}` (SHA-256 `{_sha256(input_paths['decomposition'])}`).",
        f"- Robustness summary: `{input_paths['robustness'].as_posix()}` (SHA-256 `{_sha256(input_paths['robustness'])}`).",
        f"- Task-sensitivity summary: `{input_paths['sensitivity'].as_posix()}` (SHA-256 `{_sha256(input_paths['sensitivity'])}`).",
        f"- Plan SHA-256 in completion audit: `{audit.get('provenance', {}).get('plan_sha256', 'not recorded')}`.",
        f"- Raw artifact manifest SHA-256 in completion audit: `{audit.get('provenance', {}).get('raw_file_manifest_sha256', 'not recorded')}`.",
        f"- LaTeX table: `{paths['table'].as_posix()}`.",
        f"- K/null/cluster plot data: `{paths['plot_data'].as_posix()}`.",
        "",
        "Reproduce after the completion audit and offline summaries exist:",
        "",
        "```powershell",
        f".\\.venv\\Scripts\\python.exe scripts/render_expansion_paper_results.py --output-prefix {prefix}",
        "```",
        "",
        "The LaTeX table and CSV are standalone artifacts for review. They are not inserted into `paper/main.tex` automatically.",
        "",
    ])
    return "\n".join(lines)


def render_expansion_paper_results(
    output_prefix: str = DEFAULT_PREFIX,
    *,
    analysis_dir: Path | str | None = None,
    paper_dir: Path | str | None = None,
) -> dict[str, Path]:
    """Validate inputs and write a LaTeX table, sensitivity CSV, and result note."""
    prefix = _safe_prefix(output_prefix)
    analysis_path = Path(analysis_dir) if analysis_dir is not None else ROOT / "analysis" / "bfcl"
    paper_path = Path(paper_dir) if paper_dir is not None else ROOT / "paper" / "generated"
    inputs = _input_paths(prefix, analysis_path)
    _require_input_bundle(inputs)
    loaded = {
        key: _read_json(inputs[key])
        for key in ("audit", "cf", "decomposition", "robustness", "sensitivity")
    }
    counts, task_ids = _validate_inputs(
        loaded["audit"], loaded["cf"], loaded["decomposition"], loaded["robustness"], loaded["sensitivity"]
    )
    _check_decomposition(loaded["decomposition"])
    outputs = _output_paths(prefix, analysis_path, paper_path)
    existing = [str(path) for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite generated paper artifacts: " + ", ".join(existing))

    table = _render_latex_table(prefix, loaded["cf"], counts)
    plot_data, cell_status = _make_plot_csv(loaded["sensitivity"], loaded["cf"])
    note = _render_note(
        prefix, outputs, inputs, loaded["audit"], loaded["cf"], loaded["decomposition"],
        loaded["robustness"], loaded["sensitivity"], counts, task_ids, cell_status,
    )

    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    for name, content in (("table", table), ("plot_data", plot_data), ("note", note)):
        with outputs[name].open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", default=DEFAULT_PREFIX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        outputs = render_expansion_paper_results(args.output_prefix)
    except (FileNotFoundError, FileExistsError, ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit(f"Cannot render expansion results: {exc}") from exc
    print(json.dumps({key: str(path) for key, path in outputs.items()}, indent=2))


if __name__ == "__main__":
    main()
