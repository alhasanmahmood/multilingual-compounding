import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location(
    "validate_expansion_environment",
    ROOT / "scripts" / "validate_expansion_environment.py",
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class ExpansionEnvironmentTests(unittest.TestCase):
    def test_fixed_plan_environments_and_gold_replays_pass_without_provider_calls(self):
        report = preflight.validate_expansion_environment(
            ROOT / "analysis/bfcl/newstudy20261010_plan.json"
        )

        self.assertEqual(report["status"], "passed", report["issues"])
        self.assertEqual(report["validated_task_count"], 20)
        self.assertEqual(report["gold_call_count"], 186)
        self.assertEqual(report["replay_case_count"], 186)
        self.assertEqual(report["gold_self_replay_count"], 186)
        self.assertEqual(report["provider_api_calls"], 0)
        self.assertFalse(report["provider_api_clients_created"])
        self.assertTrue(all(item["status"] == "passed" for item in report["classes"]))


if __name__ == "__main__":
    unittest.main()
