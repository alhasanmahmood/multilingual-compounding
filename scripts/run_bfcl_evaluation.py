from __future__ import annotations

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
from multilingual_compounding.evaluation import run_bfcl_evaluation  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    DEFAULT_PILOT_MODEL_KEYS,
    env_backbone_pool_model_keys,
    resolve_language_codes,
    resolve_model_keys,
    supported_model_keys,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BFCL multilingual evaluation.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_PILOT_MODEL_KEYS),
        help=(
            "Backbones to run. Accepts model keys or known OpenRouter model ids. "
            f"Supported keys: {', '.join(supported_model_keys())}."
        ),
    )
    parser.add_argument(
        "--use-env-backbone-pool",
        action="store_true",
        help="Use the repo-wide OPENROUTER_LLM_BACKBONES pool instead of --models.",
    )
    parser.add_argument(
        "--run-labels",
        nargs="+",
        default=["seed0"],
        help="Run labels to record in metadata. Use multiple labels if repeating runs.",
    )
    parser.add_argument(
        "--language-codes",
        nargs="+",
        default=None,
        help="Optional subset of languages to run, e.g. EN TR.",
    )
    parser.add_argument(
        "--task-limit",
        type=int,
        default=None,
        help="Optional cap on the number of BFCL tasks for smoke or pilot runs.",
    )
    parser.add_argument(
        "--per-category-limit",
        type=int,
        default=None,
        help="Optional balanced cap per BFCL multi-turn category.",
    )
    parser.add_argument(
        "--artifact-prefix",
        default=None,
        help="Optional prefix for metadata and summary filenames.",
    )
    parser.add_argument(
        "--skip-full-runs",
        action="store_true",
        help="Reuse existing full-run artifacts and execute only the replay stage.",
    )
    parser.add_argument(
        "--skip-replays",
        action="store_true",
        help="Reuse existing replay artifacts and execute only the full-run stage.",
    )
    parser.add_argument(
        "--force-localization",
        action="store_true",
        help="Rebuild localized queries even if cached artifacts already exist.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(ROOT_ENV_FILE)
    model_keys = (
        env_backbone_pool_model_keys() if args.use_env_backbone_pool else resolve_model_keys(args.models)
    )
    result = run_bfcl_evaluation(
        model_keys=model_keys,
        run_labels=args.run_labels,
        task_limit=args.task_limit,
        per_category_limit=args.per_category_limit,
        language_codes=resolve_language_codes(args.language_codes),
        artifact_prefix=args.artifact_prefix,
        execute_full_runs=not args.skip_full_runs,
        execute_replays=not args.skip_replays,
        force_localization=args.force_localization,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
