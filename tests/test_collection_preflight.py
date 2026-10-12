from __future__ import annotations

import json
import pathlib
import sys
import unittest
from dataclasses import asdict
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
SCRIPTS_ROOT = ROOT / "scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_expansion_collection as collection  # noqa: E402
from multilingual_compounding import evaluation  # noqa: E402
from multilingual_compounding.bfcl_vendor import BFCLTask  # noqa: E402
from multilingual_compounding.evaluation import (  # noqa: E402
    _localization_fingerprint,
    _sha256_json,
    get_original_turn_texts,
    task_content_sha256,
)
from multilingual_compounding.localization import build_localization_artifact  # noqa: E402
from multilingual_compounding.settings import (  # noqa: E402
    BFCL_COMMIT,
    PILOT_MODELS,
    PILOT_TEST_CATEGORIES,
    language_pairs,
)


def valid_inputs() -> tuple[list[BFCLTask], dict, list[dict]]:
    horizons = [10] * 7 + [9] * 12 + [8]
    tasks: list[BFCLTask] = []
    categories = {category: {"selected": []} for category in PILOT_TEST_CATEGORIES}
    task_ids: list[str] = []
    category_order = [category for category in PILOT_TEST_CATEGORIES for _ in range(5)]
    for index, (category, horizon) in enumerate(zip(category_order, horizons)):
        task_id = f"{category}_{100 + index}"
        task_ids.append(task_id)
        tasks.append(BFCLTask(
            category=category,
            prompt_entry={
                "id": task_id,
                "question": [[{"role": "user", "content": "Find a record."}]],
                "function": [],
            },
            ground_truth=[["lookup_record()"] * horizon],
        ))
        categories[category]["selected"].append({"task_id": task_id, "gold_calls": horizon})

    horizon_counts = {str(value): horizons.count(value) for value in sorted(set(horizons))}
    models = {
        key: {
            "requested_model_name": str(PILOT_MODELS[key]["model_name"]),
            "run_labels": ["expansion_seed0", "expansion_seed1"],
        }
        for key in ("gemini", "claude_sonnet46")
    }
    plan = {
        "tasks": 20,
        "unique_scenarios": 20,
        "categories": categories,
        "task_ids": task_ids,
        "selected_horizon_distribution": horizon_counts,
        "full_trajectories_total_estimate": 640,
        "replay_requests_total_exact": 5952,
        "languages": [code for code, _name in language_pairs()],
        "models": models,
        "provider": "openrouter",
        "bfcl_commit": BFCL_COMMIT,
        "artifact_prefix": "preflight",
        "localization_prefix": "preflight",
    }

    language_names = dict(language_pairs(plan["languages"]))
    rows: list[dict] = []
    translation_model = "openai/gpt-4o-2024-08-06"
    for task in tasks:
        source_turns = get_original_turn_texts(task)
        source_hash = task_content_sha256(task)
        task_id = str(task.prompt_entry["id"])
        for language in plan["languages"]:
            target_turns = (
                list(source_turns)
                if language == "EN"
                else ["localized request" for _turn in source_turns]
            )
            row = asdict(build_localization_artifact(
                task_id=task_id,
                language_code=language,
                language_name=language_names[language],
                original_turns=source_turns,
                localized_turns=target_turns,
                backtranslated_turns=list(source_turns),
                ground_truth=task.ground_truth,
            ))
            row.update({
                "task_content_sha256": source_hash,
                "localization_fingerprint": _localization_fingerprint(
                    task,
                    language,
                    language_names[language],
                    translation_model,
                    plan["provider"],
                ),
                "translation_model": translation_model,
                "api_provider": plan["provider"],
                "human_review": {
                    "status": "pending",
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "",
                },
            })
            if language != "EN":
                row["ai_review"] = {
                    "status": "reviewed",
                    "source_task_sha256": source_hash,
                    "localized_turns_sha256": _sha256_json(target_turns),
                    "unresolved_issues": [],
                }
            rows.append(row)
    return tasks, plan, rows


class CollectionPreflightTests(unittest.TestCase):
    def _write_inputs(self, root: pathlib.Path, plan: dict, rows: list[dict]) -> pathlib.Path:
        plan_path = root / "analysis/bfcl/preflight_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        cache_path = root / "data/bfcl/localized_queries/preflight_bfcl_multiturn_localizations.jsonl"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        return plan_path

    def _run_main_rejecting_before_launch(
        self,
        root: pathlib.Path,
        plan_path: pathlib.Path,
        tasks: list[BFCLTask],
        expected_message: str,
    ) -> None:
        with (
            patch.object(collection, "ROOT", root),
            patch.object(collection, "load_bfcl_multiturn_tasks", return_value=tasks),
            patch.object(collection.subprocess, "run") as environment_check,
            patch.object(collection.subprocess, "Popen") as launch_job,
            patch.object(evaluation, "build_handler") as build_handler,
            patch("multilingual_compounding.localization.OpenAICompatibleTranslator") as translator,
            patch.object(sys, "argv", [str(ROOT / "scripts/run_expansion_collection.py"), "--plan", str(plan_path)]),
        ):
            with self.assertRaisesRegex(ValueError, expected_message):
                collection.main()
        environment_check.assert_not_called()
        launch_job.assert_not_called()
        build_handler.assert_not_called()
        translator.assert_not_called()

    def test_stale_source_hash_is_rejected_before_any_job_launch(self):
        tasks, plan, rows = valid_inputs()
        rows[1]["task_content_sha256"] = "0" * 64
        with TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan_path = self._write_inputs(root, plan, rows)
            self._run_main_rejecting_before_launch(
                root, plan_path, tasks, "Localization source hash mismatch"
            )

    def test_stale_translation_review_hash_is_rejected_before_any_job_launch(self):
        tasks, plan, rows = valid_inputs()
        row = next(row for row in rows if row["language_code"] != "EN")
        task = next(task for task in tasks if task.prompt_entry["id"] == row["task_id"])
        source_turns = get_original_turn_texts(task)
        updated = asdict(build_localization_artifact(
            task_id=row["task_id"],
            language_code=row["language_code"],
            language_name=row["language_name"],
            original_turns=source_turns,
            localized_turns=["a changed localized request"],
            backtranslated_turns=list(source_turns),
            ground_truth=task.ground_truth,
        ))
        row.update(updated)
        # Keep the old AI review hash. The translation text and derived cache
        # fields are internally consistent, but the review no longer covers it.
        with TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan_path = self._write_inputs(root, plan, rows)
            self._run_main_rejecting_before_launch(
                root, plan_path, tasks, "Localization review is absent, stale, or unresolved"
            )

    def test_misaligned_turns_are_rejected_before_any_job_launch(self):
        tasks, plan, rows = valid_inputs()
        row = next(row for row in rows if row["language_code"] != "EN")
        row["localized_turns"] = ["localized request", "unexpected extra turn"]
        with TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan_path = self._write_inputs(root, plan, rows)
            self._run_main_rejecting_before_launch(
                root, plan_path, tasks, "Localization row has invalid turn content"
            )

    def test_explicit_human_approval_is_accepted_by_the_same_offline_gate(self):
        tasks, plan, rows = valid_inputs()
        row = next(row for row in rows if row["language_code"] != "EN")
        row.pop("ai_review")
        row["human_review"] = {
            "status": "approved",
            "reviewer": "Researcher",
            "reviewed_at": "2026-10-12T00:00:00Z",
            "notes": "Reviewed the target text.",
        }
        with TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan_path = self._write_inputs(root, plan, rows)
            with patch.object(collection, "ROOT", root), patch.object(
                collection, "load_bfcl_multiturn_tasks", return_value=tasks
            ):
                _raw_plan, checked_plan, checked_tasks, _cache = collection.validate_collection_inputs(plan_path)
            self.assertEqual(checked_plan["task_ids"], plan["task_ids"])
            self.assertEqual(len(checked_tasks), 20)

    def test_human_approval_without_reviewer_identity_is_rejected_before_launch(self):
        tasks, plan, rows = valid_inputs()
        row = next(row for row in rows if row["language_code"] != "EN")
        row.pop("ai_review")
        row["human_review"] = {
            "status": "approved",
            "reviewer": "",
            "reviewed_at": "2026-10-12T00:00:00Z",
            "notes": "Reviewed the target text.",
        }
        with TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan_path = self._write_inputs(root, plan, rows)
            self._run_main_rejecting_before_launch(
                root, plan_path, tasks, "Localization review is absent, stale, or unresolved"
            )


if __name__ == "__main__":
    unittest.main()
