import pathlib
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_robustness_analysis as robustness_cli  # noqa: E402
from multilingual_compounding.bfcl_vendor import BFCLTask  # noqa: E402
from multilingual_compounding.evaluation import get_original_turn_texts, task_content_sha256  # noqa: E402
from multilingual_compounding.robustness import (  # noqa: E402
    _localized_turns_sha256,
    filter_to_complete_task_intersection,
    filter_records_by_localization,
    summarize_localization_robustness,
    summarize_seed_variance,
    validate_reviewed_localizations,
)


class RobustnessTests(unittest.TestCase):
    @staticmethod
    def _task(task_id):
        return BFCLTask(
            category="multi_turn_base",
            prompt_entry={
                "id": task_id,
                "question": [
                    [{"role": "user", "content": "Please book 'Flight123'."}],
                    [],
                ],
                "function": [],
            },
            ground_truth=[["book_flight(id='Flight123')"], ["confirm()"]],
        )

    @staticmethod
    def _localization(task, language, turns, review=None):
        record = {
            "task_id": task.prompt_entry["id"],
            "language_code": language,
            "localized_turns": turns,
            "human_review": {"status": "pending"},
        }
        if review is not None:
            record["ai_review"] = review
        return record

    def test_reviewed_policy_validates_current_hashes_alignment_and_source_quotes(self):
        task = self._task("multi_turn_base_1")
        source = get_original_turn_texts(task)
        target = ["Lütfen 'Flight123' için rezervasyon yapın.", ""]
        records = [
            self._localization(task, "EN", source),
            self._localization(task, "TR", target, {
                "status": "corrected",
                "unresolved_issues": [],
                "localized_turns_sha256": _localized_turns_sha256(target),
                "source_task_sha256": task_content_sha256(task),
            }),
        ]

        result = validate_reviewed_localizations(records, [task], ["EN", "TR"])
        self.assertEqual(result["validated_records"], 2)
        self.assertEqual(result["english_identity_rows"], 1)
        self.assertEqual(result["ai_review_status_counts"], {"corrected": 1})
        self.assertEqual(result["source_quoted_literals_checked"], 2)

        records[1]["localized_turns"][0] = "Lütfen bir uçuş için rezervasyon yapın."
        with self.assertRaisesRegex(ValueError, "Quoted source literal"):
            validate_reviewed_localizations(records, [task], ["EN", "TR"])

    def test_reviewed_policy_rejects_stale_ai_target_hash(self):
        task = self._task("multi_turn_base_2")
        target = ["Lütfen 'Flight123' için rezervasyon yapın.", ""]
        records = [
            self._localization(task, "EN", get_original_turn_texts(task)),
            self._localization(task, "TR", target, {
                "status": "reviewed",
                "unresolved_issues": [],
                "localized_turns_sha256": "0" * 64,
                "source_task_sha256": task_content_sha256(task),
            }),
        ]
        with self.assertRaisesRegex(ValueError, "target hash is stale"):
            validate_reviewed_localizations(records, [task], ["EN", "TR"])

    def test_complete_intersection_drops_unmatched_english_scenario(self):
        complete = self._task("multi_turn_base_3")
        english_only = self._task("multi_turn_base_4")
        tasks = [complete, english_only]
        full = []
        replays = []
        for task, languages in ((complete, ("EN", "TR")), (english_only, ("EN",))):
            for model in ("gemini", "claude_sonnet46"):
                for label in ("expansion_seed0", "expansion_seed1"):
                    for language in languages:
                        full.append({
                            "task_id": task.prompt_entry["id"],
                            "language_code": language,
                            "model_key": model,
                            "run_label": label,
                            "success": 1,
                        })
                        for turn_index, turn in enumerate(task.ground_truth):
                            for step_index, _call in enumerate(turn):
                                replays.append({
                                    "task_id": task.prompt_entry["id"],
                                    "language_code": language,
                                    "model_key": model,
                                    "run_label": label,
                                    "turn_index": turn_index,
                                    "step_index": step_index,
                                    "valid": 1,
                                })

        result = filter_to_complete_task_intersection(
            full,
            replays,
            tasks,
            ["gemini", "claude_sonnet46"],
            ["EN", "TR"],
            ["expansion_seed0", "expansion_seed1"],
        )
        self.assertEqual(result["task_ids"], [complete.prompt_entry["id"]])
        self.assertEqual({row["task_id"] for row in result["full_run_records"]}, {complete.prompt_entry["id"]})
        self.assertEqual(len(result["full_run_records"]), 8)
        self.assertEqual(len(result["replay_records"]), 16)
        self.assertIn(english_only.prompt_entry["id"], result["excluded_task_reasons"])

    def test_complete_intersection_supports_historical_model_specific_label_families(self):
        task = self._task("multi_turn_base_5")
        full = []
        replays = []
        labels_by_model = {
            "gemini": ["pilot_seed0", "pilot_seed1"],
            "claude_sonnet46": ["expanded_seed0", "expanded_seed1"],
        }
        for model, labels in labels_by_model.items():
            for language in ("EN", "TR"):
                for label in labels:
                    full.append({
                        "task_id": task.prompt_entry["id"],
                        "language_code": language,
                        "model_key": model,
                        "run_label": label,
                        "success": 1,
                    })
                    for turn_index, turn in enumerate(task.ground_truth):
                        for step_index, _call in enumerate(turn):
                            replays.append({
                                "task_id": task.prompt_entry["id"],
                                "language_code": language,
                                "model_key": model,
                                "run_label": label,
                                "turn_index": turn_index,
                                "step_index": step_index,
                                "valid": 1,
                            })

        result = filter_to_complete_task_intersection(
            full,
            replays,
            [task],
            ["gemini", "claude_sonnet46"],
            ["EN", "TR"],
            ["pilot_seed0", "pilot_seed1", "expanded_seed0", "expanded_seed1"],
        )

        self.assertEqual(result["task_ids"], [task.prompt_entry["id"]])
        self.assertEqual(result["run_labels_by_model"], labels_by_model)
        self.assertEqual(len(result["full_run_records"]), 8)
        self.assertEqual(len(result["replay_records"]), 16)

    def test_cli_selects_reviewed_policy_explicitly(self):
        with patch("sys.argv", ["run_robustness_analysis.py", "--localization-policy", "reviewed"]):
            self.assertEqual(robustness_cli.parse_args().localization_policy, "reviewed")

    def test_cli_keeps_legacy_localization_policy_as_default(self):
        with patch("sys.argv", ["run_robustness_analysis.py"]):
            self.assertEqual(robustness_cli.parse_args().localization_policy, "legacy")

    def test_seed_check_pools_task_subsets_by_actual_seed(self):
        full = [
            {"task_id": task, "language_code": lang, "run_label": f"{subset}_seed{seed}"}
            for task, subset in [("base", "pilot"), ("context", "expanded")]
            for seed in (0, 1)
            for lang in ("EN", "TR")
        ]
        calls = []

        def fake_summary(**kwargs):
            calls.append(kwargs)
            return {
                "k": {"rounded_k": 10},
                "bootstrap": {"10": {"common": {"TR::model": {
                    "p": 0.8, "T": 0.5, "Delta": 0.1, "CF": 0.9,
                }}}},
                "scope": {"task_trials": len(kwargs["full_run_records"])},
            }

        with patch("multilingual_compounding.robustness.summarize_cf", side_effect=fake_summary):
            summary = summarize_seed_variance([], full, full, n_boot=5000)
        self.assertEqual(set(summary["per_seed_summaries"]), {"0", "1"})
        self.assertEqual(summary["per_seed_summaries"]["0"]["scope"]["task_trials"], 4)
        self.assertEqual(len(calls), 6)
        seed0_labels = {r["run_label"] for r in calls[-2]["full_run_records"]}
        self.assertEqual(seed0_labels, {"pilot_seed0", "expanded_seed0"})
        self.assertTrue(all(call["cluster_unit"] == "underlying_task" for call in calls))

    def test_localization_filter_respects_fidelity_and_invariance(self):
        localization_records = [
            {
                "task_id": "task_1",
                "language_code": "EN",
                "machine_fidelity_rating": 5,
                "invariance_pass": True,
            },
            {
                "task_id": "task_1",
                "language_code": "TR",
                "machine_fidelity_rating": 2,
                "invariance_pass": True,
            },
            {
                "task_id": "task_2",
                "language_code": "AR",
                "machine_fidelity_rating": 4,
                "invariance_pass": False,
            },
        ]
        full_run_records = [
            {"task_id": "task_1", "language_code": "EN"},
            {"task_id": "task_1", "language_code": "TR"},
            {"task_id": "task_2", "language_code": "AR"},
        ]
        replay_records = list(full_run_records)
        filtered_full, filtered_replay = filter_records_by_localization(
            full_run_records,
            replay_records,
            localization_records,
            min_fidelity=3,
            require_invariance=True,
        )
        self.assertEqual(filtered_full, [{"task_id": "task_1", "language_code": "EN"}])
        self.assertEqual(filtered_replay, [{"task_id": "task_1", "language_code": "EN"}])

    def test_localization_summary_counts_kept_and_removed(self):
        localization_records = [
            {
                "task_id": "task_1",
                "language_code": "EN",
                "machine_fidelity_rating": 5,
                "invariance_pass": True,
            },
            {
                "task_id": "task_1",
                "language_code": "TR",
                "machine_fidelity_rating": 2,
                "invariance_pass": True,
            },
        ]
        summary = summarize_localization_robustness(localization_records, min_fidelity=3)
        self.assertEqual(summary["kept_records"], 1)
        self.assertEqual(summary["removed_records"], 1)
        self.assertAlmostEqual(summary["invariance_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
