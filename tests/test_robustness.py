import pathlib
import sys
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.robustness import (  # noqa: E402
    filter_records_by_localization,
    summarize_localization_robustness,
)


class RobustnessTests(unittest.TestCase):
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
