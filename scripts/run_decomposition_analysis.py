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
from multilingual_compounding.decomposition import build_decomposition_report, summarize_decomposition  # noqa: E402
from multilingual_compounding.env import load_env_file  # noqa: E402
from multilingual_compounding.paths import ROOT_ENV_FILE, SUMMARY_ROOT  # noqa: E402
from multilingual_compounding.evaluation import collect_artifact_records, select_bfcl_tasks  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    DEFAULT_PILOT_MODEL_KEYS,
    PILOT_TEST_CATEGORIES,
    env_backbone_pool_model_keys,
    resolve_language_codes,
    resolve_model_keys,
    supported_model_keys,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize E4 decomposition from existing BFCL artifacts.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini", "claude_sonnet46"],
        help=(
            "Backbones to summarize. Accepts model keys or known OpenRouter model ids. "
            f"Supported keys: {', '.join(supported_model_keys())}."
        ),
    )
    parser.add_argument(
        "--use-env-backbone-pool",
        action="store_true",
        help="Use the repo-wide OPENROUTER_LLM_BACKBONES pool instead of --models.",
    )
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--per-category-limit", type=int, default=1)
    parser.add_argument(
        "--task-ids",
        nargs="+",
        default=None,
        help="Exact BFCL task IDs to summarize. This overrides task and category limits.",
    )
    parser.add_argument("--run-labels", nargs="+", default=["pilot_seed0", "pilot_seed1", "expanded_seed0"])
    parser.add_argument("--language-codes", nargs="+", default=None)
    parser.add_argument("--artifact-prefix", default="e4")
    parser.add_argument(
        "--input-artifact-prefix",
        default=None,
        help="Prefix on source run and replay JSONL files. Output prefix is set separately.",
    )
    return parser.parse_args()


def _artifact_name(prefix: str | None, basename: str) -> Path:
    if prefix:
        return SUMMARY_ROOT / f"{prefix}_{basename}"
    return SUMMARY_ROOT / basename


def main() -> None:
    args = parse_args()
    load_env_file(ROOT_ENV_FILE)

    model_keys = (
        env_backbone_pool_model_keys() if args.use_env_backbone_pool else resolve_model_keys(args.models)
    )
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
        language_codes=resolve_language_codes(args.language_codes),
        artifact_prefix=args.input_artifact_prefix,
    )

    summary = summarize_decomposition(
        full_run_records=full_run_records,
        replay_records=replay_records,
        tasks=tasks,
    )
    summary_path = _artifact_name(args.artifact_prefix, "summary.json")
    report_path = _artifact_name(args.artifact_prefix, "report.md")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(build_decomposition_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary": str(summary_path),
                "report": str(report_path),
                "models": model_keys,
                "full_runs": len(full_run_records),
                "replays": len(replay_records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
