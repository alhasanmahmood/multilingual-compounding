import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.metrics import (  # noqa: E402
    TaskRecord,
    bootstrap_cf,
    compute_cf,
)


class CompoundingMetricsTests(unittest.TestCase):
    def test_accepts_full_english_label(self):
        records = [
            TaskRecord("task_1", "English", "gpt4o", 1, [1, 1]),
            TaskRecord("task_1", "Turkish", "gpt4o", 0, [1, 1]),
            TaskRecord("task_2", "English", "gpt4o", 1, [1, 1]),
            TaskRecord("task_2", "Turkish", "gpt4o", 0, [1, 1]),
        ]
        result = compute_cf(records, K=2)
        self.assertIn(("Turkish", "gpt4o"), result)
        self.assertNotIn(("English", "gpt4o"), [k for k, v in result.items() if v["CF"] == v["CF"]])

    def test_bootstrap_is_task_level_and_runs_with_task_ids(self):
        records = [
            TaskRecord("task_1", "EN", "gpt4o", 1, [1, 1, 1]),
            TaskRecord("task_1", "TR", "gpt4o", 0, [1, 1, 1]),
            TaskRecord("task_2", "EN", "gpt4o", 1, [1, 1, 1]),
            TaskRecord("task_2", "TR", "gpt4o", 0, [1, 1, 1]),
            TaskRecord("task_3", "EN", "gpt4o", 1, [1, 1, 1]),
            TaskRecord("task_3", "TR", "gpt4o", 0, [1, 1, 1]),
        ]
        result = bootstrap_cf(records, K=3, n_boot=50, seed=0)
        self.assertIn(("TR", "gpt4o"), result)
        self.assertLess(result[("TR", "gpt4o")]["Delta"], 0)

    def test_detects_compounding_in_synthetic_case(self):
        records = []
        for i in range(30):
            records.append(TaskRecord(f"task_{i}", "EN", "gpt4o", 1, [1, 1, 1, 1]))
            records.append(TaskRecord(f"task_{i}", "TR", "gpt4o", 0, [1, 1, 1, 1]))
        result = bootstrap_cf(records, K=4, n_boot=100, seed=1)
        cell = result[("TR", "gpt4o")]
        self.assertTrue(cell["CF"] > 1 or cell["Delta"] < 0)


if __name__ == "__main__":
    unittest.main()
