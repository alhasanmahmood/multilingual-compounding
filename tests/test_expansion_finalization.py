import importlib.util
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finalize_expansion_collection.py"
SPEC = importlib.util.spec_from_file_location("expansion_finalization", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExpansionFinalizationTests(unittest.TestCase):
    def test_live_collection_waits(self):
        self.assertFalse(MODULE.ready_or_failed({"jobs": [{"status": "running"}]}))

    def test_failure_prevents_partial_analysis(self):
        for state in ({"status": "failed"}, {"jobs": [{"status": "failed"}]},
                      {"status": "hard_timeout"}):
            with self.assertRaises(RuntimeError):
                MODULE.ready_or_failed(state)

    def test_completion_requires_all_eight_jobs(self):
        with self.assertRaises(RuntimeError):
            MODULE.ready_or_failed({"status": "completed", "jobs": []})
        self.assertTrue(MODULE.ready_or_failed({"status": "completed",
                         "jobs": [{"status": "completed"}] * 8}))

    def test_stale_plan_and_attempt_are_rejected(self):
        state = {"plan_sha256": "plan1", "started_at": "attempt1"}
        self.assertFalse(MODULE.ready_or_failed(state, "plan1", "attempt1"))
        for plan, attempt in (("plan2", "attempt1"), ("plan1", "attempt2")):
            with self.assertRaises(RuntimeError):
                MODULE.ready_or_failed(state, plan, attempt)

    def test_prior_status_is_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            original = b'{"status":"failed","error":"quota"}\n'
            path.write_bytes(original)
            with patch.object(MODULE, "FINALIZATION", path):
                MODULE.preserve_previous_status()
            archived = list((path.parent / f"{MODULE.PREFIX}_finalization_history").glob("*.json"))
            self.assertEqual(len(archived), 1)
            self.assertEqual(archived[0].read_bytes(), original)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
