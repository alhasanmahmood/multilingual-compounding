from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OfflineAnalysisCliTests(unittest.TestCase):
    task_ids = ["multi_turn_base_0", "multi_turn_miss_func_10"]

    def _argv(self, script: str, *options: str) -> list[str]:
        del script  # The script path is already represented by the imported module.
        return ["python", "--models", "gemini", *options]

    def test_compounding_forwards_task_ids_and_separate_input_output_prefixes(self):
        script = load_script("run_compounding_analysis.py")
        with patch("sys.argv", self._argv(
            "run_compounding_analysis.py",
            "--task-ids", *self.task_ids,
            "--input-artifact-prefix", "raw20",
            "--artifact-prefix", "summary20",
            "--language-codes", "EN",
            "--run-labels", "expansion_seed0",
        )):
            with (
                patch.object(script, "load_env_file"),
                patch.object(script, "resolve_model_keys", return_value=["gemini"]),
                patch.object(script, "resolve_language_codes", return_value=["EN"]),
                patch.object(script, "load_bfcl_multiturn_tasks", return_value=["all tasks"]),
                patch.object(script, "select_bfcl_tasks", return_value=["selected tasks"]) as select,
                patch.object(script, "summarize_existing_artifacts", return_value={"full_runs": 1}) as summarize,
                redirect_stdout(io.StringIO()),
            ):
                script.main()
        self.assertEqual(select.call_args.kwargs["task_ids"], self.task_ids)
        self.assertEqual(summarize.call_args.kwargs["tasks"], ["selected tasks"])
        self.assertEqual(summarize.call_args.kwargs["input_artifact_prefix"], "raw20")
        self.assertEqual(summarize.call_args.kwargs["artifact_prefix"], "summary20")

    def test_decomposition_reads_prefixed_artifacts_and_writes_separately(self):
        script = load_script("run_decomposition_analysis.py")
        with tempfile.TemporaryDirectory() as directory:
            output_root = pathlib.Path(directory)
            with patch("sys.argv", self._argv(
                "run_decomposition_analysis.py",
                "--task-ids", *self.task_ids,
                "--input-artifact-prefix", "raw20",
                "--artifact-prefix", "summary20_e4",
                "--language-codes", "EN",
                "--run-labels", "expansion_seed0",
            )):
                with (
                    patch.object(script, "SUMMARY_ROOT", output_root),
                    patch.object(script, "load_env_file"),
                    patch.object(script, "resolve_model_keys", return_value=["gemini"]),
                    patch.object(script, "resolve_language_codes", return_value=["EN"]),
                    patch.object(script, "load_bfcl_multiturn_tasks", return_value=["all tasks"]),
                    patch.object(script, "select_bfcl_tasks", return_value=["selected tasks"]) as select,
                    patch.object(script, "collect_artifact_records", return_value=([], [])) as collect,
                    patch.object(script, "summarize_decomposition", return_value={"ok": True}),
                    patch.object(script, "build_decomposition_report", return_value="# report"),
                    redirect_stdout(io.StringIO()),
                ):
                    script.main()
            self.assertEqual(select.call_args.kwargs["task_ids"], self.task_ids)
            self.assertEqual(collect.call_args.kwargs["artifact_prefix"], "raw20")
            self.assertTrue((output_root / "summary20_e4_summary.json").exists())
            self.assertTrue((output_root / "summary20_e4_report.md").exists())

    def test_robustness_selects_prefixed_localizations_and_saved_runs(self):
        script = load_script("run_robustness_analysis.py")
        with tempfile.TemporaryDirectory() as directory:
            temp_root = pathlib.Path(directory)
            cache_root = temp_root / "cache"
            output_root = temp_root / "output"
            cache_root.mkdir()
            output_root.mkdir()
            (cache_root / "loc20_bfcl_multiturn_localizations.jsonl").write_text(
                json.dumps({"task_id": self.task_ids[0], "language_code": "EN"}) + "\n",
                encoding="utf-8",
            )
            with patch("sys.argv", self._argv(
                "run_robustness_analysis.py",
                "--task-ids", *self.task_ids,
                "--input-artifact-prefix", "raw20",
                "--localization-prefix", "loc20",
                "--artifact-prefix", "summary20_e6",
                "--language-codes", "EN",
                "--run-labels", "expansion_seed0",
            )):
                with (
                    patch.object(script, "SUMMARY_ROOT", output_root),
                    patch.object(script, "LOCALIZATION_ROOT", cache_root),
                    patch.object(script, "load_env_file"),
                    patch.object(script, "resolve_model_keys", return_value=["gemini"]),
                    patch.object(script, "resolve_language_codes", return_value=["EN"]),
                    patch.object(script, "load_bfcl_multiturn_tasks", return_value=["all tasks"]),
                    patch.object(script, "select_bfcl_tasks", return_value=["selected tasks"]) as select,
                    patch.object(script, "collect_artifact_records", return_value=([], [])) as collect,
                    patch.object(script, "summarize_localization_robustness", return_value={}),
                    patch.object(script, "filter_records_by_localization", return_value=([], [])),
                    patch.object(script, "summarize_cf", return_value={"k": {}, "bootstrap": {}}),
                    patch.object(script, "summarize_k_sensitivity", return_value={}),
                    patch.object(script, "summarize_leave_one_language_out", return_value={}),
                    patch.object(script, "summarize_seed_variance", return_value={}),
                    patch.object(script, "build_robustness_report", return_value="# report"),
                    redirect_stdout(io.StringIO()),
                ):
                    script.main()
            self.assertEqual(select.call_args.kwargs["task_ids"], self.task_ids)
            self.assertEqual(collect.call_args.kwargs["artifact_prefix"], "raw20")
            self.assertTrue((output_root / "summary20_e6_summary.json").exists())
            self.assertTrue((output_root / "summary20_e6_report.md").exists())

    def test_task_sensitivity_uses_requested_summary_path_and_input_prefix(self):
        script = load_script("run_task_sensitivity.py")
        with tempfile.TemporaryDirectory() as directory:
            temp_root = pathlib.Path(directory)
            chosen_tasks = [
                SimpleNamespace(prompt_entry={"id": task_id}, ground_truth=[["call()"]])
                for task_id in self.task_ids
            ]
            with patch("sys.argv", self._argv(
                "run_task_sensitivity.py",
                "--task-ids", *self.task_ids,
                "--per-category-limit", "5",
                "--input-artifact-prefix", "raw20",
                "--main-summary-path", str(temp_root / "summary20_cf_summary.json"),
                "--summary-path", str(temp_root / "sensitivity.json"),
                "--report-path", str(temp_root / "sensitivity.md"),
                "--language-codes", "EN", "TR",
                "--run-labels", "expansion_seed0",
            )):
                with (
                    patch.object(script, "load_env_file"),
                    patch.object(script, "resolve_model_keys", return_value=["gemini"]),
                    patch.object(script, "resolve_language_codes", return_value=["EN", "TR"]),
                    patch.object(script, "load_bfcl_multiturn_tasks", return_value=["all tasks"]),
                    patch.object(script, "select_bfcl_tasks", return_value=chosen_tasks) as select,
                    patch.object(script, "collect_artifact_records", return_value=([], [])) as collect,
                    patch.object(script, "build_task_records", return_value=([], {})),
                    patch.object(script, "run_sensitivity", return_value={"bootstrap_comparison": {}, "leave_one_task_variant_out": {}}),
                    patch.object(script, "_compare_main_point_estimates", return_value={"status": "match"}) as compare,
                    patch.object(script, "_render_report", return_value="# report"),
                    redirect_stdout(io.StringIO()),
                ):
                    script.main()
            self.assertEqual(select.call_args.kwargs["task_ids"], self.task_ids)
            self.assertIsNone(select.call_args.kwargs["per_category_limit"])
            self.assertEqual(collect.call_args.kwargs["artifact_prefix"], "raw20")
            self.assertEqual(compare.call_args.args[2], temp_root / "summary20_cf_summary.json")
            result = json.loads((temp_root / "sensitivity.json").read_text(encoding="utf-8"))
            self.assertEqual(result["scope"]["task_ids"], self.task_ids)
            self.assertEqual(result["settings"]["input_artifact_prefix"], "raw20")


if __name__ == "__main__":
    unittest.main()
