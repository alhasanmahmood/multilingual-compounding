from __future__ import annotations

import csv
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_expansion_paper_results.py"
SPEC = importlib.util.spec_from_file_location("render_expansion_paper_results", SCRIPT_PATH)
RENDERER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RENDERER)
from multilingual_compounding.metrics import TaskRecord, bootstrap_cf, compute_cf  # noqa: E402

PREFIX = "fixture_expansion"
LANGUAGES = ["EN", "AR", "TR", "ZH", "HI", "JA", "ES", "SW"]
MODELS = ["gemini", "claude_sonnet46"]
RUN_LABELS = ["expansion_seed0", "expansion_seed1"]
CATEGORIES = [
    "multi_turn_base",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "multi_turn_long_context",
]


def _fixture_bundle(base: Path) -> tuple[Path, Path, dict[str, object]]:
    analysis_dir = base / "analysis"
    paper_dir = base / "paper"
    analysis_dir.mkdir(parents=True)
    task_ids = [
        f"{category}_{100 + 5 * category_index + task_index}"
        for category_index, category in enumerate(CATEGORIES)
        for task_index in range(5)
    ]
    positions = {task_id: (9 if index < 14 else 10) for index, task_id in enumerate(task_ids)}
    counts = {
        "tasks": 20,
        "unique_scenarios": 20,
        "categories": 4,
        "tasks_per_category": {category: 5 for category in CATEGORIES},
        "languages": LANGUAGES,
        "models": MODELS,
        "run_labels": RUN_LABELS,
        "localization_rows": 160,
        "gold_call_positions": 186,
        "full_trajectories": 640,
        "replays": 5952,
    }
    audit = {
        "status": "complete",
        "counts": counts,
        "validation": {
            "localizations": {"rows": 160, "expected_rows": 160},
            "artifacts": {
                "full_trajectories": 640,
                "replays": 5952,
                "unique_task_scenarios": 20,
                "gold_call_positions_per_task": positions,
            },
            "all_expected_keys_present": True,
            "duplicate_keys": 0,
            "orphan_keys": 0,
            "provider_identities_match": True,
            "source_and_target_hashes_match": True,
            "gold_call_positions_match": True,
        },
        "provenance": {
            "plan_sha256": "a" * 64,
            "raw_file_manifest_sha256": "b" * 64,
            "bfcl_commit": "fixture-commit",
        },
    }

    cell_keys = [f"{language}::{model}" for language in LANGUAGES for model in MODELS]
    non_english_cells = [key for key in cell_keys if not key.startswith("EN::")]

    def point(k: int, language: str, model: str, null: str = "common") -> dict[str, object]:
        language_index = LANGUAGES.index(language)
        model_index = MODELS.index(model)
        delta = -0.2 + (k - 8) * 0.1 + language_index * 0.01 + model_index * 0.005
        cf = 1.1 + (k - 8) * 0.08 + language_index * 0.01 + model_index * 0.005
        if null == "position":
            delta += 0.03
            cf += 0.02
        return {
            "T": 0.5,
            "r_ind": 0.5,
            "CF": cf,
            "Delta": delta,
            "CF_reportable": True,
        }

    cf_summary: dict[str, object] = {
        "k": {"mean_k": 9.3, "rounded_k": 9, "k_range": [8, 9, 10]},
        "scope": {
            "tasks": 20,
            "task_ids": task_ids,
            "languages": LANGUAGES,
            "models": MODELS,
            "run_labels": RUN_LABELS,
            "task_trials": 640,
            "replay_trials": 5952,
        },
        "point_estimates": {},
        "bootstrap": {},
        "bootstrap_config": {
            "n_boot": 5000,
            "seed": 17,
            "cluster_unit": "underlying_task",
            "cluster_counts_by_backbone": {model: 20 for model in MODELS},
            "status": "available",
            "unavailable_reason": None,
            "tail_interpretation": "uncalibrated directional diagnostic",
        },
    }

    def interval_values(
        value: dict[str, object],
        unit: str,
        offset: float = 0.0,
    ) -> dict[str, object]:
        delta = float(value["Delta"])
        cf = float(value["CF"])
        width = 0.1 if unit == "underlying_task" else 0.2
        return {
            **value,
            "Delta_CI": [delta - width + offset, delta + width + offset],
            "CF_CI": [cf - width + offset, cf + width + offset],
            "CF_reportable": True,
            "n_boot": 5000,
            "seed": 17,
            "cluster_unit": unit,
            "cluster_count": 20 if unit == "underlying_task" else 40,
            "inference_status": "uncalibrated_tail_diagnostic",
        }

    sensitivity: dict[str, object] = {
        "metadata": {
            "bootstrap_cluster_primary": "underlying_task",
            "bootstrap_cluster_sensitivity": "task_seed",
            "inference_status": "uncalibrated_tail_diagnostic",
            "nulls": ["common", "position"],
        },
        "settings": {
            "n_boot": 5000,
            "bootstrap_seed": 17,
            "k_values": [8, 9, 10],
            "models": MODELS,
        },
        "scope": {
            "tasks": 20,
            "task_ids": task_ids,
            "languages": LANGUAGES,
            "models": MODELS,
            "run_labels": RUN_LABELS,
            "full_runs": 640,
            "replays": 5952,
            "task_seed_clusters_by_model": {model: 40 for model in MODELS},
            "underlying_task_clusters_by_model": {model: 20 for model in MODELS},
            "scenario_family_to_task_variants": {
                f"scenario_{index}": [task_id] for index, task_id in enumerate(task_ids)
            },
        },
        "point_estimate_invariance_check": {
            "status": "match",
            "checked_values": 3 * len(cell_keys),
            "checks": [
                {"k": k, "cell": cell, "status": "match"}
                for k in (8, 9, 10)
                for cell in cell_keys
            ],
        },
        "bootstrap_comparison": {},
        "leave_one_task_variant_out": {},
    }

    for k in (8, 9, 10):
        common_points = {
            cell: point(k, *cell.split("::", 1), null="common")
            for cell in cell_keys
        }
        cf_summary["point_estimates"][str(k)] = {
            cell: {
                **values,
                "p": 0.7,
                "T_ind": 0.2,
                "r_obs": 0.8,
                "n": 20,
            }
            for cell, values in common_points.items()
        }
        common_boot = {
            cell: interval_values(common_points[cell], "underlying_task")
            for cell in non_english_cells
        }
        position_points = {
            cell: point(k, *cell.split("::", 1), null="position")
            for cell in cell_keys
        }
        position_boot = {
            cell: interval_values(position_points[cell], "underlying_task")
            for cell in non_english_cells
        }
        cf_summary["bootstrap"][str(k)] = {
            "common": common_boot,
            "position": position_boot,
        }

        sensitivity["bootstrap_comparison"][str(k)] = {}
        sensitivity["leave_one_task_variant_out"][str(k)] = {}
        for null, full_points in (("common", common_points), ("position", position_points)):
            sensitivity["leave_one_task_variant_out"][str(k)][null] = {
                "full_point_estimates": full_points,
                "cells": {},
            }
            for cell, full in full_points.items():
                omissions = {}
                for index, task_id in enumerate(task_ids):
                    omitted = dict(full)
                    if k == 9 and null == "common" and cell == "TR::gemini" and index == 0:
                        omitted["Delta"] = abs(float(full["Delta"])) + 0.01
                    if k == 9 and null == "common" and cell == "TR::claude_sonnet46" and index == 1:
                        omitted["CF_reportable"] = False
                        omitted["CF"] = None
                    omissions[task_id] = omitted
                sensitivity["leave_one_task_variant_out"][str(k)][null]["cells"][cell] = {
                    "full": full,
                    "leave_one_task_variant_out": omissions,
                }
            sensitivity["bootstrap_comparison"][str(k)][null] = {}
            for unit in ("underlying_task", "task_seed"):
                sensitivity["bootstrap_comparison"][str(k)][null][unit] = {
                    cell: interval_values(
                        full_points[cell],
                        unit,
                        offset=0.017 if unit == "underlying_task" else 0.0,
                    )
                    for cell in non_english_cells
                }

    decomposition = {
        "scope": {
            "tasks": 20,
            "task_ids": task_ids,
            "languages": LANGUAGES,
            "models": MODELS,
            "run_labels": RUN_LABELS,
            "task_trials": 640,
            "replay_trials": 5952,
        },
        "aggregates": {
            "english": {
                "replay": {
                    "invalid_step_total": 3,
                    "stage_counts": {"direct": 2, "propagated": 1},
                    "failure_type_counts": {"wrong_tool": 3},
                },
                "trajectory": {"runs": 80, "runs_with_detour": 4},
            },
            "non_english": {
                "replay": {
                    "invalid_step_total": 9,
                    "stage_counts": {"direct": 4, "propagated": 5},
                    "failure_type_counts": {"wrong_tool": 6, "wrong_argument": 3},
                },
                "trajectory": {"runs": 560, "runs_with_detour": 17},
            },
        },
    }
    robustness = {
        "scope": {
            "tasks": 20,
            "task_ids": task_ids,
            "languages": LANGUAGES,
            "models": MODELS,
            "run_labels": RUN_LABELS,
            "full_runs": 640,
            "replays": 5952,
        }
    }

    inputs = {
        "collection_audit.json": audit,
        "cf_summary.json": cf_summary,
        "decomposition_summary.json": decomposition,
        "robustness_summary.json": robustness,
        "task_sensitivity_summary.json": sensitivity,
    }
    for suffix, value in inputs.items():
        (analysis_dir / f"{PREFIX}_{suffix}").write_text(
            json.dumps(value, allow_nan=True), encoding="utf-8"
        )
    for suffix in ("report.md", "decomposition_report.md", "robustness_report.md", "task_sensitivity_report.md", "overview.md"):
        (analysis_dir / f"{PREFIX}_{suffix}").write_text("fixture report\n", encoding="utf-8")
    return analysis_dir, paper_dir, audit


class RenderExpansionPaperResultsTests(unittest.TestCase):
    def test_reversing_backbone_insertion_order_reassigns_seeded_rng_blocks(self):
        def records(model_order: tuple[str, str]) -> list[TaskRecord]:
            output = []
            for model in model_order:
                for task in range(6):
                    for seed in range(2):
                        for language in ("EN", "TR"):
                            if model == "alpha":
                                steps = [
                                    int((task + seed + position) % 3 != 0)
                                    for position in range(3)
                                ]
                                success = int(
                                    (task * 2 + seed + (0 if language == "EN" else 1)) % 5
                                    not in (0, 1)
                                )
                            else:
                                steps = [
                                    int(
                                        (
                                            task * 2
                                            + seed
                                            + position * 2
                                            + (language == "TR")
                                        )
                                        % 4
                                        != 0
                                    )
                                    for position in range(3)
                                ]
                                success = int(
                                    (task + seed + (2 if language == "EN" else 0)) % 4
                                    in (0, 2, 3)
                                )
                            output.append(
                                TaskRecord(
                                    f"task{task}::seed{seed}",
                                    language,
                                    model,
                                    success,
                                    steps,
                                    f"scenario{task}",
                                    f"task{task}",
                                )
                            )
            return output

        main_order = records(("alpha", "beta"))
        sensitivity_order = records(("beta", "alpha"))
        main_points = compute_cf(main_order, K=3, null="common")
        sensitivity_points = compute_cf(sensitivity_order, K=3, null="common")
        self.assertEqual(
            {cell: values["Delta"] for cell, values in main_points.items()},
            {cell: values["Delta"] for cell, values in sensitivity_points.items()},
        )
        main_boot = bootstrap_cf(
            main_order, K=3, null="common", n_boot=100, seed=3, cluster_unit="underlying_task"
        )
        sensitivity_boot = bootstrap_cf(
            sensitivity_order, K=3, null="common", n_boot=100, seed=3, cluster_unit="underlying_task"
        )
        self.assertEqual(main_boot[("TR", "alpha")]["n_boot"], 100)
        self.assertEqual(main_boot[("TR", "alpha")]["seed"], sensitivity_boot[("TR", "alpha")]["seed"])
        self.assertEqual(
            main_boot[("TR", "alpha")]["cluster_count"],
            sensitivity_boot[("TR", "alpha")]["cluster_count"],
        )
        self.assertNotEqual(
            main_boot[("TR", "alpha")]["Delta_CI"],
            sensitivity_boot[("TR", "alpha")]["Delta_CI"],
        )

    def test_valid_bundle_writes_data_derived_table_csv_and_evidence_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, _audit = _fixture_bundle(Path(temporary))
            outputs = RENDERER.render_expansion_paper_results(
                PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
            )
            self.assertEqual(set(outputs), {"table", "plot_data", "note"})
            self.assertTrue(all(path.is_file() for path in outputs.values()))
            self.assertEqual(outputs["table"].parent, paper_dir)
            self.assertEqual(outputs["note"].parent, analysis_dir)

            table = outputs["table"].read_text(encoding="utf-8")
            self.assertIn(r"\begin{table}", table)
            self.assertIn("K=9 compounding estimates", table)
            self.assertIn("claude\\_sonnet46", table)
            self.assertIn("-0.075", table)

            csv_text = outputs["plot_data"].read_text(encoding="utf-8")
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            self.assertEqual(len(rows), 7 * 2 * 3 * 2 * 2)
            self.assertEqual(
                {row["cluster_unit"] for row in rows},
                {"underlying_task", "task_seed"},
            )
            self.assertEqual({row["null"] for row in rows}, {"common", "position"})
            self.assertEqual({row["K"] for row in rows}, {"8", "9", "10"})
            common = next(
                row for row in rows
                if row["K"] == "9" and row["null"] == "common"
                and row["cluster_unit"] == "underlying_task"
                and row["language"] == "AR" and row["model"] == "gemini"
            )
            position = next(
                row for row in rows
                if row["K"] == "9" and row["null"] == "position"
                and row["cluster_unit"] == "underlying_task"
                and row["language"] == "AR" and row["model"] == "gemini"
            )
            self.assertNotEqual(common["Delta"], position["Delta"])
            self.assertEqual(common["bootstrap_source"], "cf_summary")
            self.assertEqual(common["Delta_CI_low"], "-0.19")
            task_seed = next(
                row for row in rows
                if row["K"] == "9" and row["null"] == "common"
                and row["cluster_unit"] == "task_seed"
                and row["language"] == "AR" and row["model"] == "gemini"
            )
            self.assertEqual(task_seed["bootstrap_source"], "task_sensitivity_summary")
            sensitivity = json.loads(
                (analysis_dir / f"{PREFIX}_task_sensitivity_summary.json").read_text(encoding="utf-8")
            )
            sensitivity_scenario_interval = sensitivity["bootstrap_comparison"]["9"]["common"]["underlying_task"]["AR::gemini"]["Delta_CI"]
            self.assertNotEqual(float(common["Delta_CI_low"]), sensitivity_scenario_interval[0])
            note = outputs["note"].read_text(encoding="utf-8")
            self.assertIn("model order gemini, claude_sonnet46", note)
            self.assertIn("in claude_sonnet46, gemini order", note)

            note = outputs["note"].read_text(encoding="utf-8")
            for observed in ("| Selected tasks | 20 |", "| Gold-call positions | 186 |", "| Full trajectories | 640 |", "| Isolated replays | 5952 |"):
                self.assertIn(observed, note)
            self.assertIn("| 8 | common |", note)
            self.assertIn("| 10 | position |", note)
            self.assertIn('\"scenario_0\"', note)
            self.assertIn("wrong_argument", note)
            self.assertIn("changed the Delta sign in 1 of 14 cells", note)
            self.assertIn("changed CF reportability in 1 of 14 cells", note)
            self.assertIn("no significance claim", note)
            self.assertNotIn("paper/main.tex", note.split("Reproduce after")[0])

    def test_incomplete_audit_refuses_to_write_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, audit = _fixture_bundle(Path(temporary))
            audit["status"] = "running"
            (analysis_dir / f"{PREFIX}_collection_audit.json").write_text(
                json.dumps(audit), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "status is not 'complete'"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            self.assertFalse(paper_dir.exists())
            self.assertFalse((analysis_dir / f"{PREFIX}_paper_results_note.md").exists())

    def test_missing_offline_summary_refuses_to_write_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, _audit = _fixture_bundle(Path(temporary))
            (analysis_dir / f"{PREFIX}_task_sensitivity_summary.json").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "not ready"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            self.assertFalse(paper_dir.exists())

    def test_scope_mismatch_and_non_one_to_one_scenario_map_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, _audit = _fixture_bundle(Path(temporary))
            cf_path = analysis_dir / f"{PREFIX}_cf_summary.json"
            cf = json.loads(cf_path.read_text(encoding="utf-8"))
            cf["scope"]["task_trials"] -= 1
            cf_path.write_text(json.dumps(cf), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "trajectory count differs"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            cf["scope"]["task_trials"] += 1
            cf_path.write_text(json.dumps(cf), encoding="utf-8")

            sensitivity_path = analysis_dir / f"{PREFIX}_task_sensitivity_summary.json"
            sensitivity = json.loads(sensitivity_path.read_text(encoding="utf-8"))
            sensitivity["scope"]["scenario_family_to_task_variants"]["scenario_0"].append(
                sensitivity["scope"]["task_ids"][1]
            )
            sensitivity_path.write_text(json.dumps(sensitivity), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not one-to-one"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            self.assertFalse(paper_dir.exists())

    def test_point_estimate_mismatch_is_rejected_even_when_intervals_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, _audit = _fixture_bundle(Path(temporary))
            sensitivity_path = analysis_dir / f"{PREFIX}_task_sensitivity_summary.json"
            sensitivity = json.loads(sensitivity_path.read_text(encoding="utf-8"))
            sensitivity["leave_one_task_variant_out"]["9"]["common"]["full_point_estimates"]["TR::gemini"]["Delta"] += 0.01
            sensitivity_path.write_text(json.dumps(sensitivity), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "point estimate differs"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            self.assertFalse(paper_dir.exists())

    def test_existing_generated_artifact_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            analysis_dir, paper_dir, _audit = _fixture_bundle(Path(temporary))
            first = RENDERER.render_expansion_paper_results(
                PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
            )
            original = first["table"].read_text(encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                RENDERER.render_expansion_paper_results(
                    PREFIX, analysis_dir=analysis_dir, paper_dir=paper_dir
                )
            self.assertEqual(first["table"].read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
