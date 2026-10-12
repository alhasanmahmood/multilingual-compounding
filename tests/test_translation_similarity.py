from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for path in (SCRIPTS, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_translation_similarity as similarity  # noqa: E402


class WhitespaceTokenizer:
    def __call__(self, text, add_special_tokens=False, truncation=False):
        return {"input_ids": text.split()}

    @staticmethod
    def num_special_tokens_to_add(pair=False):
        return 2


class FakeEncoder:
    def __init__(self):
        self.tokenizer = WhitespaceTokenizer()
        self.max_seq_length = 16
        self.calls = []

    def encode(self, sentences, **kwargs):
        self.calls.append((list(sentences), kwargs))
        return [[float(index + 1), 1.0] for index, _ in enumerate(sentences)]


def localization_fixture():
    task_ids = [f"task_{index}" for index in range(similarity.EXPECTED_TASKS)]
    source_by_task = {}
    records = []
    for index, task_id in enumerate(task_ids):
        source = [f"Move 3 files and preserve 'doc{index}.txt'."]
        source_hash = f"source-hash-{index}"
        source_by_task[task_id] = (source, source_hash)
        for language in similarity.EXPECTED_LANGUAGES:
            if language == "EN":
                turns = list(source)
                record = {
                    "task_id": task_id,
                    "language_code": language,
                    "localized_turns": turns,
                    "task_content_sha256": source_hash,
                    "cache_integrity": "source_hash_verified",
                }
            else:
                task_label = chr(ord("A") + index)
                turns = [f"Translation task{task_label} has 3 items and keeps 'doc{index}.txt'."]
                record = {
                    "task_id": task_id,
                    "language_code": language,
                    "localized_turns": turns,
                    "task_content_sha256": source_hash,
                    "cache_integrity": "source_hash_verified",
                    "ai_review": {
                        "status": "reviewed",
                        "unresolved_issues": [],
                        "source_task_sha256": source_hash,
                        "localized_turns_sha256": similarity.canonical_turns_sha256(turns),
                    },
                }
            records.append(record)
    return task_ids, source_by_task, records


class TranslationSimilarityTests(unittest.TestCase):
    def test_saved_evidence_paths_resolve_inside_relocated_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            relocated = pathlib.Path(temporary)
            with patch.object(similarity, "REPO_ROOT", relocated):
                expected = relocated / "analysis/bfcl/newstudy20261010_plan.json"
                for old_path in (
                    "F:/old-checkout/analysis/bfcl/newstudy20261010_plan.json",
                    r"F:\old-checkout\analysis\bfcl\newstudy20261010_plan.json",
                    "/old-checkout/analysis/bfcl/newstudy20261010_plan.json",
                    "analysis/bfcl/newstudy20261010_plan.json",
                ):
                    self.assertEqual(similarity._resolve_repo_path(old_path), expected.resolve())
                with self.assertRaisesRegex(similarity.DiagnosticError, "escapes"):
                    similarity._resolve_repo_path("F:/old-checkout/data/bfcl/../../outside.json")

    def test_emitted_path_provenance_is_portable_and_keeps_cli_options(self):
        with tempfile.TemporaryDirectory(prefix="codex_private_user_") as temporary:
            profile = pathlib.Path(temporary)
            checkout = profile / "private_checkout"
            model_path = profile / ".cache" / "labse" / "snapshot"
            manifest = checkout / "analysis/bfcl/model_manifest.json"
            cache = checkout / "data/bfcl/localized_queries/cache.jsonl"
            audit = checkout / "analysis/bfcl/audit.json"
            plan = checkout / "analysis/bfcl/plan.json"
            negation = checkout / "analysis/bfcl/negation.json"
            output_dir = checkout / "analysis/bfcl/output"
            revision = "a" * 40
            argv = [
                str(profile / ".venv/Scripts/python.exe"),
                str(checkout / "scripts/run_translation_similarity.py"),
                "--model-revision", revision,
                "--model-path", str(model_path),
                "--model-manifest", str(manifest),
                "--cache", str(cache),
                "--audit", str(audit),
                "--negation-controls", str(negation),
                f"--output-dir={output_dir}",
                "--device", "cpu",
                "--batch-size", "8",
            ]

            with patch.object(similarity, "REPO_ROOT", checkout):
                sanitized = similarity._sanitize_command_argv(argv)
                self.assertEqual(
                    similarity._portable_path(cache, kind="cache"),
                    "data/bfcl/localized_queries/cache.jsonl",
                )
                reported_paths = {
                    "cache_path": similarity._portable_path(cache, kind="cache"),
                    "collection_audit_path": similarity._portable_path(audit, kind="audit"),
                    "plan_path": similarity._portable_path(plan, kind="plan"),
                    "negation_controls_path": similarity._portable_path(
                        negation, kind="negation-controls"
                    ),
                    "model_path": similarity._portable_path(model_path, kind="model-path"),
                    "model_manifest_path": similarity._portable_path(
                        manifest, kind="model-manifest"
                    ),
                }
                self.assertNotIn("codex_private_user_", json.dumps(reported_paths))
                self.assertEqual(
                    reported_paths["cache_path"],
                    "data/bfcl/localized_queries/cache.jsonl",
                )
                self.assertEqual(
                    reported_paths["collection_audit_path"],
                    "analysis/bfcl/audit.json",
                )
                self.assertEqual(reported_paths["plan_path"], "analysis/bfcl/plan.json")
                self.assertEqual(
                    reported_paths["negation_controls_path"],
                    "analysis/bfcl/negation.json",
                )
                self.assertEqual(reported_paths["model_path"], "<local-model-snapshot>")
                self.assertEqual(
                    reported_paths["model_manifest_path"],
                    "analysis/bfcl/model_manifest.json",
                )
                self.assertEqual(
                    similarity._portable_path(
                        r"F:\Users\codex_private_user\Desktop\cache.jsonl",
                        kind="cache",
                    ),
                    "<external-cache>",
                )

            joined = " ".join(sanitized)
            self.assertNotIn("codex_private_user_", joined)
            self.assertNotIn(str(checkout), joined)
            self.assertIn("--model-revision", sanitized)
            self.assertIn(revision, sanitized)
            self.assertIn("--model-path", sanitized)
            self.assertIn("<local-model-snapshot>", sanitized)
            self.assertIn("--model-manifest", sanitized)
            self.assertIn("analysis/bfcl/model_manifest.json", sanitized)
            self.assertIn("--cache", sanitized)
            self.assertIn("data/bfcl/localized_queries/cache.jsonl", sanitized)
            self.assertIn("--audit", sanitized)
            self.assertIn("analysis/bfcl/audit.json", sanitized)
            self.assertIn("--negation-controls", sanitized)
            self.assertIn("analysis/bfcl/negation.json", sanitized)
            self.assertIn("--output-dir=analysis/bfcl/output", sanitized)
            self.assertEqual(sanitized[-4:], ["--device", "cpu", "--batch-size", "8"])

    def test_localization_rows_require_complete_pairing_and_current_review_hashes(self):
        task_ids, source_by_task, records = localization_fixture()
        indexed = similarity.validate_localization_rows(records, task_ids, source_by_task)
        self.assertEqual(len(indexed), 160)

        stale = [dict(record) for record in records]
        stale_target = next(row for row in stale if row["language_code"] == "TR")
        stale_target["ai_review"] = dict(stale_target["ai_review"])
        stale_target["ai_review"]["localized_turns_sha256"] = "0" * 64
        with self.assertRaisesRegex(similarity.DiagnosticError, "target hash is stale"):
            similarity.validate_localization_rows(stale, task_ids, source_by_task)

        duplicate = records + [dict(records[0])]
        with self.assertRaisesRegex(similarity.DiagnosticError, "Duplicate localization"):
            similarity.validate_localization_rows(duplicate, task_ids, source_by_task)

    def test_cache_and_plan_hashes_are_checked_against_collection_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            plan_path = root / "plan.json"
            cache_path = root / "cache.jsonl"
            audit_path = root / "audit.json"
            task_ids = [f"task_{index}" for index in range(similarity.EXPECTED_TASKS)]
            plan_path.write_text(json.dumps({"task_ids": task_ids}), encoding="utf-8")
            cache_path.write_text("\n".join(["{}"] * similarity.EXPECTED_CACHE_ROWS), encoding="utf-8")
            plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            cache_hash = hashlib.sha256(cache_path.read_bytes()).hexdigest()
            audit = {
                "status": "complete",
                "counts": {
                    "tasks": 20,
                    "unique_scenarios": 20,
                    "localization_rows": 160,
                    "languages": list(similarity.EXPECTED_LANGUAGES),
                },
                "provenance": {
                    "plan_path": str(plan_path),
                    "plan_sha256": plan_hash,
                    "localization_cache_path": str(cache_path),
                    "localization_cache_sha256": cache_hash,
                },
            }
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            _, _, resolved_cache, _, rows = similarity.verify_audit_and_cache(audit_path)
            self.assertEqual(resolved_cache, cache_path)
            self.assertEqual(len(rows), 160)

            cache_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(similarity.DiagnosticError, "cache hash"):
                similarity.verify_audit_and_cache(audit_path)

    def test_numeric_normalization_and_direct_literal_flags_are_separate(self):
        source = "Use 3.5 liters with 'report.txt'."
        target = "استخدم ٣,٥ لتر مع 'report.txt'."
        checked = similarity.inspect_literal_constraints(source, target)
        self.assertEqual(checked["source_numbers"], ["3.5"])
        self.assertEqual(checked["target_numbers"], ["3.5"])
        self.assertTrue(checked["numeric_values_match"])
        self.assertTrue(checked["source_quoted_literals_preserved"])
        self.assertTrue(checked["source_filenames_preserved"])
        self.assertFalse(checked["needs_manual_review"])
        self.assertEqual(similarity.numeric_values("القيمة ٣٫٥، ثم ١٬٠٠٠"), ["3.5", "1000"])
        self.assertEqual(similarity.source_filenames("Use 3.5 liters and 'report.txt'."), ["report.txt"])

        changed = similarity.inspect_literal_constraints(source, "استخدم ٣,٦ لتر مع 'other.txt'.")
        self.assertFalse(changed["numeric_values_match"])
        self.assertEqual(changed["missing_source_quoted_literals"], ["report.txt"])
        self.assertEqual(changed["missing_source_filenames"], ["report.txt"])
        self.assertTrue(changed["needs_manual_review"])

    def test_control_corruptions_are_deterministic_target_side_changes(self):
        self.assertEqual(similarity.corrupt_first_number("Use value 12.5 now."), "Use value 12.6 now.")
        self.assertEqual(similarity.corrupt_first_number("Use value ٣ now."), "Use value ٤ now.")
        self.assertIsNone(similarity.corrupt_first_number("No numeric value."))
        result = similarity.corrupt_first_source_literal(
            "Keep 'budget.csv' unchanged.", "حافظ على 'budget.csv' كما هو."
        )
        self.assertEqual(result, ("budget.csv", "حافظ على 'budget.csv_changed' كما هو."))

    def test_authored_corruptions_and_mismatched_task_controls_are_labeled(self):
        task_ids, source_by_task, records = localization_fixture()
        indexed = similarity.validate_localization_rows(records, task_ids, source_by_task)
        pairs = similarity._nonempty_pairs(task_ids, source_by_task, indexed)
        negation = {
            "provenance": {"authoring": "AI-authored", "review": "separately AI-reviewed"},
            "records": [{
                "control_id": "tr_1",
                "language_code": "TR",
                "source_text": "Keep this file.",
                "correct_text": "Bu dosyayı sakla.",
                "corrupted_text": "Bu dosyayı saklama.",
                "corruption_type": "negation_reversal",
            }],
        }
        controls = similarity._build_controls(pairs, task_ids, source_by_task, indexed, negation)
        control_classes = {row["control_class"] for row in controls}
        self.assertIn("real_bfcl_target_corruption", control_classes)
        self.assertIn("real_task_cross_pair_control", control_classes)
        self.assertIn("artificial_authored_challenge", control_classes)
        self.assertTrue(any(row["control_type"] == "number_changed" for row in controls))
        self.assertTrue(any(row["control_type"] == "quoted_literal_or_filename_changed" for row in controls))
        self.assertTrue(any(row["control_type"] == "mismatched_task_turn" for row in controls))
        self.assertEqual(sum(row["control_type"] == "mismatched_task_turn" for row in controls), 140)

    def test_over_limit_text_fails_without_silent_truncation(self):
        tokenizer = WhitespaceTokenizer()
        windows, token_count = similarity.prepare_token_windows("one two three", tokenizer, max_seq_length=5)
        self.assertEqual(windows, [("one two three", 3)])
        self.assertEqual(token_count, 3)
        with self.assertRaisesRegex(similarity.DiagnosticError, "no truncation or chunking"):
            similarity.prepare_token_windows("one two three four", tokenizer, max_seq_length=5)

    def test_score_texts_encodes_deduplicated_inputs_and_normalizes_vectors(self):
        model = FakeEncoder()
        embeddings, layout = similarity._score_texts(["source text", "target text", "source text"], model, 8)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][0], ["source text", "target text"])
        self.assertEqual(model.calls[0][1]["normalize_embeddings"], False)
        self.assertEqual(layout["source text"], {"token_count": 2, "chunk_count": 1})
        self.assertAlmostEqual(sum(value * value for value in embeddings["source text"]), 1.0)
        self.assertAlmostEqual(
            similarity.cosine_similarity(embeddings["source text"], embeddings["target text"]),
            3 / (10**0.5),
        )

    def test_cosine_and_percentile_math_are_correct(self):
        self.assertAlmostEqual(similarity.cosine_similarity([1.0, 0.0], [3.0, 4.0]), 0.6)
        self.assertAlmostEqual(similarity.cosine_similarity([1.0, 1.0], [1.0, 1.0]), 1.0)
        self.assertAlmostEqual(similarity._percentile([0.0, 1.0, 2.0], 0.5), 1.0)

    def test_writer_refuses_to_overwrite_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            (directory / "existing.csv").write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(similarity.DiagnosticError, "Refusing to overwrite"):
                similarity._write_outputs_without_overwrite(directory, {"existing.csv": "replacement"})
            self.assertEqual((directory / "existing.csv").read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
