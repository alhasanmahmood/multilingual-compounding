import pathlib
import sys
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.bfcl_vendor import BFCLTask  # noqa: E402
from multilingual_compounding.decomposition import (  # noqa: E402
    _align_actual_trace,
    _build_replay_summary,
    _build_trajectory_rows,
    _classify_stage,
    build_task_reference_map,
)


class DecompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = BFCLTask(
            category="multi_turn_base",
            prompt_entry={"id": "task_1", "question": []},
            ground_truth=[
                ["cd(folder='document')", "mkdir(dir_name='temp')"],
                ["grep(file_name='final_report.pdf',pattern='budget analysis')"],
            ],
        )
        self.task_reference_map = build_task_reference_map([self.task])

    def test_classifies_same_function_mismatch_as_argument_parameter(self):
        task_reference = self.task_reference_map["task_1"]
        stage, failure_type = _classify_stage(
            gold_call="grep(file_name='final_report.pdf',pattern='budget analysis')",
            candidate_call="grep(file_name='temp/final_report.pdf',pattern='budget analysis')",
            task_reference=task_reference,
            gold_flat_index=2,
            error_type="multi_turn:execution_response_mismatch",
        )
        self.assertEqual(stage, "argument_parameter")
        self.assertEqual(failure_type, "wrong_arguments")

    def test_classifies_future_gold_function_as_sequencing(self):
        task_reference = self.task_reference_map["task_1"]
        stage, failure_type = _classify_stage(
            gold_call="cd(folder='document')",
            candidate_call="mkdir(dir_name='temp')",
            task_reference=task_reference,
            gold_flat_index=0,
            error_type="multi_turn:instance_state_mismatch",
        )
        self.assertEqual(stage, "sequencing_planning")
        self.assertEqual(failure_type, "wrong_order_or_context")

    def test_alignment_treats_extra_call_as_detour_and_allows_recovery(self):
        task_reference = self.task_reference_map["task_1"]
        alignment = _align_actual_trace(
            task_reference,
            [
                [["ls()"], ["cd(folder='document')"], ["mkdir(dir_name='temp')"]],
                [["grep(file_name='final_report.pdf',pattern='budget analysis')"]],
            ],
        )
        self.assertEqual(len(alignment["detours"]), 1)
        self.assertTrue(alignment["fully_aligned"])

    def test_replay_and_trajectory_summary_join(self):
        replay_records = [
            {
                "task_id": "task_1",
                "language_code": "TR",
                "model_key": "gemini",
                "run_label": "seed0",
                "turn_index": 0,
                "step_index": 0,
                "gold_call": "cd(folder='document')",
                "candidate_call": "mkdir(dir_name='temp')",
                "valid": 0,
                "evaluation": {"error_type": "multi_turn:instance_state_mismatch"},
            },
            {
                "task_id": "task_1",
                "language_code": "TR",
                "model_key": "gemini",
                "run_label": "seed0",
                "turn_index": 0,
                "step_index": 1,
                "gold_call": "mkdir(dir_name='temp')",
                "candidate_call": "mkdir(dir_name='temp')",
                "valid": 1,
                "evaluation": {},
            },
            {
                "task_id": "task_1",
                "language_code": "TR",
                "model_key": "gemini",
                "run_label": "seed0",
                "turn_index": 1,
                "step_index": 0,
                "gold_call": "grep(file_name='final_report.pdf',pattern='budget analysis')",
                "candidate_call": "grep(file_name='final_report.pdf',pattern='budget analysis')",
                "valid": 1,
                "evaluation": {},
            },
        ]
        replay_summary = _build_replay_summary(replay_records, self.task_reference_map)
        full_run_records = [
            {
                "task_id": "task_1",
                "language_code": "TR",
                "model_key": "gemini",
                "run_label": "seed0",
                "seed": 0,
                "success": 1,
                "evaluation": {
                    "decoded_result": [
                        [["ls()"], ["cd(folder='document')"], ["mkdir(dir_name='temp')"]],
                        [["grep(file_name='final_report.pdf',pattern='budget analysis')"]],
                    ]
                },
            }
        ]
        trajectory_rows = _build_trajectory_rows(
            full_run_records,
            replay_summary,
            self.task_reference_map,
        )
        self.assertEqual(len(trajectory_rows), 1)
        self.assertTrue(trajectory_rows[0]["has_detour"])
        self.assertEqual(trajectory_rows[0]["recovered"], 1)
        self.assertAlmostEqual(trajectory_rows[0]["replay_validity_rate"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
