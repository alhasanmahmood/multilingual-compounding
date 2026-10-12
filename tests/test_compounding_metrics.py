import pathlib
import sys
import unittest
import numpy as np

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
    @staticmethod
    def _seeded_records():
        records = []
        for task in range(4):
            for seed in range(2):
                task_id = f"task_{task}::seed{seed}"
                length = 2 + ((task + seed) % 2)
                en_steps = [int((task + seed + position) % 3 != 0) for position in range(length)]
                tr_steps = [int((task + 2 * seed + position) % 4 != 0) for position in range(length)]
                records.append(
                    TaskRecord(task_id, "EN", "model", int(sum(en_steps) == length), en_steps, f"task_{task}")
                )
                records.append(
                    TaskRecord(task_id, "TR", "model", int(sum(tr_steps) == length - 1), tr_steps, f"task_{task}")
                )
        return records

    @staticmethod
    def _reference_bootstrap(records, K, null, n_boot, seed, cluster_unit):
        groups = {}
        for record in records:
            group_id = (
                record.task_id
                if cluster_unit == "task_seed"
                else (record.underlying_task_id or record.task_id)
            )
            groups.setdefault(group_id, []).append(record)
        cluster_ids = sorted(groups)
        rng = np.random.default_rng(seed)
        delta_draws = []
        cf_draws = []
        for counts in rng.multinomial(
            len(cluster_ids), np.full(len(cluster_ids), 1.0 / len(cluster_ids)), size=n_boot
        ):
            sample = []
            for cluster_id, count in zip(cluster_ids, counts):
                sample.extend(groups[cluster_id] * int(count))
            point = compute_cf(sample, K=K, null=null)
            delta_draws.append(point[("TR", "model")]["Delta"])
            cf_draws.append(point[("TR", "model")]["CF"])
        delta_draws = np.asarray(delta_draws, dtype=float)
        cf_draws = np.asarray(cf_draws, dtype=float)
        valid_cf = cf_draws[~np.isnan(cf_draws)]
        return {
            "Delta_CI": np.percentile(delta_draws, [2.5, 97.5]),
            "CF_CI": np.percentile(valid_cf, [2.5, 97.5]),
            "p_raw": (np.sum(delta_draws >= 0.0) + 1) / (len(delta_draws) + 1),
        }

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

    def test_underlying_task_bootstrap_groups_seed_repeats_and_preserves_point_estimates(self):
        records = self._seeded_records()
        point = compute_cf(records, K=3, null="common")
        task_seed = bootstrap_cf(
            records, K=3, null="common", n_boot=60, seed=17, cluster_unit="task_seed"
        )
        underlying = bootstrap_cf(
            records, K=3, null="common", n_boot=60, seed=17, cluster_unit="underlying_task"
        )

        self.assertEqual(task_seed[("TR", "model")]["cluster_count"], 8)
        self.assertEqual(underlying[("TR", "model")]["cluster_count"], 4)
        self.assertEqual(task_seed[("TR", "model")]["n_boot"], 60)
        self.assertEqual(task_seed[("TR", "model")]["seed"], 17)
        self.assertEqual(task_seed[("TR", "model")]["inference_status"], "uncalibrated_tail_diagnostic")
        self.assertEqual(
            task_seed[("TR", "model")]["p_raw"],
            task_seed[("TR", "model")]["bootstrap_tail_probability"],
        )
        self.assertAlmostEqual(task_seed[("TR", "model")]["CF"], point[("TR", "model")]["CF"])
        self.assertAlmostEqual(underlying[("TR", "model")]["CF"], point[("TR", "model")]["CF"])
        self.assertAlmostEqual(task_seed[("TR", "model")]["Delta"], underlying[("TR", "model")]["Delta"])

    def test_vectorized_bootstrap_matches_task_record_reference_for_both_nulls_and_clusters(self):
        records = self._seeded_records()
        for null in ("common", "position"):
            for cluster_unit in ("task_seed", "underlying_task"):
                with self.subTest(null=null, cluster_unit=cluster_unit):
                    result = bootstrap_cf(
                        records, K=3, null=null, n_boot=41, seed=29, cluster_unit=cluster_unit
                    )[("TR", "model")]
                    reference = self._reference_bootstrap(
                        records, K=3, null=null, n_boot=41, seed=29, cluster_unit=cluster_unit
                    )
                    np.testing.assert_allclose(result["Delta_CI"], reference["Delta_CI"])
                    np.testing.assert_allclose(result["CF_CI"], reference["CF_CI"])
                    self.assertAlmostEqual(result["p_raw"], reference["p_raw"])

    def test_underlying_bootstrap_refuses_single_scenario_cluster(self):
        records = []
        for variant in range(4):
            for seed in range(2):
                task_seed = f"variant_{variant}::seed{seed}"
                records.append(TaskRecord(task_seed, "EN", "model", 1, [1, 1], "scenario_0"))
                records.append(TaskRecord(task_seed, "TR", "model", 0, [1, 1], "scenario_0"))
        with self.assertRaisesRegex(ValueError, "only 1 cluster"):
            bootstrap_cf(records, K=2, n_boot=50, cluster_unit="underlying_task")


if __name__ == "__main__":
    unittest.main()
