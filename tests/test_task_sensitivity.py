import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.metrics import TaskRecord, compute_cf  # noqa: E402

SCRIPT_PATH = REPO_ROOT / "scripts" / "run_task_sensitivity.py"
SPEC = importlib.util.spec_from_file_location("run_task_sensitivity", SCRIPT_PATH)
SENSITIVITY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SENSITIVITY)


class TaskSensitivityTests(unittest.TestCase):
    @staticmethod
    def _records(scenario_count=1):
        records = []
        for task in range(4):
            for seed in range(2):
                task_id = f"task_{task}::seed{seed}"
                en_steps = [int((task + seed + k) % 3 != 0) for k in range(3)]
                tr_steps = [int((task + seed + k) % 4 != 0) for k in range(3)]
                records.append(
                    TaskRecord(
                        task_id, "EN", "gemini", int(sum(en_steps) == 3), en_steps,
                        f"scenario_{task % scenario_count}", f"task_{task}"
                    )
                )
                records.append(
                    TaskRecord(
                        task_id, "TR", "gemini", int(sum(tr_steps) >= 2), tr_steps,
                        f"scenario_{task % scenario_count}", f"task_{task}"
                    )
                )
        return records

    def test_leave_one_variant_out_removes_both_seed_runs_and_matches_direct_estimate(self):
        records = self._records()
        result = SENSITIVITY.summarize_leave_one_task_out(records, [3], nulls=("common",))
        cell = result["3"]["common"]["cells"]["TR::gemini"]
        self.assertEqual(len(cell["leave_one_task_variant_out"]), 4)

        for omitted_task, values in cell["leave_one_task_variant_out"].items():
            reduced = [
                record
                for record in records
                if record.task_variant_id != omitted_task
            ]
            kept_cluster_ids = {record.underlying_task_id for record in reduced}
            self.assertEqual(kept_cluster_ids, {"scenario_0"})
            self.assertEqual(len({record.task_variant_id for record in reduced}), 3)
            self.assertEqual(sum(record.language == "TR" for record in reduced), 6)
            expected = compute_cf(reduced, K=3, null="common")[("TR", "gemini")]
            self.assertAlmostEqual(values["Delta"], expected["Delta"])
            self.assertAlmostEqual(values["CF"], expected["CF"])

    def test_scenario_bootstrap_is_reported_unavailable_for_one_family(self):
        summary = SENSITIVITY.run_sensitivity(
            self._records(), [3], n_boot=10, bootstrap_seed=0, min_log_rind=0.05
        )
        result = summary["bootstrap_comparison"]["3"]["common"]["underlying_task"]
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["cluster_count_by_model"], {"gemini": 1})

    def test_multiple_scenario_clusters_are_bootstrapped_and_reported_dynamically(self):
        records = self._records(scenario_count=2)
        bootstrap_calls = []

        def fake_bootstrap(records, **kwargs):
            cluster_ids = {
                record.underlying_task_id if kwargs["cluster_unit"] == "underlying_task" else record.task_id
                for record in records
                if record.backbone == "gemini"
            }
            bootstrap_calls.append((kwargs["cluster_unit"], len(cluster_ids)))
            return {
                ("TR", "gemini"): {
                    "CF": 1.2,
                    "Delta": 0.2,
                    "CF_CI": (0.8, 1.5),
                    "Delta_CI": (0.1, 0.3),
                    "bootstrap_tail_probability": 0.2,
                    "holm_adjusted_bootstrap_tail_probability": 0.4,
                    "CF_reportable": True,
                }
            }

        with patch.object(SENSITIVITY, "bootstrap_cf", side_effect=fake_bootstrap):
            result = SENSITIVITY.run_sensitivity(
                records, [3], n_boot=10, bootstrap_seed=0, min_log_rind=0.05
            )

        self.assertEqual(bootstrap_calls.count(("underlying_task", 2)), 2)
        self.assertEqual(bootstrap_calls.count(("task_seed", 8)), 2)
        self.assertIn(
            "TR::gemini",
            result["bootstrap_comparison"]["3"]["common"]["underlying_task"],
        )

        summary = {
            "scope": {
                "tasks": 4,
                "task_ids": [f"task_{i}" for i in range(4)],
                "languages": ["EN", "TR"],
                "models": ["gemini"],
                "run_labels": ["seed0", "seed1"],
                "full_runs": 16,
                "replays": 48,
                "task_seed_clusters_by_model": {"gemini": 8},
                "underlying_task_clusters_by_model": {"gemini": 2},
                "scenario_family_to_task_variants": {
                    "scenario_0": ["task_0", "task_2"],
                    "scenario_1": ["task_1", "task_3"],
                },
            },
            "settings": {"n_boot": 10, "bootstrap_seed": 0},
            "point_estimate_invariance_check": {"status": "match"},
            **result,
        }
        report = SENSITIVITY._render_report(summary)
        self.assertIn("2 underlying scenario families", report)
        self.assertIn("underlying_task | estimated", report)
        self.assertIn("task_seed | estimated", report)
        self.assertIn("conditional sensitivity diagnostics", report)
        self.assertNotIn("four category variants", report.lower())
        self.assertNotIn("14 non-English model cells", report)
        self.assertNotIn("eight category-variant/seed rows", report)


if __name__ == "__main__":
    unittest.main()
