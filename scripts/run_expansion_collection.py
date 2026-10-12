"""Collect the fixed expansion plan with isolated, resumable provider jobs.

Translations must already exist and have an explicit AI or human review record.
This script performs live API calls. It never purchases provider credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_completed_expansion import (  # noqa: E402
    validate_fixed_plan,
    validate_localization_records,
)
from multilingual_compounding.bfcl_vendor import BFCLTask, load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import read_jsonl
from multilingual_compounding.settings import PILOT_TEST_CATEGORIES  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_collection_inputs(
    plan_path: Path,
) -> tuple[bytes, dict[str, Any], list[BFCLTask], Path]:
    """Validate the pinned task plan and every reviewed localization offline.

    This gate runs before environment checks or provider jobs. It deliberately
    constructs no model or translation clients.
    """
    raw_plan = plan_path.read_bytes()
    plan = json.loads(raw_plan.decode("utf-8-sig"))
    if not isinstance(plan, dict):
        raise ValueError("Expansion plan must be a JSON object")

    for field in ("artifact_prefix", "localization_prefix"):
        value = plan.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
            raise ValueError(f"{field} must be a safe path label")

    all_tasks = load_bfcl_multiturn_tasks(list(PILOT_TEST_CATEGORIES))
    tasks = validate_fixed_plan(plan, all_tasks)

    cache = ROOT / "data/bfcl/localized_queries" / (
        f"{plan['localization_prefix']}_bfcl_multiturn_localizations.jsonl"
    )
    rows = read_jsonl(cache)
    # This verifies the exact task/language matrix, pinned source hashes, current
    # localization fingerprints, aligned turns, and a valid AI review or explicit
    # human approval before any provider job can be spawned.
    validate_localization_records(plan, tasks, rows)
    return raw_plan, plan, tasks, cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "analysis/bfcl/newstudy20261010_plan.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-hours", type=float, default=14)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not math.isfinite(args.timeout_hours) or args.timeout_hours <= 0:
        parser.error("workers must be 1-8 and timeout-hours must be positive")
    raw_plan, plan, selected_tasks, cache = validate_collection_inputs(args.plan)
    prefix = plan["artifact_prefix"]
    ids = [str(task.prompt_entry["id"]) for task in selected_tasks]
    subprocess.run([sys.executable, str(ROOT / 'scripts/validate_expansion_environment.py'),
                    '--plan', str(args.plan)], cwd=ROOT, check=True)
    log_dir = ROOT / "analysis/bfcl" / f"{prefix}_collection_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    state_path = ROOT / "analysis/bfcl" / f"{prefix}_collection_status.json"
    prefix_lock = FileLock(str(state_path) + ".lock")
    prefix_lock.acquire(timeout=0)
    if state_path.exists():
        history = log_dir / 'history'
        history.mkdir(exist_ok=True)
        shutil.copy2(state_path, history / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'))
    groups = [plan["languages"][i:i + 2] for i in range(0, len(plan["languages"]), 2)]
    # Interleave models so a long model does not leave the other waiting.
    jobs = []
    for group in groups:
        for model in plan["models"]:
            label = model + "_" + "_".join(group)
            command = [sys.executable, str(ROOT / "scripts/run_bfcl_evaluation.py"),
                       "--models", model, "--task-ids", *ids,
                       "--language-codes", *group,
                       "--run-labels", *plan["models"][model]["run_labels"],
                       "--artifact-prefix", prefix,
                       "--localization-prefix", plan["localization_prefix"],
                       "--provider", plan["provider"], "--collection-only", "--job-label", label]
            jobs.append({"label": label, "command": command, "status": "pending",
                         "log": str(log_dir / f"{label}.log")})
    state = {"started_at": now(), "plan_sha256": hashlib.sha256(raw_plan).hexdigest(),
             "localization_cache_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(),
             "environment_validation_sha256": hashlib.sha256((ROOT / f'analysis/bfcl/{prefix}_environment_validation.json').read_bytes()).hexdigest(),
             "code_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (ROOT / 'src/multilingual_compounding/evaluation.py',
                                       ROOT / 'src/multilingual_compounding/openrouter_handler.py',
                                       ROOT / 'scripts/run_expansion_collection.py')},
             "workers": args.workers, "timeout_hours": args.timeout_hours,
             "expected_full_trajectories": plan["full_trajectories_total_estimate"],
             "expected_replays": plan["replay_requests_total_exact"], "jobs": jobs}
    running = {}
    env = os.environ.copy()
    env["TRANSLATION_MODEL"] = "openai/gpt-4o-2024-08-06"
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.monotonic()
    last_report = -60.0
    try:
        while any(j["status"] in {"pending", "running"} for j in jobs):
            if time.monotonic() - started > args.timeout_hours * 3600:
                state["status"] = "hard_timeout"
                print("Hard timeout reached; preserving completed checkpoints.", flush=True)
                for process, handle in running.values():
                    process.terminate()
                    handle.close()
                break
            for job in jobs:
                if any(j['status'] == 'failed' for j in jobs):
                    break
                if job["status"] == "pending" and len(running) < args.workers:
                    handle = Path(job["log"]).open("a", encoding="utf-8")
                    handle.write(f"\nCollection invocation {now()}\n")
                    handle.flush()
                    process = subprocess.Popen(job["command"], cwd=ROOT, env=env,
                                               stdout=handle, stderr=subprocess.STDOUT,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    running[job["label"]] = (process, handle)
                    job.update(status="running", pid=process.pid, started_at=now())
                if job["status"] == "running":
                    process, handle = running[job["label"]]
                    code = process.poll()
                    if code is not None:
                        handle.close()
                        del running[job["label"]]
                        job.update(status="completed" if code == 0 else "failed",
                                   exit_code=code, finished_at=now())
                        print(f"Job {job['label']}: {job['status']} (exit {code})", flush=True)
            if any(j['status'] == 'failed' for j in jobs):
                state['status'] = 'failed'
                print('A job failed; stopping the queue and preserving checkpoints.', flush=True)
                break
            elapsed = time.monotonic() - started
            if elapsed - last_report >= 60:
                counts = {}
                for stage in ("runs", "isolated_replays"):
                    # A writer may be appending a large row at this instant.
                    # Count only newline-terminated checkpoints for monitoring.
                    counts[stage] = sum(
                        p.read_bytes().count(b'\n')
                        for p in (ROOT / "data/bfcl" / stage).glob(prefix + "_*.jsonl")
                    )
                state["completed_checkpoints"] = counts
                print(f"Elapsed {elapsed / 60:.1f} min; full {counts['runs']}/{state['expected_full_trajectories']}; replay {counts['isolated_replays']}/{state['expected_replays']}; running {len(running)}", flush=True)
                last_report = elapsed
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            if running or any(j["status"] == "pending" for j in jobs):
                time.sleep(10)
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        for process, handle in running.values():
            process.terminate()
            handle.close()
        raise
    finally:
        for process, handle in running.values():
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=30)
            if not handle.closed:
                handle.close()
        for job in jobs:
            if job['status'] in {'running', 'pending'}:
                job['status'] = 'cancelled'
                job['finished_at'] = now()
        state.setdefault("status", "completed" if all(j["status"] == "completed" for j in jobs) else "incomplete")
        state["finished_at"] = now()
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        prefix_lock.release()
    if state["status"] != "completed":
        sys.exit(1)


if __name__ == "__main__":
    main()
