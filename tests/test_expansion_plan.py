import importlib.util
import pathlib
import sys
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("expansion_plan", ROOT / "scripts" / "plan_bfcl_expansion.py")
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)
from multilingual_compounding.bfcl_vendor import BFCLTask
from multilingual_compounding.settings import PILOT_TEST_CATEGORIES


class ExpansionPlanTests(unittest.TestCase):
    def test_selection_preserves_unique_scenarios_and_balanced_categories(self):
        lengths = [10] * 7 + [9] * 12 + [8] * 4 + [35]
        tasks = [
            BFCLTask(cat, {"id": f"{cat}_{index}"}, [["tool()"] * length])
            for cat in PILOT_TEST_CATEGORIES
            for index, length in enumerate(lengths)
        ]
        selected = plan.select_horizon_matched_tasks(tasks, 5)
        self.assertEqual(len(selected), 20)
        self.assertEqual(len({t.prompt_entry["id"].rsplit("_", 1)[1] for t in selected}), 20)
        self.assertEqual(Counter(t.category for t in selected), Counter({c: 5 for c in PILOT_TEST_CATEGORIES}))
        self.assertEqual(Counter(plan.gold_call_count(t) for t in selected), Counter({10: 7, 9: 12, 8: 1}))
        self.assertEqual([t.prompt_entry["id"] for t in selected], [t.prompt_entry["id"] for t in plan.select_horizon_matched_tasks(list(reversed(tasks)), 5)])

    def test_refuses_insufficient_distinct_scenarios(self):
        tasks = [BFCLTask(c, {"id": f"{c}_0"}, [["tool()"] * 10]) for c in PILOT_TEST_CATEGORIES]
        with self.assertRaises(ValueError):
            plan.select_horizon_matched_tasks(tasks, 5)


if __name__ == "__main__":
    unittest.main()
