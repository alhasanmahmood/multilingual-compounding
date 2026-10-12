"""Run a reproducible, non-threshold LaBSE translation consistency diagnostic.

This tool scores direct English-to-target turns from the frozen BFCL localization
cache. It does not score backtranslations and does not interpret cosine similarity
as translation accuracy. Inputs over the tokenizer limit fail explicitly, with no
truncation or chunking.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.bfcl_vendor import load_bfcl_multiturn_tasks  # noqa: E402
from multilingual_compounding.evaluation import get_original_turn_texts, task_content_sha256  # noqa: E402
from multilingual_compounding.settings import PILOT_TEST_CATEGORIES  # noqa: E402


MODEL_ID = "sentence-transformers/LaBSE"
EXPECTED_LANGUAGES = ("EN", "AR", "TR", "ZH", "HI", "JA", "ES", "SW")
EXPECTED_TASKS = 20
EXPECTED_CACHE_ROWS = EXPECTED_TASKS * len(EXPECTED_LANGUAGES)
AI_REVIEW_STATUSES = {"reviewed", "corrected"}
LOCALIZATION_HASH_FIELDS = ("localized_turns_sha256", "target_turns_sha256")

# Kept aligned with the source-literal pattern used by robustness validation.
SOURCE_QUOTED_PATTERN = re.compile(r"(?<!\w)'([^'\n]+)'(?!\w)|\"([^\"\n]+)\"")
FILENAME_PATTERN = re.compile(r"(?<![\w/.-])[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*\.[A-Za-z]{1,8}(?![\w.-])")
NUMBER_PATTERN = re.compile(r"(?<![\w])[-+]?(?:\d+(?:[.,\u066B\u066C]\d+)?|[.,\u066B\u066C]\d+)(?![\w])")
REVISION_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
PATH_OPTIONS = {
    "--audit": "audit",
    "--cache": "cache",
    "--negation-controls": "negation-controls",
    "--output-dir": "output-dir",
    "--model-path": "model-path",
    "--model-manifest": "model-manifest",
}

OUTPUT_NAMES = (
    "newstudy20261010_labse_pairs.csv",
    "newstudy20261010_labse_controls.csv",
    "newstudy20261010_labse_summary.json",
    "newstudy20261010_labse_report.md",
)


class DiagnosticError(ValueError):
    """Raised when source, cache, model, or output integrity checks fail."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_absolute_path(value: str) -> bool:
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _portable_path(value: str | Path, *, kind: str = "path") -> str:
    """Return a repository-relative path or a neutral label for external paths."""
    if kind == "model-path":
        return "<local-model-snapshot>"
    raw_path = str(value)
    candidate = Path(raw_path).expanduser()
    # A Windows path may appear in preserved argv while this code is being
    # inspected or run on another platform. Do not reinterpret it as a local
    # relative filename and accidentally retain its profile components.
    if PureWindowsPath(raw_path).is_absolute() and not candidate.is_absolute():
        return f"<external-{kind}>"
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return f"<external-{kind}>"
    return relative.as_posix()


def _sanitize_command_argv(argv: Sequence[str]) -> list[str]:
    """Keep command settings while removing checkout and profile paths."""
    sanitized: list[str] = []
    path_option: str | None = None
    for index, token in enumerate(argv):
        if path_option is not None:
            sanitized.append(_portable_path(token, kind=PATH_OPTIONS[path_option]))
            path_option = None
            continue

        option, separator, value = token.partition("=")
        if separator and option in PATH_OPTIONS:
            sanitized.append(
                f"{option}={_portable_path(value, kind=PATH_OPTIONS[option])}"
            )
            continue
        if token in PATH_OPTIONS:
            sanitized.append(token)
            path_option = token
            continue

        # argv[0] is often a machine-specific Python executable. Other absolute
        # paths may be supplied positionally, so normalize or redact those too.
        if _is_absolute_path(token):
            sanitized.append(_portable_path(token, kind="executable" if index == 0 else "path"))
        else:
            sanitized.append(token)
    return sanitized


def canonical_turns_sha256(turns: Sequence[str]) -> str:
    serialized = json.dumps(
        list(turns), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _resolve_repo_path(value: str | Path) -> Path:
    # Preserve historical provenance bytes while reading this checkout's evidence.
    # Saved Windows absolute paths must also work in Linux or relocated copies.
    normalized = str(value).replace("\\", "/")
    for anchor in ("analysis/bfcl/", "data/bfcl/"):
        index = normalized.find(anchor)
        if index >= 0:
            candidate = (REPO_ROOT / normalized[index:]).resolve()
            evidence_root = (REPO_ROOT / anchor).resolve()
            if not candidate.is_relative_to(evidence_root):
                raise DiagnosticError("Evidence path escapes its repository directory.")
            return candidate
    candidate = Path(normalized)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DiagnosticError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise DiagnosticError(f"Expected an object in {path}:{line_number}.")
            rows.append(row)
    return rows


def verify_audit_and_cache(
    audit_path: Path,
    cache_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path, list[dict[str, Any]]]:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "complete":
        raise DiagnosticError("The collection audit is not marked complete.")
    provenance = audit.get("provenance")
    if not isinstance(provenance, dict):
        raise DiagnosticError("The collection audit has no provenance object.")

    plan_path = _resolve_repo_path(provenance.get("plan_path", ""))
    if not plan_path.is_file():
        raise DiagnosticError(f"The collection plan is missing: {plan_path}")
    plan_hash = sha256_file(plan_path)
    if plan_hash != provenance.get("plan_sha256"):
        raise DiagnosticError("The collection plan hash does not match the audit.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    task_ids = plan.get("task_ids")
    if not isinstance(task_ids, list) or len(task_ids) != EXPECTED_TASKS:
        raise DiagnosticError(f"Expected {EXPECTED_TASKS} task IDs in the plan.")
    if len(set(map(str, task_ids))) != EXPECTED_TASKS:
        raise DiagnosticError("The plan contains duplicate task IDs.")

    resolved_cache = cache_path or _resolve_repo_path(provenance.get("localization_cache_path", ""))
    if not resolved_cache.is_file():
        raise DiagnosticError(f"The frozen localization cache is missing: {resolved_cache}")
    cache_hash = sha256_file(resolved_cache)
    expected_cache_hash = provenance.get("localization_cache_sha256")
    if not expected_cache_hash or cache_hash != expected_cache_hash:
        raise DiagnosticError("The localization cache hash does not match the collection audit.")

    counts = audit.get("counts", {})
    if counts.get("tasks") != EXPECTED_TASKS or counts.get("unique_scenarios") != EXPECTED_TASKS:
        raise DiagnosticError("The collection audit does not describe the expected 20 scenarios.")
    if counts.get("localization_rows") != EXPECTED_CACHE_ROWS:
        raise DiagnosticError(f"Expected {EXPECTED_CACHE_ROWS} localization rows in the audit.")
    audit_languages = tuple(counts.get("languages", ()))
    if set(audit_languages) != set(EXPECTED_LANGUAGES):
        raise DiagnosticError("The collection audit language set is not the expected eight languages.")
    rows = read_jsonl(resolved_cache)
    if len(rows) != EXPECTED_CACHE_ROWS:
        raise DiagnosticError(f"Expected {EXPECTED_CACHE_ROWS} cache rows, found {len(rows)}.")
    return audit, plan, resolved_cache, plan_path, rows


def validate_localization_rows(
    records: Sequence[dict[str, Any]],
    task_ids: Sequence[str],
    source_by_task: dict[str, tuple[list[str], str]],
    languages: Sequence[str] = EXPECTED_LANGUAGES,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Check complete task-language pairing, source hashes, and current AI review hashes."""
    expected_tasks = [str(task_id) for task_id in task_ids]
    if len(expected_tasks) != EXPECTED_TASKS or len(set(expected_tasks)) != EXPECTED_TASKS:
        raise DiagnosticError(f"Expected {EXPECTED_TASKS} distinct selected task IDs.")
    if set(expected_tasks) != set(source_by_task):
        raise DiagnosticError("Current BFCL source tasks do not match the selected plan IDs.")

    expected_keys = {(task_id, language) for task_id in expected_tasks for language in languages}
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("task_id", "")), str(record.get("language_code", "")))
        if key in by_key:
            raise DiagnosticError(f"Duplicate localization cache row: {key}.")
        if key not in expected_keys:
            raise DiagnosticError(f"Unexpected localization cache row: {key}.")
        by_key[key] = record
    if set(by_key) != expected_keys:
        missing = sorted(expected_keys - set(by_key))
        raise DiagnosticError(f"Localization cache is missing expected task-language rows: {missing[:5]}.")

    for (task_id, language), record in by_key.items():
        source_turns, source_hash = source_by_task[task_id]
        turns = record.get("localized_turns")
        if not isinstance(turns, list) or any(not isinstance(turn, str) for turn in turns):
            raise DiagnosticError(f"Localization turns are malformed for {(task_id, language)}.")
        if len(turns) != len(source_turns):
            raise DiagnosticError(f"Turn alignment length differs for {(task_id, language)}.")
        if record.get("task_content_sha256") != source_hash:
            raise DiagnosticError(f"Cache source task hash is stale for {(task_id, language)}.")
        if record.get("cache_integrity") != "source_hash_verified":
            raise DiagnosticError(f"Cache source integrity is not verified for {(task_id, language)}.")
        for index, (source_turn, target_turn) in enumerate(zip(source_turns, turns)):
            if bool(source_turn.strip()) != bool(target_turn.strip()):
                raise DiagnosticError(
                    f"Blank-turn alignment differs for {(task_id, language, index)}."
                )
        if language == "EN":
            if turns != source_turns:
                raise DiagnosticError(f"English identity row differs from source for {task_id}.")
            continue

        ai_review = record.get("ai_review")
        if not isinstance(ai_review, dict):
            raise DiagnosticError(f"AI review metadata is missing for {(task_id, language)}.")
        if ai_review.get("status") not in AI_REVIEW_STATUSES:
            raise DiagnosticError(f"AI review is not current for {(task_id, language)}.")
        if ai_review.get("unresolved_issues") != []:
            raise DiagnosticError(f"Unresolved AI review issues remain for {(task_id, language)}.")
        if ai_review.get("source_task_sha256") != source_hash:
            raise DiagnosticError(f"AI review source hash is stale for {(task_id, language)}.")
        target_hash = canonical_turns_sha256(turns)
        stored_hash = next(
            (ai_review.get(field) for field in LOCALIZATION_HASH_FIELDS if ai_review.get(field)),
            None,
        )
        if stored_hash != target_hash:
            raise DiagnosticError(f"AI review target hash is stale for {(task_id, language)}.")
    return by_key


def _digit_value(character: str) -> int:
    try:
        return unicodedata.digit(character)
    except (TypeError, ValueError):
        return int(character)


def normalize_number(raw: str) -> str:
    converted: list[str] = []
    for character in raw:
        if character.isdigit():
            converted.append(str(_digit_value(character)))
        elif character == "٫":
            converted.append(".")
        elif character == "٬":
            continue
        else:
            converted.append(character)
    value = "".join(converted)
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    return value


def numeric_values(text: str) -> list[str]:
    return [normalize_number(match.group(0)) for match in NUMBER_PATTERN.finditer(text)]


def source_quoted_literals(text: str) -> list[str]:
    return [left or right for left, right in SOURCE_QUOTED_PATTERN.findall(text)]


def source_filenames(text: str) -> list[str]:
    return list(dict.fromkeys(
        value for value in FILENAME_PATTERN.findall(text)
        if NUMBER_PATTERN.fullmatch(value) is None
    ))


def inspect_literal_constraints(source: str, target: str) -> dict[str, Any]:
    source_numbers = numeric_values(source)
    target_numbers = numeric_values(target)
    quoted = list(dict.fromkeys(source_quoted_literals(source)))
    filenames = source_filenames(source)
    missing_quoted = [literal for literal in quoted if literal not in target]
    missing_filenames = [literal for literal in filenames if literal not in target]
    return {
        "source_numbers": source_numbers,
        "target_numbers": target_numbers,
        "numeric_values_match": Counter(source_numbers) == Counter(target_numbers),
        "source_quoted_literals": quoted,
        "missing_source_quoted_literals": missing_quoted,
        "source_quoted_literals_preserved": not missing_quoted,
        "source_filenames": filenames,
        "missing_source_filenames": missing_filenames,
        "source_filenames_preserved": not missing_filenames,
        "needs_manual_review": bool(missing_quoted or missing_filenames or Counter(source_numbers) != Counter(target_numbers)),
    }


def corrupt_first_number(text: str) -> str | None:
    """Change the last digit of the first numeric token, preserving its digit script."""
    match = NUMBER_PATTERN.search(text)
    if not match:
        return None
    token = match.group(0)
    digit_indices = [index for index, character in enumerate(token) if character.isdigit()]
    if not digit_indices:
        return None
    index = digit_indices[-1]
    original = token[index]
    new_value = (_digit_value(original) + 1) % 10
    try:
        replacement = chr(ord(original) - _digit_value(original) + new_value)
    except (TypeError, ValueError):
        replacement = str(new_value)
    mutated = token[:index] + replacement + token[index + 1 :]
    if normalize_number(mutated) == normalize_number(token):
        replacement = str(new_value)
        mutated = token[:index] + replacement + token[index + 1 :]
    return text[: match.start()] + mutated + text[match.end() :]


def corrupt_first_source_literal(source: str, target: str) -> tuple[str, str] | None:
    for literal in source_quoted_literals(source):
        if literal in target:
            replacement = literal + "_changed"
            return literal, target.replace(literal, replacement, 1)
    for literal in source_filenames(source):
        if literal in target:
            stem, suffix = literal.rsplit(".", 1)
            replacement = f"{stem}_changed.{suffix}"
            return literal, target.replace(literal, replacement, 1)
    return None


def prepare_token_windows(text: str, tokenizer: Any, max_seq_length: int) -> tuple[list[tuple[str, int]], int]:
    """Return one intact input or fail explicitly when it exceeds the model limit."""
    token_ids = list(tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"])
    special_count = int(tokenizer.num_special_tokens_to_add(pair=False))
    body_limit = max_seq_length - special_count
    if body_limit < 1:
        raise DiagnosticError("The model sequence limit leaves no room for text tokens.")
    if not token_ids:
        return [(text, 1)], 0
    if len(token_ids) > body_limit:
        raise DiagnosticError(
            f"Input has {len(token_ids)} content tokens, exceeding the model limit of "
            f"{body_limit}; no truncation or chunking was applied."
        )
    return [(text, len(token_ids))], len(token_ids)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        raise DiagnosticError("Cosine similarity requires equal nonempty vectors.")
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if not left_norm or not right_norm:
        raise DiagnosticError("Cosine similarity is undefined for a zero vector.")
    return sum(float(a) * float(b) for a, b in zip(left, right)) / (left_norm * right_norm)


def unit_vector(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if not vector or not math.isfinite(norm) or norm == 0:
        raise DiagnosticError("Embedding has zero or non-finite norm.")
    return [float(value) / norm for value in vector]


def _load_model(model_id: str, revision: str, device: str, model_path: Path | None) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise DiagnosticError("sentence-transformers is required to run the LaBSE diagnostic.") from exc
    resolved_device = None if device == "auto" else device
    if model_path is not None:
        return SentenceTransformer(str(model_path), device=resolved_device, local_files_only=True)
    return SentenceTransformer(model_id, revision=revision, device=resolved_device)


def verify_model_manifest(model_dir: Path, manifest_path: Path, model_id: str, revision: str) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_id") != model_id or manifest.get("revision", "").lower() != revision.lower():
        raise DiagnosticError("The downloaded model manifest does not match model ID and pinned revision.")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise DiagnosticError("The model manifest does not list model files.")
    root = model_dir.resolve()
    for item in files:
        candidate = (root / Path(str(item.get("path", "")))).resolve()
        if not candidate.is_relative_to(root):
            raise DiagnosticError("Model manifest contains a path outside the model directory.")
        if not candidate.is_file():
            raise DiagnosticError(f"Pinned model file is missing: {candidate}")
        if candidate.stat().st_size != item.get("bytes") or sha256_file(candidate) != item.get("sha256"):
            raise DiagnosticError(f"Pinned model file hash or size differs: {candidate}")
    return sha256_file(manifest_path)


def _software_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for package in ("sentence-transformers", "transformers", "torch", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _nonempty_pairs(
    plan_task_ids: Sequence[str],
    source_by_task: dict[str, tuple[list[str], str]],
    cache_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for task_id in plan_task_ids:
        source_turns, _ = source_by_task[str(task_id)]
        for language in EXPECTED_LANGUAGES:
            if language == "EN":
                continue
            record = cache_by_key[(str(task_id), language)]
            target_turns = record["localized_turns"]
            for turn_index, (source, target) in enumerate(zip(source_turns, target_turns)):
                if not source.strip() and not target.strip():
                    continue
                pairs.append({
                    "pair_id": f"{task_id}/{language}/{turn_index}",
                    "task_id": str(task_id),
                    "language_code": language,
                    "turn_index": turn_index,
                    "source_text": source,
                    "target_text": target,
                    "ai_review_status": record["ai_review"]["status"],
                })
    return pairs


def _build_controls(
    pairs: Sequence[dict[str, Any]],
    plan_task_ids: Sequence[str],
    source_by_task: dict[str, tuple[list[str], str]],
    cache_by_key: dict[tuple[str, str], dict[str, Any]],
    negation_controls: dict[str, Any],
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for pair in pairs:
        source = pair["source_text"]
        target = pair["target_text"]
        nums_source = numeric_values(source)
        nums_target = numeric_values(target)
        changed_number = corrupt_first_number(target) if nums_source and Counter(nums_source) == Counter(nums_target) else None
        if changed_number is not None:
            controls.append({
                "control_id": f"number:{pair['pair_id']}",
                "control_type": "number_changed",
                "control_class": "real_bfcl_target_corruption",
                "language_code": pair["language_code"],
                "task_id": pair["task_id"],
                "turn_index": pair["turn_index"],
                "source_text": source,
                "baseline_target": target,
                "comparison_target": changed_number,
                "corrupted_literal": "number",
            })
        changed_literal = corrupt_first_source_literal(source, target)
        if changed_literal is not None:
            literal, corrupted = changed_literal
            controls.append({
                "control_id": f"literal:{pair['pair_id']}",
                "control_type": "quoted_literal_or_filename_changed",
                "control_class": "real_bfcl_target_corruption",
                "language_code": pair["language_code"],
                "task_id": pair["task_id"],
                "turn_index": pair["turn_index"],
                "source_text": source,
                "baseline_target": target,
                "comparison_target": corrupted,
                "corrupted_literal": literal,
            })

    ordered_tasks = [str(task_id) for task_id in plan_task_ids]
    for language in EXPECTED_LANGUAGES:
        if language == "EN":
            continue
        for index, task_id in enumerate(ordered_tasks):
            other_task_id = ordered_tasks[(index + 1) % len(ordered_tasks)]
            source_turns, _ = source_by_task[task_id]
            current_target = cache_by_key[(task_id, language)]["localized_turns"]
            other_target = cache_by_key[(other_task_id, language)]["localized_turns"]
            for turn_index, (source, baseline) in enumerate(zip(source_turns, current_target)):
                if not source.strip() or not baseline.strip() or turn_index >= len(other_target):
                    continue
                mismatched = other_target[turn_index]
                if not mismatched.strip():
                    continue
                controls.append({
                    "control_id": f"mismatch:{task_id}:{language}:{turn_index}:{other_task_id}",
                    "control_type": "mismatched_task_turn",
                    "control_class": "real_task_cross_pair_control",
                    "language_code": language,
                    "task_id": task_id,
                    "other_task_id": other_task_id,
                    "turn_index": turn_index,
                    "source_text": source,
                    "baseline_target": baseline,
                    "comparison_target": mismatched,
                    "corrupted_literal": "",
                })

    provenance = negation_controls.get("provenance")
    negation_rows = negation_controls.get("records")
    if not isinstance(provenance, dict) or not provenance:
        raise DiagnosticError("Negation controls must include their authoring and review provenance.")
    if not isinstance(negation_rows, list) or not negation_rows:
        raise DiagnosticError("No authored negation controls were supplied.")
    for row in negation_rows:
        required = ("control_id", "language_code", "source_text", "correct_text", "corrupted_text", "corruption_type")
        if any(not isinstance(row.get(field), str) or not row[field].strip() for field in required):
            raise DiagnosticError("Malformed authored negation control record.")
        if row["corruption_type"] != "negation_reversal":
            raise DiagnosticError(f"Unexpected negation control type: {row['corruption_type']}.")
        if row["language_code"] not in EXPECTED_LANGUAGES or row["language_code"] == "EN":
            raise DiagnosticError(f"Unexpected language for negation control {row['control_id']}.")
        controls.append({
            "control_id": f"negation:{row['control_id']}",
            "control_type": "negation_reversal",
            "control_class": "artificial_authored_challenge",
            "language_code": row["language_code"],
            "task_id": "",
            "turn_index": "",
            "source_text": row["source_text"],
            "baseline_target": row["correct_text"],
            "comparison_target": row["corrupted_text"],
            "corrupted_literal": "negation",
            "control_provenance": json.dumps(provenance, ensure_ascii=False, sort_keys=True),
        })
    return controls


def _score_texts(
    texts: Iterable[str],
    model: Any,
    batch_size: int,
) -> tuple[dict[str, list[float]], dict[str, dict[str, int]]]:
    tokenizer = getattr(model, "tokenizer", None)
    max_seq_length = getattr(model, "max_seq_length", None)
    if tokenizer is None or not isinstance(max_seq_length, int):
        raise DiagnosticError("Loaded model must expose its tokenizer and max_seq_length.")
    text_windows: dict[str, list[tuple[str, int]]] = {}
    token_counts: dict[str, int] = {}
    unique_chunks: dict[str, None] = {}
    for text in dict.fromkeys(texts):
        if not isinstance(text, str) or not text.strip():
            raise DiagnosticError("Only nonempty text can be scored.")
        windows, count = prepare_token_windows(text, tokenizer, max_seq_length)
        text_windows[text] = windows
        token_counts[text] = count
        for chunk, _ in windows:
            unique_chunks.setdefault(chunk, None)

    chunk_texts = list(unique_chunks)
    if not chunk_texts:
        raise DiagnosticError("No input text was prepared for embedding.")
    vectors = model.encode(
        chunk_texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=False,
        show_progress_bar=True,
    )
    if len(vectors) != len(chunk_texts):
        raise DiagnosticError("Encoder returned a different number of vectors than input chunks.")
    chunk_vectors = {chunk: list(map(float, vector)) for chunk, vector in zip(chunk_texts, vectors)}

    normalized: dict[str, list[float]] = {}
    layout: dict[str, dict[str, int]] = {}
    for text, windows in text_windows.items():
        chunk_embeds = [chunk_vectors[chunk] for chunk, _ in windows]
        if len(chunk_embeds) != 1:
            raise DiagnosticError("No-chunking policy expected exactly one embedding per text.")
        normalized[text] = unit_vector(chunk_embeds[0])
        layout[text] = {"token_count": token_counts[text], "chunk_count": len(windows)}
    return normalized, layout


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise DiagnosticError("Cannot summarize an empty score list.")
    ordered = sorted(float(value) for value in values)
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize_pair_scores(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_language: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_language[str(row["language_code"])].append(float(row["cosine_similarity"]))
    return {
        language: {
            "nonempty_pairs": len(values),
            "median": statistics.median(values),
            "p10": _percentile(values, 0.10),
            "minimum": min(values),
            "mean": statistics.fmean(values),
        }
        for language, values in sorted(by_language.items())
    }


def _csv_text(rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> str:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            key: json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (list, dict))
            else value
            for key, value in row.items()
        })
    return buffer.getvalue()


def _truncate_report_text(value: str, maximum: int = 220) -> str:
    compact = " ".join(value.split())
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 1] + "…"


def build_report(
    pair_rows: Sequence[dict[str, Any]],
    control_rows: Sequence[dict[str, Any]],
    summary: dict[str, Any],
    provenance: dict[str, Any],
    bottom_pairs: int,
) -> str:
    lines = [
        "# LaBSE translation consistency diagnostic",
        "",
        "This local diagnostic compares each direct English source turn with its current target-language turn. It does not use backtranslations. Cosine scores measure embedding similarity, not translation accuracy or probability of correctness. No universal pass threshold is applied.",
        "",
        f"- Model: `{provenance['model_id']}` at pinned revision `{provenance['model_revision']}`",
        f"- Frozen localization cache SHA-256: `{provenance['cache_sha256']}`",
        f"- Collection audit SHA-256: `{provenance['collection_audit_sha256']}`",
        f"- Scored nonempty direct pairs: {len(pair_rows)} across {len(summary)} languages",
        f"- Encoder window policy: {provenance['chunk_policy']}",
        "",
        "## Score distribution by language",
        "",
        "| Language | Pairs | Median | 10th percentile | Minimum | Mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language, values in summary.items():
        lines.append(
            f"| {language} | {values['nonempty_pairs']} | {values['median']:.4f} | {values['p10']:.4f} | {values['minimum']:.4f} | {values['mean']:.4f} |"
        )

    lines.extend(["", "## Lowest-scoring real pairs for manual inspection", ""])
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        by_language[str(row["language_code"])].append(row)
    for language in sorted(by_language):
        lines.extend([f"### {language}", ""])
        for row in sorted(by_language[language], key=lambda item: float(item["cosine_similarity"]))[:bottom_pairs]:
            lines.append(
                f"- `{row['task_id']}` turn {row['turn_index']}, cosine `{float(row['cosine_similarity']):.4f}`. "
                f"Source: {_truncate_report_text(row['source_text'])} Target: {_truncate_report_text(row['target_text'])}"
            )
        lines.append("")

    constraints = Counter()
    for row in pair_rows:
        if not row["numeric_values_match"]:
            constraints["numeric_multiset_differences"] += 1
        if not row["source_quoted_literals_preserved"]:
            constraints["missing_quoted_literal_rows"] += 1
        if not row["source_filenames_preserved"]:
            constraints["missing_filename_rows"] += 1
    lines.extend([
        "## Literal-preservation diagnostics",
        "",
        f"Numeric multiset differences: {constraints['numeric_multiset_differences']} of {len(pair_rows)} pairs.",
        f"Rows with an exact source-quoted literal not found in the target text: {constraints['missing_quoted_literal_rows']}.",
        f"Rows with a source filename not found verbatim in the target text: {constraints['missing_filename_rows']}.",
        "These are string-level review flags. They do not determine semantic correctness; number formatting and localization choices can require inspection. Full values are in the pair CSV.",
        "",
        "## Controlled comparisons",
        "",
        "| Control type | Class | Pairs | Mean baseline cosine | Mean comparison cosine | Mean score drop |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ])
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in control_rows:
        grouped[(str(row["control_type"]), str(row["control_class"]))].append(row)
    for (control_type, control_class), rows in sorted(grouped.items()):
        baseline = statistics.fmean(float(row["baseline_similarity"]) for row in rows)
        comparison = statistics.fmean(float(row["comparison_similarity"]) for row in rows)
        drop = statistics.fmean(float(row["score_drop"]) for row in rows)
        lines.append(f"| {control_type} | {control_class} | {len(rows)} | {baseline:.4f} | {comparison:.4f} | {drop:.4f} |")
    lines.extend([
        "",
        "Number and quoted-literal corruptions alter real BFCL target turns deterministically. Mismatched-task controls pair a source turn with another task's target turn at the same language and turn index. Negation controls are separately authored challenge sentences with their provenance in the JSON input. These controls test score sensitivity; they are not a benchmark of natural translation errors.",
        "",
        "## Interpretation limits",
        "",
        "LaBSE was trained to represent cross-lingual sentence meaning and retrieve translation pairs. A high cosine score can coexist with a changed number, filename, negation, or task constraint, and a lower score can reflect valid wording or domain-specific phrasing. The score is not calibrated as an accuracy percentage. Review the lowest pairs and the per-control score changes alongside the direct author review and literal checks. This diagnostic alone cannot establish that every translation is accurate.",
        "",
        "## Reproducibility",
        "",
        f"- Created UTC: `{provenance['created_at_utc']}`",
        f"- Python and package versions: `{json.dumps(provenance['software_versions'], sort_keys=True)}`",
        f"- Tokenizer max sequence length: `{provenance['max_seq_length']}`",
        f"- Negation challenge file SHA-256: `{provenance['negation_controls_sha256']}`",
        f"- Command argv: `{json.dumps(provenance['command_argv'], ensure_ascii=False)}`",
        "",
    ])
    return "\n".join(lines)


def _write_outputs_without_overwrite(output_dir: Path, outputs: dict[str, str]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / name for name in outputs]
    existing = [path for path in paths if path.exists()]
    if existing:
        raise DiagnosticError(f"Refusing to overwrite existing output(s): {existing}")
    created: list[Path] = []
    try:
        for name, content in outputs.items():
            path = output_dir / name
            with path.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
            created.append(path)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score direct BFCL source/translation turns with pinned LaBSE embeddings."
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=REPO_ROOT / "analysis/bfcl/newstudy20261010_expansion_collection_audit.json",
    )
    parser.add_argument("--cache", type=Path, default=None, help="Optional explicit path to the frozen JSONL cache.")
    parser.add_argument(
        "--negation-controls",
        type=Path,
        default=REPO_ROOT / "analysis/bfcl/newstudy20261010_labse_negation_controls.json",
    )
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "analysis/bfcl")
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--model-revision", required=True, help="Pinned 40-character model repository commit SHA.")
    parser.add_argument("--model-path", type=Path, default=None, help="Optional verified local model snapshot directory.")
    parser.add_argument(
        "--model-manifest",
        type=Path,
        default=REPO_ROOT / "analysis/bfcl/newstudy20261010_labse_model_manifest.json",
    )
    parser.add_argument("--device", default="auto", help="Sentence Transformers device, for example auto, cpu, or cuda.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--bottom-pairs", type=int, default=3)
    return parser.parse_args(argv)


def run_diagnostic(args: argparse.Namespace) -> list[Path]:
    if args.model_id != MODEL_ID:
        raise DiagnosticError(f"This diagnostic is pinned to model ID {MODEL_ID!r}.")
    if not REVISION_PATTERN.fullmatch(args.model_revision):
        raise DiagnosticError("--model-revision must be a pinned 40-character hexadecimal commit SHA.")
    if args.batch_size < 1 or args.bottom_pairs < 1:
        raise DiagnosticError("Batch size and bottom-pairs must be positive.")
    output_dir = args.output_dir.resolve()
    output_paths = [output_dir / name for name in OUTPUT_NAMES]
    existing = [path for path in output_paths if path.exists()]
    if existing:
        raise DiagnosticError(f"Refusing to overwrite existing output(s): {existing}")

    audit_path = args.audit.resolve()
    audit, plan, cache_path, plan_path, records = verify_audit_and_cache(audit_path, args.cache)
    task_ids = [str(task_id) for task_id in plan["task_ids"]]
    all_tasks = load_bfcl_multiturn_tasks(PILOT_TEST_CATEGORIES)
    tasks_by_id = {str(task.prompt_entry["id"]): task for task in all_tasks}
    missing_tasks = [task_id for task_id in task_ids if task_id not in tasks_by_id]
    if missing_tasks:
        raise DiagnosticError(f"Selected tasks are missing from the local BFCL snapshot: {missing_tasks}")
    tasks = [tasks_by_id[task_id] for task_id in task_ids]
    source_by_task = {
        str(task.prompt_entry["id"]): (get_original_turn_texts(task), task_content_sha256(task))
        for task in tasks
    }
    cache_by_key = validate_localization_rows(records, task_ids, source_by_task)
    pairs = _nonempty_pairs(task_ids, source_by_task, cache_by_key)
    if len(pairs) != 602:
        raise DiagnosticError(f"Expected 602 nonempty direct pairs, found {len(pairs)}.")
    per_language = Counter(pair["language_code"] for pair in pairs)
    if any(per_language[language] != 86 for language in EXPECTED_LANGUAGES if language != "EN"):
        raise DiagnosticError(f"Unexpected nonempty pair count by language: {dict(per_language)}")

    negation_path = args.negation_controls.resolve()
    if not negation_path.is_file():
        raise DiagnosticError(f"The authored negation controls are missing: {negation_path}")
    negation_data = json.loads(negation_path.read_text(encoding="utf-8"))
    controls = _build_controls(pairs, task_ids, source_by_task, cache_by_key, negation_data)
    all_texts: list[str] = []
    for pair in pairs:
        all_texts.extend((pair["source_text"], pair["target_text"]))
    for control in controls:
        all_texts.extend((control["source_text"], control["baseline_target"], control["comparison_target"]))

    model_path = args.model_path.resolve() if args.model_path else None
    model_manifest_hash = None
    if model_path is not None:
        model_manifest_hash = verify_model_manifest(
            model_path,
            args.model_manifest.resolve(),
            args.model_id,
            args.model_revision,
        )
    model = _load_model(args.model_id, args.model_revision, args.device, model_path)
    embeddings, layout = _score_texts(all_texts, model, args.batch_size)
    for pair in pairs:
        pair["cosine_similarity"] = cosine_similarity(
            embeddings[pair["source_text"]], embeddings[pair["target_text"]]
        )
        pair["source_token_count"] = layout[pair["source_text"]]["token_count"]
        pair["target_token_count"] = layout[pair["target_text"]]["token_count"]
        pair["source_chunk_count"] = layout[pair["source_text"]]["chunk_count"]
        pair["target_chunk_count"] = layout[pair["target_text"]]["chunk_count"]
        pair.update(inspect_literal_constraints(pair["source_text"], pair["target_text"]))
    for control in controls:
        control["baseline_similarity"] = cosine_similarity(
            embeddings[control["source_text"]], embeddings[control["baseline_target"]]
        )
        control["comparison_similarity"] = cosine_similarity(
            embeddings[control["source_text"]], embeddings[control["comparison_target"]]
        )
        control["score_drop"] = control["baseline_similarity"] - control["comparison_similarity"]
        control["source_token_count"] = layout[control["source_text"]]["token_count"]
        control["baseline_target_token_count"] = layout[control["baseline_target"]]["token_count"]
        control["comparison_target_token_count"] = layout[control["comparison_target"]]["token_count"]

    summary = summarize_pair_scores(pairs)
    audit_hash = sha256_file(audit_path)
    provenance = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": args.model_id,
        "model_revision": args.model_revision.lower(),
        "cache_path": _portable_path(cache_path, kind="cache"),
        "cache_sha256": sha256_file(cache_path),
        "collection_audit_path": _portable_path(audit_path, kind="audit"),
        "collection_audit_sha256": audit_hash,
        "plan_path": _portable_path(plan_path, kind="plan"),
        "plan_sha256": sha256_file(plan_path),
        "task_count": len(task_ids),
        "cache_rows": len(records),
        "languages": list(EXPECTED_LANGUAGES),
        "nonempty_pairs": len(pairs),
        "negation_controls_path": _portable_path(negation_path, kind="negation-controls"),
        "negation_controls_sha256": sha256_file(negation_path),
        "model_path": _portable_path(model_path, kind="model-path") if model_path else None,
        "model_manifest_path": _portable_path(args.model_manifest.resolve(), kind="model-manifest") if model_path else None,
        "model_manifest_sha256": model_manifest_hash,
        "software_versions": _software_versions(),
        "device_requested": args.device,
        "device_used": str(getattr(model, "device", "unknown")),
        "max_seq_length": int(model.max_seq_length),
        "chunk_policy": "No chunking: every nonempty text is tokenized without special tokens and must fit within max_seq_length minus tokenizer special-token allowance. Over-limit text fails explicitly; no truncation is allowed.",
        "command_argv": _sanitize_command_argv(sys.argv),
        "limitations": [
            "Cosine similarity is not calibrated translation accuracy.",
            "Low and high scores require human interpretation.",
            "Artificial corruption controls are sensitivity probes, not a natural-error benchmark.",
            "Numeric and literal checks flag string differences and do not decide semantic correctness.",
        ],
    }
    for pair in pairs:
        pair["model_id"] = args.model_id
        pair["model_revision"] = args.model_revision.lower()
        pair["cache_sha256"] = provenance["cache_sha256"]
    for control in controls:
        control["model_id"] = args.model_id
        control["model_revision"] = args.model_revision.lower()
        control["cache_sha256"] = provenance["cache_sha256"]
        control.setdefault("control_provenance", "Derived from frozen BFCL cache; artificial perturbation described in control_type.")
    report = build_report(pairs, controls, summary, provenance, args.bottom_pairs)
    summary_object = {
        "schema_version": 1,
        "interpretation": "Embedding similarity diagnostic only; no threshold or accuracy probability.",
        "provenance": provenance,
        "pair_summary_by_language": summary,
        "pair_count_by_language": dict(sorted(per_language.items())),
        "literal_diagnostic_counts": {
            "numeric_multiset_differences": sum(not pair["numeric_values_match"] for pair in pairs),
            "missing_quoted_literal_rows": sum(not pair["source_quoted_literals_preserved"] for pair in pairs),
            "missing_filename_rows": sum(not pair["source_filenames_preserved"] for pair in pairs),
        },
        "control_counts": dict(sorted(Counter(row["control_type"] for row in controls).items())),
        "control_class_counts": dict(sorted(Counter(row["control_class"] for row in controls).items())),
    }
    pair_fields = (
        "pair_id", "task_id", "language_code", "turn_index", "ai_review_status", "cosine_similarity",
        "source_token_count", "target_token_count", "source_chunk_count", "target_chunk_count",
        "source_numbers", "target_numbers", "numeric_values_match", "source_quoted_literals",
        "missing_source_quoted_literals", "source_quoted_literals_preserved", "source_filenames",
        "missing_source_filenames", "source_filenames_preserved", "needs_manual_review",
        "source_text", "target_text", "model_id", "model_revision", "cache_sha256",
    )
    control_fields = (
        "control_id", "control_type", "control_class", "language_code", "task_id", "other_task_id",
        "turn_index", "corrupted_literal", "baseline_similarity", "comparison_similarity", "score_drop",
        "source_token_count", "baseline_target_token_count", "comparison_target_token_count",
        "source_text", "baseline_target", "comparison_target", "control_provenance",
        "model_id", "model_revision", "cache_sha256",
    )
    outputs = {
        OUTPUT_NAMES[0]: _csv_text(pairs, pair_fields),
        OUTPUT_NAMES[1]: _csv_text(controls, control_fields),
        OUTPUT_NAMES[2]: json.dumps(summary_object, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        OUTPUT_NAMES[3]: report,
    }
    return _write_outputs_without_overwrite(output_dir, outputs)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        paths = run_diagnostic(args)
    except (DiagnosticError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
