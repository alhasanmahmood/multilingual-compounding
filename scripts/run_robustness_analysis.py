# pyright: reportMissingImports=false
from __future__ import annotations

import argparse
import json
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
    filter_records_by_localization,
    summarize_k_sensitivity,
    summarize_leave_one_language_out,
    summarize_localization_robustness,
    summarize_seed_variance,
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
    parser.add_argument("--run-labels", nargs="+", default=["pilot_seed0", "pilot_seed1", "expanded_seed0", "expanded_seed1"])
    parser.add_argument("--language-codes", nargs="+", default=None)
    parser.add_argument("--artifact-prefix", default="e6")
    parser.add_argument("--min-fidelity", type=int, default=3)
    return parser.parse_args()


def _artifact_name(prefix: str | None, basename: str) -> Path:
    if prefix:
        return SUMMARY_ROOT / f"{prefix}_{basename}"
    return SUMMARY_ROOT / basename


def main() -> None:
    args = parse_args()
    load_env_file(ROOT_ENV_FILE)
    model_keys = resolve_model_keys(args.models)
    tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    tasks = select_bfcl_tasks(tasks, task_limit=args.task_limit, per_category_limit=args.per_category_limit)
    full_run_records, replay_records = collect_artifact_records(
        model_keys=model_keys,
        run_labels=args.run_labels,
        language_codes=resolve_language_codes(args.language_codes),
    )
    localization_records = [
        json.loads(line)
        for line in (LOCALIZATION_ROOT / "bfcl_multiturn_localizations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

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
    filtered_cf_summary = summarize_cf(
        full_run_records=filtered_full,
        replay_records=filtered_replays,
        tasks=tasks,
    )

    summary = {
        "scope": {
            "models": model_keys,
            "run_labels": args.run_labels,
            "languages": sorted({record["language_code"] for record in filtered_full}),
            "full_runs": len(filtered_full),
            "replays": len(filtered_replays),
        },
        "localization": localization_summary,
        "k_sensitivity": summarize_k_sensitivity(filtered_cf_summary),
        "leave_one_language_out": summarize_leave_one_language_out(
            tasks=tasks,
            full_run_records=filtered_full,
            replay_records=filtered_replays,
        ),
        "seed_variance": summarize_seed_variance(
            tasks=tasks,
            full_run_records=filtered_full,
            replay_records=filtered_replays,
        ),
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
                "full_runs": len(filtered_full),
                "replays": len(filtered_replays),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
