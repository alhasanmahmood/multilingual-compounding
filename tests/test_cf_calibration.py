import math
import pathlib
import sys
import unittest

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.metrics import TaskRecord, bootstrap_cf, compute_cf  # noqa: E402
from scripts.run_cf_calibration import (  # noqa: E402
    TASK_DIFFICULTY_BETA,
    _family_generation_parameters,
    _load_observed_rates,
    best_case_holm_p,
    beta_moment,
    expected_factor_cf,
    expected_metric_pair,
    generate_family_records,
    generate_factor_records,
    generate_position_records,
    generate_shared_difficulty_records,
    minimum_resamples_for_strict_holm,
    repair_process_expectations,
)


class CfCalibrationTests(unittest.TestCase):
    def test_generator_is_reproducible_for_a_fixed_seed(self):
        args = (32, {"EN": 0.90, "TR": 0.86}, {"EN": 0.70, "TR": 0.35})
        first = generate_factor_records(*args, seed=321)
        second = generate_factor_records(*args, seed=321)
        self.assertEqual(first, second)

    def test_shared_survival_factor_has_analytic_null_cf_one(self):
        self.assertAlmostEqual(
            expected_factor_cf(0.90, 0.86, 0.70, 0.70, k=10), 1.0
        )
        records = generate_factor_records(
            5_000,
            {"EN": 0.90, "TR": 0.86},
            {"EN": 0.70, "TR": 0.70},
            seed=88,
        )
        tr = compute_cf(records, K=10)[("TR", "synthetic")]
        self.assertLess(abs(tr["CF"] - 1.0), 0.20)
        self.assertGreater(tr["T"], 0.0)
        self.assertGreater(tr["T_ind"], 0.0)

    def test_extra_non_english_survival_loss_increases_expected_cf(self):
        cf = expected_factor_cf(0.90, 0.86, 0.70, 0.35, k=10)
        self.assertGreater(cf, 1.0)

    def test_holm_bootstrap_resolution_floor(self):
        self.assertAlmostEqual(best_case_holm_p(14, 200), 14 / 201)
        self.assertAlmostEqual(best_case_holm_p(14, 279), 0.05)
        self.assertLess(best_case_holm_p(14, 280), 0.05)
        self.assertEqual(minimum_resamples_for_strict_holm(14, 0.05), 280)

    def test_near_zero_independence_ratio_excludes_cf_but_keeps_delta(self):
        records = []
        for task_index in range(100):
            task_id = f"task_{task_index:03d}"
            en_steps = [1] * 10 if task_index < 90 else [0] * 10
            if task_index < 89:
                tr_steps = [1] * 10
            elif task_index == 89:
                tr_steps = [1] * 7 + [0] * 3
            else:
                tr_steps = [0] * 10
            records.append(
                TaskRecord(task_id, "EN", "test", int(task_index < 80), en_steps)
            )
            records.append(
                TaskRecord(task_id, "TR", "test", int(task_index < 70), tr_steps)
            )

        point = compute_cf(records, K=10)[("TR", "test")]
        result = bootstrap_cf(records, K=10, n_boot=40, seed=4)[("TR", "test")]
        self.assertTrue(math.isfinite(point["CF"]))
        self.assertLess(abs(math.log(point["r_ind"])), 0.05)
        self.assertFalse(result["CF_reportable"])
        self.assertTrue(math.isfinite(result["Delta"]))

    def test_additive_repair_does_not_cancel_like_shared_survival(self):
        same_repair = repair_process_expectations(0.90, 0.86, 0.10, 0.10)
        language_specific = repair_process_expectations(0.90, 0.86, 0.10, 0.15)
        same = same_repair["metrics"]
        specific = language_specific["metrics"]

        self.assertAlmostEqual(same["common"]["CF"], same["position"]["CF"])
        self.assertAlmostEqual(same["common"]["CF"], 0.7135387336771024)
        self.assertNotAlmostEqual(
            same["common"]["CF"], expected_factor_cf(0.90, 0.86, 0.70, 0.70)
        )
        self.assertNotAlmostEqual(
            same["common"]["CF"], specific["common"]["CF"]
        )
        self.assertAlmostEqual(
            same_repair["T"]["EN"], 0.90**10 + 0.10 * (1 - 0.90**10)
        )

    def test_position_specific_null_handles_unequal_step_difficulty(self):
        p_positions = {"EN": [0.96] * 8 + [0.66] * 2, "TR": [0.95] * 5 + [0.77] * 5}
        task_rates = {language: float(np.prod(values)) for language, values in p_positions.items()}
        expected = expected_metric_pair(p_positions, task_rates)

        self.assertAlmostEqual(expected["position"]["CF"], 1.0)
        self.assertAlmostEqual(expected["position"]["Delta"], 0.0)
        self.assertNotAlmostEqual(expected["common"]["CF"], 1.0)

        records = generate_position_records(4_000, p_positions, seed=87)
        result = compute_cf(records, K=10, null="position")[("TR", "position")]
        self.assertLess(abs(result["CF"] - 1.0), 0.12)

    def test_shared_task_difficulty_changes_absolute_fit_but_cancels_in_this_process(self):
        alpha, beta = TASK_DIFFICULTY_BETA
        mean = alpha / (alpha + beta)
        kth_moment = beta_moment(10, alpha, beta)
        tr_scale = 0.86 / 0.90
        expected_t = {"EN": kth_moment, "TR": tr_scale**10 * kth_moment}
        expected = expected_metric_pair(
            {"EN": [mean] * 10, "TR": [tr_scale * mean] * 10}, expected_t
        )

        self.assertGreater(expected_t["EN"], mean**10)
        self.assertAlmostEqual(expected["common"]["CF"], 1.0)
        self.assertAlmostEqual(expected["common"]["Delta"], 0.0)

        records = generate_shared_difficulty_records(
            4_000,
            scale_by_language={"EN": 1.0, "TR": tr_scale},
            n_seeds=2,
            alpha=alpha,
            beta=beta,
            seed=88,
        )
        point = compute_cf(records, K=10)[("EN", "shared_difficulty")]
        self.assertGreater(point["T"], point["T_ind"])

    def test_family_null_is_analytic_cf_one_and_bootstrap_keeps_seed_pairs(self):
        observed = _load_observed_rates()
        parameters = _family_generation_parameters(observed, alternative=False)
        en = parameters["cells"]["EN::gemini"]
        for language in ("AR", "ES", "HI", "JA", "SW", "TR", "ZH"):
            cell = parameters["cells"][f"{language}::gemini"]
            expected_cf = math.log(cell["T"] / en["T"]) / math.log(
                (cell["p"] / en["p"]) ** 10
            )
            self.assertAlmostEqual(expected_cf, 1.0)

        records, _ = generate_family_records(
            4, observed=observed, alternative=False, seed=99
        )
        task_seed_ids = [record.task_id for record in records if record.language == "TR" and record.backbone == "gemini"]
        underlying_ids = [record.underlying_task_id for record in records if record.language == "TR" and record.backbone == "gemini"]
        self.assertEqual(len(set(task_seed_ids)), 8)
        self.assertEqual(len(set(underlying_ids)), 4)

        result = bootstrap_cf(
            records,
            K=10,
            n_boot=100,
            seed=100,
            cluster_unit="underlying_task",
        )
        self.assertEqual(len(result), 14)
        self.assertEqual(result[("TR", "gemini")]["cluster_count"], 4)
        self.assertEqual(result[("TR", "gemini")]["cluster_unit"], "underlying_task")


if __name__ == "__main__":
    unittest.main()
