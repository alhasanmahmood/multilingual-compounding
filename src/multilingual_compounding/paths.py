from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = REPO_ROOT / ".env"

VENDOR_ROOT = REPO_ROOT / "vendor" / "berkeley-function-call-leaderboard"
BFCL_PACKAGE_ROOT = VENDOR_ROOT / "bfcl_eval"

DATA_ROOT = REPO_ROOT / "data"
ANALYSIS_ROOT = REPO_ROOT / "analysis"
DOCS_ROOT = REPO_ROOT / "docs"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
TESTS_ROOT = REPO_ROOT / "tests"

BENCHMARK_ROOT = DATA_ROOT / "bfcl"
LOCALIZATION_ROOT = BENCHMARK_ROOT / "localized_queries"
RUNS_ROOT = BENCHMARK_ROOT / "runs"
REPLAY_ROOT = BENCHMARK_ROOT / "isolated_replays"
TRACE_ROOT = BENCHMARK_ROOT / "trace_db"
METADATA_ROOT = BENCHMARK_ROOT / "metadata"
SUMMARY_ROOT = ANALYSIS_ROOT / "bfcl"

# Backward-compatible aliases used by older call sites during the rename.
PILOT_ROOT = BENCHMARK_ROOT


def ensure_project_dirs() -> None:
    for path in [
        DATA_ROOT,
        ANALYSIS_ROOT,
        DOCS_ROOT,
        BENCHMARK_ROOT,
        LOCALIZATION_ROOT,
        RUNS_ROOT,
        REPLAY_ROOT,
        TRACE_ROOT,
        METADATA_ROOT,
        SUMMARY_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)
