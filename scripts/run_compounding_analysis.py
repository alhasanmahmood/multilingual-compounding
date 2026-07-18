from __future__ import annotations
# pyright: reportMissingImports=false

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.env import load_env_file  # noqa: E402
from multilingual_compounding.paths import ROOT_ENV_FILE  # noqa: E402
from multilingual_compounding.bfcl_vendor import load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import select_bfcl_tasks, summarize_existing_artifacts  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    DEFAULT_PILOT_MODEL_KEYS,
    PILOT_TEST_CATEGORIES,
    env_backbone_pool_model_keys,
    resolve_language_codes,
    resolve_model_keys,
    supported_model_keys,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize existing BFCL evaluation artifacts.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_PILOT_MODEL_KEYS),
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
    parser.add_argument("--per-category-limit", type=int, default=None)
    parser.add_argument("--run-labels", nargs="+", default=["seed0"])
    parser.add_argument("--language-codes", nargs="+", default=None)
    parser.add_argument("--artifact-prefix", default=None)
    return parser.parse_args()


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
    )
    result = summarize_existing_artifacts(
        tasks=tasks,
        model_keys=model_keys,
        language_codes=resolve_language_codes(args.language_codes),
        run_labels=args.run_labels,
        artifact_prefix=args.artifact_prefix,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
