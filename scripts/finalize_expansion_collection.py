"""Wait for the active collection, then run its gated offline analysis.

This one-shot companion never launches provider collection, changes prompts,
or purchases credit. Failed or incomplete collection stops finalization.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "newstudy20261010"
STATUS = ROOT / "analysis/bfcl" / f"{PREFIX}_collection_status.json"
PLAN = ROOT / "analysis/bfcl" / f"{PREFIX}_plan.json"
FINALIZATION = ROOT / "analysis/bfcl" / f"{PREFIX}_finalization_status.json"
TERMINAL_FAILURES = {"failed", "incomplete", "hard_timeout", "interrupted"}


def ready_or_failed(state: dict, expected_plan_sha256: str | None = None,
                    expected_started_at: str | None = None) -> bool:
    if expected_plan_sha256 is not None and state.get("plan_sha256") != expected_plan_sha256:
        raise RuntimeError("Collection status belongs to another plan.")
    if expected_started_at is not None and state.get("started_at") != expected_started_at:
        raise RuntimeError("Collection status belongs to another attempt.")
    status = state.get("status")
    if status in TERMINAL_FAILURES:
        raise RuntimeError(f"Collection ended with status {status}; saved checkpoints are preserved.")
    jobs = state.get("jobs", [])
    if any(job.get("status") == "failed" for job in jobs):
        raise RuntimeError("Collection job failed; analysis will not use the partial dataset.")
    if status == "completed":
        if len(jobs) != 8 or any(job.get("status") != "completed" for job in jobs):
            raise RuntimeError("Collection completion status contradicts its job matrix.")
        return True
    return False


def record(state: dict, **fields) -> None:
    state.update(fields, updated_at=datetime.now(timezone.utc).isoformat())
    temporary = FINALIZATION.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, FINALIZATION)


def preserve_previous_status() -> None:
    if FINALIZATION.exists():
        history = FINALIZATION.parent / f"{PREFIX}_finalization_history"
        history.mkdir(exist_ok=True)
        destination = history / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex}.json"
        destination.write_bytes(FINALIZATION.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-hours", type=float, default=15)
    parser.add_argument("--render-paper-artifacts", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.timeout_hours) or args.timeout_hours <= 0:
        raise SystemExit("Timeout must be positive.")
    lock = FileLock(str(FINALIZATION) + ".lock")
    with lock.acquire(timeout=0):
        plan_sha256 = hashlib.sha256(PLAN.read_bytes()).hexdigest()
        initial_collection = json.loads(STATUS.read_text(encoding="utf-8"))
        expected_started_at = initial_collection.get("started_at")
        if not expected_started_at:
            raise RuntimeError("Collection attempt has no start identity.")
        ready_or_failed(initial_collection, plan_sha256, expected_started_at)
        preserve_previous_status()
        state = {"status": "waiting_for_collection", "collection_status": str(STATUS),
                 "plan_sha256": plan_sha256, "collection_started_at": expected_started_at,
                 "pid": os.getpid(),
                 "manuscript_integration": "pending_manuscript_revision"}
        record(state)
        started = time.monotonic()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            while True:
                if time.monotonic() - started > args.timeout_hours * 3600:
                    raise TimeoutError("Collection finalization timeout; no partial-data analysis was run.")
                try:
                    collection = json.loads(STATUS.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError):
                    # The collector rewrites this monitoring file while running.
                    time.sleep(10)
                    continue
                if ready_or_failed(collection, plan_sha256, expected_started_at):
                    break
                time.sleep(10)
            if hashlib.sha256(PLAN.read_bytes()).hexdigest() != plan_sha256:
                raise RuntimeError("Active plan changed while waiting for collection.")
            record(state, status="validating_and_analyzing")
            subprocess.run([sys.executable, str(ROOT / "scripts/analyze_completed_expansion.py"),
                            "--run-analyses"], cwd=ROOT, env=env, check=True,
                           timeout=max(1, args.timeout_hours * 3600 - (time.monotonic() - started)))
            if args.render_paper_artifacts:
                record(state, status="rendering_paper_artifacts")
                subprocess.run([sys.executable, str(ROOT / "scripts/render_expansion_paper_results.py")],
                               cwd=ROOT, env=env, check=True,
                               timeout=max(1, args.timeout_hours * 3600 - (time.monotonic() - started)))
            record(state, status="completed", manuscript_integration="pending_manuscript_revision")
            print("Complete collection audited and analyzed; manuscript integration remains pending.", flush=True)
        except Exception as exc:
            record(state, status="failed", error=f"{type(exc).__name__}: {exc}")
            raise


if __name__ == "__main__":
    main()
