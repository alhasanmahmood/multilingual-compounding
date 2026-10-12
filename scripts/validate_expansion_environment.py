"""Preflight BFCL environments and gold-step replay cases without provider calls.

The check imports every environment class used by the fixed expansion plan,
constructs each task's initial environments, builds the same gold-prefix replay
cases used by evaluation, and checks that gold calls execute and self-replay.
It does not create model handlers or contact model/provider APIs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multilingual_compounding.bfcl_vendor import (  # noqa: E402
    BFCLTask,
    build_step_replay_cases,
    evaluate_step_replay,
    execute_multi_turn_func_call,
    load_bfcl_multiturn_tasks,
)
from multilingual_compounding.settings import PILOT_TEST_CATEGORIES  # noqa: E402

from bfcl_eval.constants.executable_backend_config import (  # noqa: E402
    CLASS_FILE_PATH_MAPPING,
    STATELESS_CLASSES,
)


def _long_context(task: BFCLTask) -> bool:
    return "long_context" in task.category or "composite" in task.category


def _exception(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc)[:2000],
    }


def _expected_task_counts(plan: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    expected: dict[str, int] = {}
    issues: list[str] = []
    task_ids = plan.get("task_ids")
    categories = plan.get("categories")
    if not isinstance(task_ids, list) or not all(isinstance(item, str) for item in task_ids):
        return {}, ["Plan task_ids must be a list of task ID strings."]
    if not isinstance(categories, dict):
        return {}, ["Plan categories must be an object with selected task records."]
    if len(task_ids) != len(set(task_ids)):
        issues.append("Plan contains duplicate task IDs.")
    if plan.get("tasks") != len(task_ids):
        issues.append(f"Plan tasks={plan.get('tasks')!r} does not match task_ids length {len(task_ids)}.")
    if set(categories) != set(PILOT_TEST_CATEGORIES):
        issues.append(
            "Plan category keys do not match the configured multi-turn categories: "
            f"{sorted(categories)}."
        )

    selected_ids: list[str] = []
    for category, category_info in categories.items():
        selected = category_info.get("selected", []) if isinstance(category_info, dict) else []
        if not isinstance(selected, list):
            issues.append(f"Plan category {category} has no selected-record list.")
            continue
        for item in selected:
            if not isinstance(item, dict) or not isinstance(item.get("task_id"), str):
                issues.append(f"Plan category {category} contains a malformed selected record.")
                continue
            task_id = item["task_id"]
            selected_ids.append(task_id)
            try:
                expected[task_id] = int(item["gold_calls"])
            except (KeyError, TypeError, ValueError):
                issues.append(f"Plan task {task_id} has an invalid gold_calls count.")
    if len(selected_ids) != len(set(selected_ids)) or set(selected_ids) != set(task_ids):
        issues.append("Plan task_ids content does not match the category-selected task records.")
    if len(task_ids) != 20:
        issues.append(f"Expected 20 selected tasks, found {len(task_ids)}.")
    if len(categories) != 4 or any(
        len(info.get("selected", [])) != 5
        for info in categories.values()
        if isinstance(info, dict)
    ):
        issues.append("Plan must select five tasks from each of four categories.")
    return expected, issues


def validate_expansion_environment(plan_path: Path) -> dict[str, Any]:
    """Return a JSON-safe report; do not perform model or provider API calls."""
    plan_path = plan_path.resolve()
    report: dict[str, Any] = {
        "status": "failed",
        "plan_path": plan_path.relative_to(ROOT).as_posix() if plan_path.is_relative_to(ROOT) else "<external-plan>",
        "provider_api_calls": 0,
        "provider_api_clients_created": False,
        "tasks": [],
        "classes": [],
        "issues": [],
    }
    try:
        plan_bytes = plan_path.read_bytes()
        plan = json.loads(plan_bytes.decode("utf-8-sig"))
    except Exception as exc:  # report parse/read failures in the JSON artifact
        report["issues"].append({"scope": "plan", **_exception(exc)})
        return report

    report.update(
        plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        bfcl_commit=plan.get("bfcl_commit"),
        artifact_prefix=plan.get("artifact_prefix"),
    )
    expected_counts, plan_issues = _expected_task_counts(plan)
    report["issues"].extend({"scope": "plan", "message": issue} for issue in plan_issues)

    try:
        tasks = load_bfcl_multiturn_tasks(list(PILOT_TEST_CATEGORIES))
    except Exception as exc:
        report["issues"].append({"scope": "dataset", **_exception(exc)})
        return report
    tasks_by_id = {str(task.prompt_entry.get("id")): task for task in tasks}
    report["available_bfcl_task_count"] = len(tasks)

    missing_tasks = [task_id for task_id in plan.get("task_ids", []) if task_id not in tasks_by_id]
    report["issues"].extend(
        {"scope": "dataset", "message": f"Selected task is missing from pinned BFCL data: {task_id}"}
        for task_id in missing_tasks
    )

    class_cache: dict[str, dict[str, Any]] = {}

    def load_environment_class(class_name: str) -> tuple[type | None, dict[str, Any]]:
        if class_name in class_cache:
            cached = class_cache[class_name]
            return cached.get("class"), cached["report"]
        class_report: dict[str, Any] = {"class_name": class_name}
        module_name = CLASS_FILE_PATH_MAPPING.get(class_name)
        class_report["module"] = module_name
        cls: type | None = None
        try:
            if module_name is None:
                raise KeyError(f"No BFCL backend module mapping for {class_name}.")
            module = importlib.import_module(module_name)
            candidate = getattr(module, class_name)
            if not isinstance(candidate, type):
                raise TypeError(f"{module_name}.{class_name} is not a class.")
            cls = candidate
            instance = cls()
            class_report["module_imported"] = True
            class_report["class_instantiated"] = True
            class_report["status"] = "passed"
        except Exception as exc:
            class_report["status"] = "failed"
            class_report["error"] = _exception(exc)
            report["issues"].append(
                {"scope": "environment_class", "class_name": class_name, **_exception(exc)}
            )
        class_cache[class_name] = {"class": cls, "report": class_report}
        return cls, class_report

    selected_ids = plan.get("task_ids", [])
    for task_id in selected_ids:
        task = tasks_by_id.get(task_id)
        if task is None:
            continue
        task_id = str(task_id)
        category = task.category
        task_issues: list[dict[str, Any]] = []
        involved_classes = task.prompt_entry.get("involved_classes", [])
        class_results: list[dict[str, Any]] = []
        for class_name in involved_classes:
            cls, class_report = load_environment_class(class_name)
            class_results.append({
                "class_name": class_name,
                "module": class_report.get("module"),
                "class_status": class_report.get("status", "failed"),
            })
            if cls is None:
                task_issues.append({
                    "stage": "class_import",
                    "class_name": class_name,
                    **class_report.get("error", {"message": "Environment class is unavailable."}),
                })
                continue
            try:
                instance = cls()
                if class_name not in STATELESS_CLASSES:
                    loader = getattr(instance, "_load_scenario", None)
                    if not callable(loader):
                        raise AttributeError(f"{class_name} has no callable _load_scenario method.")
                    initial_config = task.prompt_entry.get("initial_config", {}).get(class_name, {})
                    loader(copy.deepcopy(initial_config), long_context=_long_context(task))
            except Exception as exc:
                task_issues.append({"stage": "initial_environment", "class_name": class_name, **_exception(exc)})

        gold_turns = task.ground_truth
        flattened_gold = [call for turn in gold_turns for call in turn]
        expected_gold_calls = expected_counts.get(task_id)
        actual_gold_calls = len(flattened_gold)
        if expected_gold_calls is None:
            task_issues.append({"stage": "plan_alignment", "message": "Task has no planned gold_calls count."})
        elif expected_gold_calls != actual_gold_calls:
            task_issues.append({
                "stage": "plan_alignment",
                "message": f"Plan expects {expected_gold_calls} gold calls; BFCL data has {actual_gold_calls}.",
            })

        task_result: dict[str, Any] = {
            "task_id": task_id,
            "category": category,
            "involved_classes": class_results,
            "expected_gold_calls": expected_gold_calls,
            "gold_calls": actual_gold_calls,
            "initial_environments_checked": len(involved_classes),
            "replay_cases": 0,
            "gold_self_replays_passed": 0,
            "issues": task_issues,
        }

        cases = []
        try:
            cases = build_step_replay_cases(task)
            task_result["replay_cases"] = len(cases)
            if len(cases) != actual_gold_calls:
                task_issues.append({
                    "stage": "case_construction",
                    "message": f"Built {len(cases)} replay cases for {actual_gold_calls} gold calls.",
                })
        except Exception as exc:
            task_issues.append({"stage": "case_construction", **_exception(exc)})

        # Execute each gold turn in order to verify every gold call, including a
        # task's last call, and to compare the actual results with replay prefixes.
        gold_results: list[str] = []
        if not any(item["stage"] in {"class_import", "initial_environment"} for item in task_issues):
            try:
                for turn_index, turn_calls in enumerate(gold_turns):
                    results, _instances = execute_multi_turn_func_call(
                        func_call_list=list(turn_calls),
                        initial_config=copy.deepcopy(task.prompt_entry.get("initial_config", {})),
                        involved_classes=copy.deepcopy(involved_classes),
                        model_name="expansion_preflight_gold",
                        test_entry_id=task_id,
                        long_context=_long_context(task),
                        is_evaL_run=True,
                    )
                    if len(results) != len(turn_calls):
                        task_issues.append({
                            "stage": "gold_execution",
                            "turn_index": turn_index,
                            "message": f"Executed {len(results)} results for {len(turn_calls)} gold calls.",
                        })
                    gold_results.extend(results)
                    for call_index, result in enumerate(results):
                        if isinstance(result, str) and result.startswith("Error during execution:"):
                            task_issues.append({
                                "stage": "gold_execution",
                                "turn_index": turn_index,
                                "step_index": call_index,
                                "message": result[:1000],
                            })
            except Exception as exc:
                task_issues.append({"stage": "gold_execution", **_exception(exc)})

        for flat_index, case in enumerate(cases):
            expected_prefix = flattened_gold[:flat_index]
            if case.task_id != task_id or case.gold_call != flattened_gold[flat_index]:
                task_issues.append({
                    "stage": "case_alignment",
                    "step_index": flat_index,
                    "message": "Replay case task ID or gold call does not match BFCL ground truth order.",
                })
            if case.prefix_calls != expected_prefix:
                task_issues.append({
                    "stage": "case_alignment",
                    "step_index": flat_index,
                    "message": "Replay case prefix does not equal all preceding gold calls.",
                })
            if case.execution_task_id != f"{task_id}_turn{case.turn_index}_step{case.step_index}":
                task_issues.append({
                    "stage": "case_alignment",
                    "step_index": flat_index,
                    "message": "Replay case execution_task_id is not deterministic for its turn and step.",
                })
            if len(case.prefix_execution_results) != flat_index:
                task_issues.append({
                    "stage": "prefix_execution",
                    "step_index": flat_index,
                    "message": f"Prefix produced {len(case.prefix_execution_results)} results; expected {flat_index}.",
                })
            for prefix_index, result in enumerate(case.prefix_execution_results):
                if isinstance(result, str) and result.startswith("Error during execution:"):
                    task_issues.append({
                        "stage": "prefix_execution",
                        "step_index": flat_index,
                        "prefix_call_index": prefix_index,
                        "message": result[:1000],
                    })
                if prefix_index < len(gold_results) and result != gold_results[prefix_index]:
                    task_issues.append({
                        "stage": "prefix_execution",
                        "step_index": flat_index,
                        "prefix_call_index": prefix_index,
                        "message": "Gold-prefix execution result differs from the sequential gold execution result.",
                    })
            try:
                replay_result = evaluate_step_replay(case, case.gold_call)
                if replay_result.get("valid"):
                    task_result["gold_self_replays_passed"] += 1
                else:
                    task_issues.append({
                        "stage": "gold_self_replay",
                        "step_index": flat_index,
                        "error_type": replay_result.get("error_type"),
                        "details": replay_result.get("details"),
                        "message": "Replaying the exact gold call did not pass the isolated replay checker.",
                    })
            except Exception as exc:
                task_issues.append({"stage": "gold_self_replay", "step_index": flat_index, **_exception(exc)})

        task_result["status"] = "passed" if not task_issues else "failed"
        report["tasks"].append(task_result)

    report["classes"] = [class_cache[name]["report"] for name in sorted(class_cache)]
    report["expected_task_count"] = len(selected_ids)
    report["validated_task_count"] = len(report["tasks"])
    report["gold_call_count"] = sum(item["gold_calls"] for item in report["tasks"])
    report["replay_case_count"] = sum(item["replay_cases"] for item in report["tasks"])
    report["gold_self_replay_count"] = sum(item["gold_self_replays_passed"] for item in report["tasks"])
    report["issues"].extend(
        {"scope": "task", "task_id": task_result["task_id"], **issue}
        for task_result in report["tasks"]
        for issue in task_result["issues"]
    )
    report["status"] = "passed" if not report["issues"] else "failed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "analysis/bfcl/newstudy20261010_plan.json")
    parser.add_argument("--output", type=Path, help="JSON report path; defaults beside the plan artifacts.")
    args = parser.parse_args()
    report = validate_expansion_environment(args.plan)
    prefix = report.get("artifact_prefix") or "newstudy20261010"
    output = args.output or ROOT / "analysis/bfcl" / f"{prefix}_environment_validation.json"
    output = output.resolve()
    report["report_path"] = output.relative_to(ROOT).as_posix() if output.is_relative_to(ROOT) else "<external-report>"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "report_path": str(output),
        "validated_task_count": report.get("validated_task_count", 0),
        "gold_call_count": report.get("gold_call_count", 0),
        "replay_case_count": report.get("replay_case_count", 0),
        "gold_self_replay_count": report.get("gold_self_replay_count", 0),
        "issue_count": len(report.get("issues", [])),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
