from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding import evaluation  # noqa: E402
from multilingual_compounding.bfcl_vendor import BFCLTask, StepReplayCase  # noqa: E402
from multilingual_compounding.settings import PILOT_MODELS, PILOT_TEST_CATEGORIES  # noqa: E402
from multilingual_compounding.localization import OpenAICompatibleTranslator, build_localization_artifact
from dataclasses import asdict


def make_task(task_id: str, *, category: str | None = None, content: str = "Run the tool") -> BFCLTask:
    task_category = category or task_id.rsplit("_", 1)[0]
    return BFCLTask(
        category=task_category,
        prompt_entry={
            "id": task_id,
            "question": [[{"role": "user", "content": content}]],
            "function": [],
        },
        ground_truth=[["tool(x=1)"]],
    )


class EvaluationCollectionTests(unittest.TestCase):
    def test_assistant_only_turns_preserve_indices_and_empty_content(self):
        translator = OpenAICompatibleTranslator(api_key="mock", base_url="https://mock.invalid")
        turns = ["first", "", "last"]
        with patch.object(translator, "_chat_json", return_value={"translations": ["uno", "ultimo"]}) as call:
            self.assertEqual(translator.translate_turns(turns, "Spanish"), ["uno", "", "ultimo"])
            self.assertIn('["first", "last"]', call.call_args.kwargs["user_prompt"])
        with patch.object(translator, "_chat_json", return_value={"translations": ["first", "last"]}):
            self.assertEqual(translator.backtranslate_turns(["uno", "", "ultimo"], "Spanish"), turns)
        with patch.object(translator, "_chat_json", return_value={"translations": ["uno"]}):
            with self.assertRaisesRegex(ValueError, "every nonempty"):
                translator.translate_turns(turns, "Spanish")
        task = make_task("multi_turn_base_4")
        task.prompt_entry["question"] = [[{"role": "user", "content": "first"}],
                                         [{"role": "assistant", "content": "reply"}],
                                         [{"role": "user", "content": "last"}]]
        row = asdict(build_localization_artifact(task.prompt_entry["id"], "ES", "Spanish",
                                                turns, ["uno", "", "ultimo"], turns, task.ground_truth))
        evaluation._validate_localization_record(row, task, "ES")
        row["localized_turns"][1] = "invented request"
        with self.assertRaisesRegex(ValueError, "invalid turn content"):
            evaluation._validate_localization_record(row, task, "ES")

    def test_localization_cache_fills_missing_keys_without_replacing_existing_rows(self):
        class FakeTranslator:
            instances = []

            def __init__(self, model, api_key, base_url):
                self.model = model
                self.provider_reported_model_ids = []
                self.translate_calls = 0
                self.backtranslate_calls = 0
                self.instances.append(self)

            def translate_turns(self, turns, _language_name):
                self.translate_calls += 1
                self.provider_reported_model_ids.append("openai/gpt-4o-2024-08-06")
                return [f"localized: {turn}" for turn in turns]

            def backtranslate_turns(self, turns, _language_name):
                self.backtranslate_calls += 1
                self.provider_reported_model_ids.append("openai/gpt-4o-2024-08-06")
                return [turn.removeprefix("localized: ") for turn in turns]

        task_a = make_task("multi_turn_base_1")
        task_b = make_task("multi_turn_base_2", content="Find the value")
        with tempfile.TemporaryDirectory() as directory:
            cache_root = Path(directory)
            with (
                patch.object(evaluation, "LOCALIZATION_ROOT", cache_root),
                patch.object(evaluation, "OpenAICompatibleTranslator", FakeTranslator),
                patch.object(evaluation, "_provider_credentials", return_value=("placeholder", "https://mock.invalid/v1")),
                patch.dict("os.environ", {"TRANSLATION_MODEL": "gpt-4o-2024-08-06"}),
            ):
                first = evaluation.localize_tasks(
                    [task_a], language_codes=["EN"], cache_prefix="newstudy"
                )
                self.assertEqual(len(first), 1)
                self.assertEqual(FakeTranslator.instances[-1].model, "openai/gpt-4o-2024-08-06")

                second = evaluation.localize_tasks(
                    [task_a, task_b],
                    language_codes=["EN", "TR"],
                    cache_prefix="newstudy",
                )

            self.assertEqual(len(second), 4)
            translator = FakeTranslator.instances[-1]
            self.assertEqual(translator.translate_calls, 2)
            self.assertEqual(translator.backtranslate_calls, 2)
            cache_path = cache_root / "newstudy_bfcl_multiturn_localizations.jsonl"
            rows = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({(row["task_id"], row["language_code"]) for row in rows}), 4)
            self.assertEqual(rows[0]["task_id"], "multi_turn_base_1")
            self.assertEqual(rows[0]["language_code"], "EN")
            self.assertEqual(rows[0]["human_review"]["status"], "pending")
            self.assertEqual(rows[-1]["provider_reported_model_ids"], ["openai/gpt-4o-2024-08-06"])
            self.assertNotEqual(
                evaluation._localization_cache_path("newstudy"),
                evaluation._localization_cache_path(),
            )

    def test_collection_only_and_human_review_fail_before_translator_creation(self):
        task = make_task("multi_turn_base_3")
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(evaluation, "LOCALIZATION_ROOT", Path(directory)),
                patch.object(evaluation, "OpenAICompatibleTranslator", side_effect=AssertionError("must not instantiate translator")),
                patch.object(evaluation, "_provider_credentials", side_effect=AssertionError("must not read credentials")),
            ):
                with self.assertRaises(FileNotFoundError):
                    evaluation.localize_tasks(
                        [task], language_codes=["EN"], cache_prefix="collection",
                        allow_generation=False,
                    )
                with self.assertRaisesRegex(ValueError, "Human localization review"):
                    evaluation.localize_tasks(
                        [task], language_codes=["EN"], cache_prefix="review",
                        require_human_review=True,
                    )

    def test_full_trajectory_checkpoints_resume_and_reject_changed_tasks(self):
        first = make_task("multi_turn_base_1")
        second = make_task("multi_turn_base_2")
        localization = [
            {"task_id": task.prompt_entry["id"], "language_code": "EN", "localized_turns": ["Run the tool"]}
            for task in (first, second)
        ]
        state = {"calls": 0, "failed_once": False}

        class FakeHandler:
            def __init__(self):
                self.api_key = None
                self.base_url = None
                self.provider_reported_model_ids = []

            def inference(self, _prompt_entry, **_kwargs):
                state["calls"] += 1
                if state["calls"] == 2 and not state["failed_once"]:
                    state["failed_once"] = True
                    raise RuntimeError("mock interruption")
                self.provider_reported_model_ids.append(PILOT_MODELS["gemini"]["model_name"])
                return [[{"mock": "tool call"}]], {"input_token_count": [10], "output_token_count": [1]}

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(evaluation, "RUNS_ROOT", Path(directory) / "runs"),
                patch.object(evaluation, "build_handler", side_effect=lambda *_a, **_k: FakeHandler()),
                patch.object(evaluation, "evaluate_multi_turn_entry", return_value={"valid": True}),
                patch.object(evaluation, "_provider_credentials", return_value=("placeholder", "https://mock.invalid/v1")),
            ):
                with self.assertRaisesRegex(RuntimeError, "mock interruption"):
                    evaluation.run_full_tasks(
                        tasks=[first, second], localization_records=localization,
                        models=["gemini"], run_labels=["seed0"], language_codes=["EN"],
                        artifact_prefix="resume", api_provider="openrouter",
                    )
                checkpoint = Path(directory) / "runs" / "resume_gemini_EN_seed0.jsonl"
                self.assertEqual(len(checkpoint.read_text(encoding="utf-8").splitlines()), 1)
                resumed = evaluation.run_full_tasks(
                    tasks=[first, second], localization_records=localization,
                    models=["gemini"], run_labels=["seed0"], language_codes=["EN"],
                    artifact_prefix="resume", api_provider="openrouter",
                )
                self.assertEqual(len(resumed), 2)
                self.assertEqual(state["calls"], 3)
                self.assertEqual(len(checkpoint.read_text(encoding="utf-8").splitlines()), 2)
                loaded = evaluation._load_complete_stage(
                    stage="full", tasks=[first, second], model_keys=["gemini"],
                    run_labels=["seed0"], language_codes=["EN"], artifact_prefix="resume",
                    api_provider="openrouter", localization_records=localization,
                )
                self.assertEqual(len(loaded), 2)
                self.assertEqual(state["calls"], 3)
                altered_localization = [dict(row) for row in localization]
                altered_localization[0]["localized_turns"] = ["Changed translation"]
                with self.assertRaisesRegex(ValueError, "does not match the requested dataset/settings"):
                    evaluation.run_full_tasks(
                        tasks=[first, second], localization_records=altered_localization,
                        models=["gemini"], run_labels=["seed0"], language_codes=["EN"],
                        artifact_prefix="resume", api_provider="openrouter",
                    )
                self.assertEqual(state["calls"], 3)
                with self.assertRaisesRegex(ValueError, "does not match the requested dataset/settings"):
                    evaluation.run_full_tasks(
                        tasks=[make_task("multi_turn_base_1", content="Changed source")],
                        localization_records=[localization[0]], models=["gemini"],
                        run_labels=["seed0"], language_codes=["EN"],
                        artifact_prefix="resume", api_provider="openrouter",
                    )

    def test_step_replays_checkpoint_each_result_and_resume_without_duplicates(self):
        task = make_task("multi_turn_base_1")
        localization = [{"task_id": task.prompt_entry["id"], "language_code": "EN", "localized_turns": ["Run the tool"]}]
        cases = [
            StepReplayCase(
                task_id=task.prompt_entry["id"],
                execution_task_id=f"exec-{step}",
                category=task.category,
                turn_index=0,
                step_index=step,
                current_turn_message="Run the tool",
                prefix_calls=[],
                gold_call=f"tool(x={step})",
                prefix_execution_results=[],
                prompt_entry=task.prompt_entry,
            )
            for step in (0, 1)
        ]
        state = {"calls": 0, "failed_once": False}

        class FakeHandler:
            api_key = None
            base_url = None
            provider_reported_model_ids: list[str] = []

        def fake_replay(_handler, *_args):
            state["calls"] += 1
            if state["calls"] == 2 and not state["failed_once"]:
                state["failed_once"] = True
                raise RuntimeError("mock replay interruption")
            _handler.provider_reported_model_ids.append(PILOT_MODELS["gemini"]["model_name"])
            return [[{"mock": "tool call"}]], {"input_token_count": [1], "output_token_count": [1]}

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(evaluation, "REPLAY_ROOT", Path(directory) / "replays"),
                patch.object(evaluation, "build_handler", side_effect=lambda *_a, **_k: FakeHandler()),
                patch.object(evaluation, "build_step_replay_cases", return_value=cases),
                patch.object(evaluation, "_run_step_replay_query", side_effect=fake_replay),
                patch.object(evaluation, "_extract_first_candidate_call", return_value="tool(x=0)"),
                patch.object(evaluation, "evaluate_step_replay", return_value={"valid": True}),
                patch.object(evaluation, "_provider_credentials", return_value=("placeholder", "https://mock.invalid/v1")),
            ):
                with self.assertRaisesRegex(RuntimeError, "mock replay interruption"):
                    evaluation.run_step_replays(
                        tasks=[task], localization_records=localization, models=["gemini"],
                        run_labels=["seed0"], language_codes=["EN"],
                        artifact_prefix="resume", api_provider="openrouter",
                    )
                checkpoint = Path(directory) / "replays" / "resume_gemini_EN_seed0.jsonl"
                self.assertEqual(len(checkpoint.read_text(encoding="utf-8").splitlines()), 1)
                resumed = evaluation.run_step_replays(
                    tasks=[task], localization_records=localization, models=["gemini"],
                    run_labels=["seed0"], language_codes=["EN"],
                    artifact_prefix="resume", api_provider="openrouter",
                )
                self.assertEqual(len(resumed), 2)
                self.assertEqual(state["calls"], 3)
                self.assertEqual(len(checkpoint.read_text(encoding="utf-8").splitlines()), 2)

    def test_summary_marks_single_scenario_bootstrap_unavailable_and_retains_task_seed(self):
        tasks = [
            make_task(f"{category}_0", category=category)
            for category in PILOT_TEST_CATEGORIES
        ]
        full = []
        replay = []
        for task in tasks:
            task_id = task.prompt_entry["id"]
            for run_label in ("seed0", "seed1"):
                for language in ("EN", "TR"):
                    full.append({
                        "task_id": task_id,
                        "language_code": language,
                        "model_key": "gemini",
                        "run_label": run_label,
                        "success": int(language == "EN"),
                    })
                    replay.append({
                        "task_id": task_id,
                        "language_code": language,
                        "model_key": "gemini",
                        "run_label": run_label,
                        "turn_index": 0,
                        "step_index": 0,
                        "valid": 1,
                    })

        unavailable = evaluation.summarize_cf(full, replay, tasks, n_boot=20, bootstrap_seed=7)
        self.assertEqual(unavailable["bootstrap_config"]["status"], "unavailable")
        self.assertEqual(unavailable["bootstrap_config"]["cluster_counts_by_backbone"], {"gemini": 1})
        unavailable_cell = unavailable["bootstrap"]["1"]["common"]["TR::gemini"]
        self.assertEqual(unavailable_cell["inference_status"], "unavailable_insufficient_clusters")
        self.assertIsNone(unavailable_cell["Delta_CI"])
        self.assertIsNone(unavailable_cell["CF_CI"])
        self.assertIsNone(unavailable_cell["p_holm"])
        self.assertIn("at least two underlying_task clusters", unavailable_cell["unavailable_reason"].lower())

        sensitivity = evaluation.summarize_cf(
            full, replay, tasks, n_boot=20, bootstrap_seed=7, cluster_unit="task_seed"
        )
        self.assertEqual(sensitivity["bootstrap_config"]["status"], "available")
        self.assertEqual(sensitivity["bootstrap_config"]["cluster_counts_by_backbone"], {"gemini": 8})
        self.assertEqual(
            sensitivity["bootstrap"]["1"]["common"]["TR::gemini"]["inference_status"],
            "uncalibrated_tail_diagnostic",
        )

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(evaluation, "SUMMARY_ROOT", Path(directory)):
                report_path = evaluation.write_analysis_report(unavailable, artifact_prefix="single")
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("uncalibrated directional diagnostics, not inferential p-values", report)
            self.assertIn("scenario-level bootstrap unavailable", report)

    def test_provider_model_mismatch_is_rejected(self):
        handler = SimpleNamespace(provider_reported_model_ids=["unexpected/model"])
        with self.assertRaisesRegex(RuntimeError, "unexpected model id"):
            evaluation._verify_provider_models(
                handler,
                PILOT_MODELS["gemini"]["model_name"],
                "gemini",
            )


if __name__ == "__main__":
    unittest.main()
