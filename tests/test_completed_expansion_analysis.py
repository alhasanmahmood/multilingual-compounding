from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
SCRIPTS_ROOT = ROOT / "scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import analyze_completed_expansion as analysis  # noqa: E402
from multilingual_compounding.bfcl_vendor import BFCLTask  # noqa: E402
from multilingual_compounding.settings import PILOT_MODELS, PILOT_TEST_CATEGORIES  # noqa: E402


def valid_fixture():
    task = BFCLTask(
        category="multi_turn_base",
        prompt_entry={
            "id": "multi_turn_base_987654",
            "question": [[{"role": "user", "content": "Find a record."}]],
            "function": [],
        },
        ground_truth=[["lookup_record(name='Ada')", "save_record(id=7)" ]],
    )
    task_id = str(task.prompt_entry["id"])
    model_key = "gemini"
    model_id = PILOT_MODELS[model_key]["model_name"]
    run_label = "expansion_seed0"
    localization = {"localized_turns": ["Find a record."]}
    plan = {
        "provider": "openrouter",
        "languages": ["EN"],
        "models": {
            model_key: {
                "requested_model_name": model_id,
                "run_labels": [run_label],
            }
        },
    }
    query_hash = analysis._sha256_json({task_id: localization["localized_turns"]})
    common = {
        "task_id": task_id,
        "category": task.category,
        "language_code": "EN",
        "model_key": model_key,
        "run_label": run_label,
        "task_content_sha256": analysis.task_content_sha256(task),
        "localized_turns_sha256": analysis._sha256_json(localization["localized_turns"]),
        "api_provider": "openrouter",
        "requested_model_name": model_id,
        "provider_reported_model_ids": [model_id],
        "evaluation_fingerprint": analysis._evaluation_fingerprint(
            stage="full",
            tasks=[task],
            model_key=model_key,
            run_label=run_label,
            language_code="EN",
            api_provider="openrouter",
            localized_queries_sha256=query_hash,
        ),
    }
    full = [{**common, "success": 1}]
    replays = []
    for step_index, gold_call in enumerate(task.ground_truth[0]):
        replays.append({
            **common,
            "evaluation_fingerprint": analysis._evaluation_fingerprint(
                stage="replay",
                tasks=[task],
                model_key=model_key,
                run_label=run_label,
                language_code="EN",
                api_provider="openrouter",
                localized_queries_sha256=query_hash,
            ),
            "turn_index": 0,
            "step_index": step_index,
            "gold_call": gold_call,
            "valid": 1,
        })
    return plan, [task], {(task_id, "EN"): localization}, full, replays


class CompletedExpansionAnalysisTests(unittest.TestCase):
    def test_raw_manifest_digest_matches_frozen_digest_with_either_separator(self):
        audit = json.loads((ROOT / "analysis/bfcl/newstudy20261010_expansion_collection_audit.json").read_text())
        provenance = audit["provenance"]
        rows = provenance["raw_files"]
        portable = [dict(row, path=row["path"].replace("\\", "/")) for row in rows]
        self.assertEqual(analysis._raw_manifest_sha256(rows), provenance["raw_file_manifest_sha256"])
        self.assertEqual(analysis._raw_manifest_sha256(portable), provenance["raw_file_manifest_sha256"])

    def test_displayed_reproduction_command_does_not_expose_checkout(self):
        command = [sys.executable, str(ROOT / "scripts/run_task_sensitivity.py"),
                   "--summary-path", str(ROOT / "analysis/bfcl/reproduction.json")]
        displayed = analysis._portable_command(command)
        self.assertEqual(displayed, "python scripts/run_task_sensitivity.py --summary-path analysis/bfcl/reproduction.json")

    def test_valid_artifact_matrix_checks_exact_gold_positions_and_hashes(self):
        plan, tasks, localizations, full, replays = valid_fixture()
        result = analysis.validate_artifact_records(plan, tasks, localizations, full, replays)
        self.assertEqual(result["full_trajectories"], 1)
        self.assertEqual(result["replays"], 2)
        self.assertEqual(result["unique_task_scenarios"], 1)
        self.assertEqual(result["provider_reported_model_ids"]["gemini"], [PILOT_MODELS["gemini"]["model_name"]])

    def test_gate_rejects_duplicate_trajectory(self):
        plan, tasks, localizations, full, replays = valid_fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate artifact keys"):
            analysis.validate_artifact_records(plan, tasks, localizations, full + [copy.deepcopy(full[0])], replays)

    def test_gate_rejects_missing_replay_position(self):
        plan, tasks, localizations, full, replays = valid_fixture()
        with self.assertRaisesRegex(ValueError, "incomplete or contains orphan rows"):
            analysis.validate_artifact_records(plan, tasks, localizations, full, replays[:1])

    def test_gate_rejects_wrong_gold_call_at_position(self):
        plan, tasks, localizations, full, replays = valid_fixture()
        replays[0]["gold_call"] = "lookup_record(name='wrong')"
        with self.assertRaisesRegex(ValueError, "Replay gold call mismatch"):
            analysis.validate_artifact_records(plan, tasks, localizations, full, replays)

    def test_gate_rejects_stale_target_hash_and_provider_identity(self):
        plan, tasks, localizations, full, replays = valid_fixture()
        bad_full = copy.deepcopy(full)
        bad_full[0]["localized_turns_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "target hash does not match current cache"):
            analysis.validate_artifact_records(plan, tasks, localizations, bad_full, replays)

        bad_full = copy.deepcopy(full)
        bad_full[0]["provider_reported_model_ids"] = ["unexpected/model"]
        with self.assertRaisesRegex(ValueError, "Provider-reported model identity mismatch"):
            analysis.validate_artifact_records(plan, tasks, localizations, bad_full, replays)

    def test_gate_rejects_nonfixed_plan_shape(self):
        plan = {
            "tasks": 19,
            "categories": {name: {"selected": []} for name in PILOT_TEST_CATEGORIES},
            "task_ids": [],
        }
        with self.assertRaisesRegex(ValueError, "exactly 20 selected tasks"):
            analysis.validate_fixed_plan(plan, [])

    def test_gate_refuses_live_or_incomplete_collection_status(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state_path = state_dir / "newstudy_collection_status.json"
            state_path.write_text(json.dumps({
                "status": None,
                "jobs": [{"label": "gemini_EN_AR", "status": "running"}],
            }), encoding="utf-8")
            with patch.object(analysis, "SUMMARY_ROOT", state_dir):
                with self.assertRaisesRegex(ValueError, "Refusing to analyze live data"):
                    analysis._check_collection_state("newstudy")

    def test_stale_completed_plan_hash_refuses_before_raw_artifact_reads(self):
        with TemporaryDirectory() as directory:
            state_dir = Path(directory)
            plan_path = state_dir / "plan.json"
            plan_path.write_text(json.dumps({
                "artifact_prefix": "newstudy",
                "localization_prefix": "newstudy",
            }), encoding="utf-8")
            state_path = state_dir / "newstudy_collection_status.json"
            state_path.write_text(json.dumps({
                "status": "completed",
                "plan_sha256": hashlib.sha256(b"previous plan").hexdigest(),
                "jobs": [{"label": f"job_{index}", "status": "completed"} for index in range(8)],
            }), encoding="utf-8")

            with patch.object(analysis, "SUMMARY_ROOT", state_dir), \
                    patch.object(analysis, "_load_raw_stage") as load_raw_stage:
                with self.assertRaisesRegex(ValueError, "different plan hash"):
                    analysis.validate_completed_collection(plan_path)
                load_raw_stage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
