# pyright: reportMissingImports=false
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.bfcl_vendor import load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.env import load_env_file  # noqa: E402
from multilingual_compounding.paths import LOCALIZATION_ROOT, ROOT_ENV_FILE, SUMMARY_ROOT  # noqa: E402
from multilingual_compounding.evaluation import collect_artifact_records, select_bfcl_tasks, summarize_cf  # noqa: E402
from multilingual_compounding.robustness import (  # noqa: E402
    build_robustness_report,
    filter_to_complete_task_intersection,
    filter_records_by_localization,
    summarize_k_sensitivity,
    summarize_leave_one_language_out,
    summarize_localization_robustness,
    summarize_seed_variance,
    validate_reviewed_localizations,
)
from multilingual_compounding.settings import (  # noqa: E402
    PILOT_TEST_CATEGORIES,
    resolve_language_codes,
    resolve_model_keys,
    supported_model_keys,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize BFCL E6 robustness from existing artifacts.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini", "claude_sonnet46"],
        help=(
            "Backbones to summarize. Accepts model keys or known OpenRouter model ids. "
            f"Supported keys: {', '.join(supported_model_keys())}."
        ),
    )
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--per-category-limit", type=int, default=1)
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Exact BFCL task IDs to summarize. This overrides task and category limits.",
    )
    parser.add_argument("--run-labels", nargs="+", default=["pilot_seed0", "pilot_seed1", "expanded_seed0", "expanded_seed1"])
    parser.add_argument("--language-codes", nargs="+", default=None)
    parser.add_argument("--artifact-prefix", default="e6")
    parser.add_argument(
        "--input-artifact-prefix",
        default=None,
        help="Prefix on source run and replay JSONL files. Output prefix is set separately.",
    )
    parser.add_argument(
        "--localization-prefix",
        default=None,
        help="Prefix on the localization JSONL cache used for this robustness analysis.",
    )
    parser.add_argument("--min-fidelity", type=int, default=3)
    parser.add_argument(
        "--localization-policy",
        choices=["legacy", "reviewed"],
        default="legacy",
        help="Use the historical machine-field filter or validate current AI-reviewed text and source literals.",
    )
    parser.add_argument("--n-boot", type=int, default=5_000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--cluster-unit", choices=["underlying_task", "task_seed"], default="underlying_task")
    return parser.parse_args()


def _artifact_name(prefix: str | None, basename: str) -> Path:
    if prefix:
        return SUMMARY_ROOT / f"{prefix}_{basename}"
    return SUMMARY_ROOT / basename


def _localization_path(prefix: str | None) -> Path:
    basename = "bfcl_multiturn_localizations.jsonl"
    if prefix is None:
        return LOCALIZATION_ROOT / basename
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", prefix):
        raise ValueError(
            "Localization prefixes must start with a letter or digit and contain "
            "only letters, digits, underscores, or hyphens (max 64 characters)."
        )
    return LOCALIZATION_ROOT / f"{prefix}_{basename}"


def _annotate_actual_scope(summary: dict, full_records: list[dict], replay_records: list[dict]) -> None:
    scope = summary.get("scope")
    if not isinstance(scope, dict):
        return
    task_ids = sorted({str(record["task_id"]) for record in full_records})
    scope["actual_task_ids"] = task_ids
    scope["actual_tasks"] = len(task_ids)
    scope["actual_full_runs"] = len(full_records)
    scope["actual_replays"] = len(replay_records)


def _reviewed_localization_summary(
    selected_localizations: list[dict],
    review_validation: dict,
    min_fidelity: int,
) -> dict:
    heuristic = summarize_localization_robustness(
        selected_localizations,
        min_fidelity=min_fidelity,
        require_invariance=True,
    )
    rating_counts = heuristic["rating_counts"]
    fidelity_passes = sum(
        count for rating, count in rating_counts.items() if int(rating) >= min_fidelity
    )
    return {
        "policy": "reviewed",
        "total_records": len(selected_localizations),
        "validated_records": review_validation["validated_records"],
        "retained_records": len(selected_localizations),
        "removed_records": 0,
        "english_identity_rows": review_validation["english_identity_rows"],
        "ai_review_status_counts": review_validation["ai_review_status_counts"],
        "human_review_status_counts": review_validation["human_review_status_counts"],
        "source_quoted_literals_checked": review_validation["source_quoted_literals_checked"],
        "automatic_heuristic_diagnostic": {
            "invariance_passes": heuristic["invariance_passes"],
            "invariance_rate": heuristic["invariance_rate"],
            "rating_counts": heuristic["rating_counts"],
            "min_fidelity": min_fidelity,
            "fidelity_at_or_above_min": fidelity_passes,
            "combined_heuristic_passes": heuristic["kept_records"],
            "combined_heuristic_removed": heuristic["removed_records"],
            "interpretation": "Diagnostic only; these fields do not gate AI-reviewed rows.",
        },
    }


def main() -> None:
    args = parse_args()
    load_env_file(ROOT_ENV_FILE)
    model_keys = resolve_model_keys(args.models)
    language_codes = resolve_language_codes(args.language_codes)
    tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    tasks = select_bfcl_tasks(
        tasks,
        task_limit=args.task_limit,
        per_category_limit=args.per_category_limit,
        task_ids=args.task_ids,
    )
    full_run_records, replay_records = collect_artifact_records(
        model_keys=model_keys,
        run_labels=args.run_labels,
        language_codes=language_codes,
        artifact_prefix=args.input_artifact_prefix,
    )
    localization_records = [
        json.loads(line)
        for line in _localization_path(args.localization_prefix).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if args.localization_policy == "reviewed":
        selected_task_ids = {str(task.prompt_entry["id"]) for task in tasks}
        selected_languages = set(language_codes)
        selected_localizations = [
            record
            for record in localization_records
            if str(record.get("task_id")) in selected_task_ids
            and str(record.get("language_code")) in selected_languages
        ]
        review_validation = validate_reviewed_localizations(
            selected_localizations,
            tasks,
            language_codes,
        )
        localization_summary = _reviewed_localization_summary(
            selected_localizations,
            review_validation,
            args.min_fidelity,
        )
        intersection = filter_to_complete_task_intersection(
            full_run_records,
            replay_records,
            tasks,
            model_keys,
            language_codes,
            args.run_labels,
        )
        filtered_full = intersection["full_run_records"]
        filtered_replays = intersection["replay_records"]
        analysis_tasks = intersection["tasks"]
        task_intersection = {
            "policy": "complete_intersection",
            "requested_task_ids": [str(task.prompt_entry["id"]) for task in tasks],
            "run_labels_by_model": intersection["run_labels_by_model"],
            "retained_task_ids": intersection["task_ids"],
            "excluded_task_reasons": intersection["excluded_task_reasons"],
        }
    else:
        localization_summary = summarize_localization_robustness(
            localization_records,
            min_fidelity=args.min_fidelity,
            require_invariance=True,
        )
        filtered_full, filtered_replays = filter_records_by_localization(
            full_run_records,
            replay_records,
            localization_records,
            min_fidelity=args.min_fidelity,
            require_invariance=True,
        )
        analysis_tasks = tasks
        task_intersection = {
            "policy": "legacy_pairwise_filter",
            "status": "not_applied_to_preserve_legacy_reproduction",
            "retained_task_ids": sorted({str(record["task_id"]) for record in filtered_full}),
        }

    actual_task_ids = sorted({str(record["task_id"]) for record in filtered_full})
    filtered_cf_summary = summarize_cf(
        full_run_records=filtered_full,
        replay_records=filtered_replays,
        tasks=analysis_tasks,
        n_boot=args.n_boot,
        bootstrap_seed=args.bootstrap_seed,
        cluster_unit=args.cluster_unit,
    )
    _annotate_actual_scope(filtered_cf_summary, filtered_full, filtered_replays)

    loo_summary = summarize_leave_one_language_out(
        tasks=analysis_tasks,
        full_run_records=filtered_full,
        replay_records=filtered_replays,
        n_boot=args.n_boot,
        bootstrap_seed=args.bootstrap_seed,
        cluster_unit=args.cluster_unit,
    )
    for language, values in loo_summary.items():
        held_full = [record for record in filtered_full if record["language_code"] != language]
        held_replays = [record for record in filtered_replays if record["language_code"] != language]
        values["actual_task_ids"] = sorted({str(record["task_id"]) for record in held_full})
        values["actual_tasks"] = len(values["actual_task_ids"])
        values["actual_full_runs"] = len(held_full)
        values["actual_replays"] = len(held_replays)

    seed_summary = summarize_seed_variance(
        tasks=analysis_tasks,
        full_run_records=filtered_full,
        replay_records=filtered_replays,
        n_boot=args.n_boot,
        bootstrap_seed=args.bootstrap_seed,
        cluster_unit=args.cluster_unit,
    )
    for label, sub_summary in seed_summary.get("per_label_summaries", {}).items():
        sub_full = [record for record in filtered_full if record["run_label"] == label]
        sub_replays = [record for record in filtered_replays if record["run_label"] == label]
        _annotate_actual_scope(sub_summary, sub_full, sub_replays)
    for _seed, sub_summary in seed_summary.get("per_seed_summaries", {}).items():
        labels = set(sub_summary.get("scope", {}).get("run_labels", []))
        sub_full = [record for record in filtered_full if record["run_label"] in labels]
        sub_replays = [record for record in filtered_replays if record["run_label"] in labels]
        _annotate_actual_scope(sub_summary, sub_full, sub_replays)

    summary = {
        "localization_policy": args.localization_policy,
        "task_intersection": task_intersection,
        "scope": {
            "models": model_keys,
            "run_labels": args.run_labels,
            "languages": sorted({record["language_code"] for record in filtered_full}),
            "actual_task_ids": actual_task_ids,
            "actual_tasks": len(actual_task_ids),
            "full_runs": len(filtered_full),
            "replays": len(filtered_replays),
        },
        "bootstrap_settings": {
            "n_boot": args.n_boot,
            "seed": args.bootstrap_seed,
            "cluster_unit": args.cluster_unit,
        },
        "localization": localization_summary,
        "k_sensitivity": summarize_k_sensitivity(filtered_cf_summary),
        "leave_one_language_out": loo_summary,
        "seed_variance": seed_summary,
        "environment_holdout": {
            "status": "not_run",
            "reason": "The current manuscript is explicitly BFCL-primary, so no second environment is in completed scope for a meaningful environment-holdout rerun.",
        },
    }

    summary_path = _artifact_name(args.artifact_prefix, "summary.json")
    report_path = _artifact_name(args.artifact_prefix, "report.md")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(build_robustness_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary": str(summary_path),
                "report": str(report_path),
                "models": model_keys,
                "localization_policy": args.localization_policy,
                "actual_tasks": len(actual_task_ids),
                "full_runs": len(filtered_full),
                "replays": len(filtered_replays),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
