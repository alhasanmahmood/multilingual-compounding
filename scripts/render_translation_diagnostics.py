"""Render the paper appendix from saved LaBSE pair and control diagnostics."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "analysis/bfcl"


def _linear_percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot summarize an empty LaBSE score list.")
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _validate_saved_scores(
    summary: dict,
    pairs: list[dict[str, str]],
    controls: list[dict[str, str]],
) -> None:
    provenance = summary.get("provenance", {})
    expected_model_id = provenance.get("model_id")
    expected_revision = provenance.get("model_revision")
    expected_cache_hash = provenance.get("cache_sha256")
    if not expected_model_id or not expected_revision or not expected_cache_hash:
        raise ValueError("LaBSE summary lacks model identity or frozen-cache provenance.")
    if provenance.get("task_count") != 20:
        raise ValueError("LaBSE scores do not identify the current twenty-scenario cohort.")
    pair_ids = [row.get("pair_id", "") for row in pairs]
    if not pairs or any(not pair_id for pair_id in pair_ids) or len(pair_ids) != len(set(pair_ids)):
        raise ValueError("Pair CSV has missing or duplicate pair IDs.")
    if len(pairs) != sum(summary.get("pair_count_by_language", {}).values()) or len(pairs) != provenance.get("nonempty_pairs"):
        raise ValueError("Pair CSV row count differs from the LaBSE summary.")

    by_language: dict[str, list[float]] = defaultdict(list)
    numeric_flags = 0
    quoted_flags = 0
    filename_flags = 0
    for row in pairs:
        if (
            row.get("model_id") != expected_model_id
            or row.get("model_revision") != expected_revision
            or row.get("cache_sha256") != expected_cache_hash
        ):
            raise ValueError("Pair CSV mixes model identities, revisions, or translation-cache hashes.")
        score = float(row["cosine_similarity"])
        if not math.isfinite(score):
            raise ValueError("Pair CSV contains a non-finite cosine score.")
        by_language[row["language_code"]].append(score)
        numeric_flags += row.get("numeric_values_match") != "True"
        quoted_flags += row.get("source_quoted_literals_preserved") != "True"
        filename_flags += row.get("source_filenames_preserved") != "True"

    if set(by_language) != set(summary.get("pair_count_by_language", {})):
        raise ValueError("Pair CSV languages differ from the LaBSE summary.")
    if {language: len(scores) for language, scores in by_language.items()} != summary["pair_count_by_language"]:
        raise ValueError("Per-language pair counts differ from the LaBSE summary.")
    for language, scores in by_language.items():
        actual = summary["pair_summary_by_language"].get(language, {})
        expected = {
            "nonempty_pairs": len(scores),
            "median": statistics.median(scores),
            "p10": _linear_percentile(scores, 0.10),
            "minimum": min(scores),
            "mean": statistics.fmean(scores),
        }
        if any(
            key not in actual or not math.isclose(float(actual[key]), value, rel_tol=0.0, abs_tol=1e-9)
            for key, value in expected.items()
        ):
            raise ValueError(f"Per-language LaBSE statistics for {language} do not reproduce from the pair CSV.")

    literal_counts = summary.get("literal_diagnostic_counts", {})
    if literal_counts != {
        "numeric_multiset_differences": numeric_flags,
        "missing_quoted_literal_rows": quoted_flags,
        "missing_filename_rows": filename_flags,
    }:
        raise ValueError("Literal diagnostic counts do not reproduce from the pair CSV.")

    control_ids = [row.get("control_id", "") for row in controls]
    if not controls or any(not control_id for control_id in control_ids) or len(control_ids) != len(set(control_ids)):
        raise ValueError("Control CSV has missing or duplicate control IDs.")
    types = Counter(row.get("control_type", "") for row in controls)
    classes = Counter(row.get("control_class", "") for row in controls)
    if dict(sorted(types.items())) != summary.get("control_counts"):
        raise ValueError("Control counts differ from the LaBSE summary.")
    if dict(sorted(classes.items())) != summary.get("control_class_counts"):
        raise ValueError("Control classes differ from the LaBSE summary.")
    for row in controls:
        if (
            row.get("model_id") != expected_model_id
            or row.get("model_revision") != expected_revision
            or row.get("cache_sha256") != expected_cache_hash
        ):
            raise ValueError("Control CSV mixes model identities, revisions, or translation-cache hashes.")
        baseline = float(row["baseline_similarity"])
        comparison = float(row["comparison_similarity"])
        drop = float(row["score_drop"])
        if not all(math.isfinite(value) for value in (baseline, comparison, drop)):
            raise ValueError("Control CSV contains a non-finite score.")
        if not math.isclose(baseline - comparison, drop, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Control score drop does not match its baseline and comparison: {row['control_id']}.")


def main() -> None:
    summary = json.loads((BASE / "newstudy20261010_labse_summary.json").read_text(encoding="utf-8"))
    pair_path = BASE / "newstudy20261010_labse_pairs.csv"
    review = json.loads((BASE / "newstudy20261011_labse_outlier_review.json").read_text(encoding="utf-8"))
    if hashlib.sha256(pair_path.read_bytes()).hexdigest() != review["source_csv_sha256"]:
        raise ValueError("Targeted review does not match the scored pair CSV.")
    if review.get("model_id") != summary["provenance"].get("model_id"):
        raise ValueError("Targeted review model differs from the LaBSE score summary.")
    if review.get("model_revision") != summary["provenance"].get("model_revision"):
        raise ValueError("Targeted review revision differs from the LaBSE score summary.")
    if review.get("frozen_translation_cache_sha256") != summary["provenance"].get("cache_sha256"):
        raise ValueError("Targeted review translation cache differs from the LaBSE score summary.")
    if review.get("result", {}).get("confirmed_task_critical_mistranslations") != 0:
        raise ValueError("The current paper text assumes no task-critical error in the inspected sample.")
    with pair_path.open(encoding="utf-8", newline="") as handle:
        pairs = list(csv.DictReader(handle))
    with (BASE / "newstudy20261010_labse_controls.csv").open(encoding="utf-8", newline="") as handle:
        controls = list(csv.DictReader(handle))
    _validate_saved_scores(summary, pairs, controls)
    wanted = {row["pair_id"] for row in pairs if row["needs_manual_review"] == "True"}
    for language in summary["pair_count_by_language"]:
        ranked = sorted((row for row in pairs if row["language_code"] == language), key=lambda row: float(row["cosine_similarity"]))
        wanted.update(row["pair_id"] for row in ranked[:3])
    reviewed = {row["pair_id"] for row in review["lowest_cosine_pairs"] + review["numeric_flags"]}
    if reviewed != wanted or review["coverage"]["full_text_pairs_inspected"] != len(wanted):
        raise ValueError("Targeted review must cover exactly the lowest three pairs per language and all string flags.")
    if review["coverage"].get("numeric_manual_review_flags") != summary["literal_diagnostic_counts"]["numeric_multiset_differences"]:
        raise ValueError("Targeted review numeric-flag coverage differs from the LaBSE pair diagnostics.")
    if review["coverage"].get("reviewed_union_count") != len(wanted):
        raise ValueError("Targeted review union count does not match its inspected pair IDs.")
    pair_counts = summary["pair_count_by_language"]
    paper_languages = {"AR", "TR", "ZH", "HI", "JA", "ES", "SW"}
    if set(pair_counts) != paper_languages:
        raise ValueError("LaBSE languages do not match the appendix table rows.")
    if len(set(pair_counts.values())) != 1:
        raise ValueError("The current LaBSE table caption expects equal pair counts per language.")
    pairs_per_language = next(iter(pair_counts.values()))
    groups = defaultdict(list)
    for row in controls:
        groups[row["control_type"]].append(row)
    higher_literal = sum(float(row["score_drop"]) < 0 for row in groups["quoted_literal_or_filename_changed"])
    higher_negation = sum(float(row["score_drop"]) < 0 for row in groups["negation_reversal"])
    lines = [
        r"\section{Translation Consistency Diagnostics}",
        r"\label{app:translation_quality}",
        r"We apply LaBSE \citep{feng2022labse} to the frozen translations used in",
        r"the twenty-scenario cohort. We compare each nonempty English source turn",
        f"directly with its target-language turn, yielding ${len(pairs)}$ pairs, ${pairs_per_language}$ per",
        r"language. Backtranslations are not scored. We pin the encoder revision",
        r"and retain cache, model-file, and input hashes with the outputs.",
        f"Every input fits the encoder's ${summary['provenance']['max_seq_length']}$-token limit; the script rejects",
        r"over-limit text rather than truncating it. Table~\ref{tab:labse_pairs}",
        r"reports cosine distributions without a pass threshold.",
        "",
        r"\begin{table}[ht]",
        r"\centering\footnotesize",
        r"\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrr@{}}\toprule",
        r"Language & Median & 10th percentile & Minimum \\\midrule",
    ]
    for language in ("AR", "TR", "ZH", "HI", "JA", "ES", "SW"):
        values = summary["pair_summary_by_language"][language]
        lines.append(f"{language} & {values['median']:.3f} & {values['p10']:.3f} & {values['minimum']:.3f} " + r"\\")
    lines += [
        r"\bottomrule\end{tabular*}",
        r"\caption{LaBSE cosine for English--translation pairs,",
        f"${pairs_per_language}$ per language. This score measures text similarity, not translation accuracy.}}",
        r"\label{tab:labse_pairs}",
        r"\end{table}",
        "",
        r"\paragraph{Control probes.} We change one number",
        r"or an exact quoted literal/filename in eligible target turns, and pair",
        r"source turns with another task's target turn in the same language",
        r"and turn position. We also include",
        f"${len(groups['negation_reversal'])}$ AI-written and AI-checked sentence pairs, one per",
        r"target language. Each pair reverses a ``do not delete the original file''",
        r"instruction. These are artificial probes, not a labeled benchmark of natural",
        r"translation errors.",
        r"Table~\ref{tab:labse_controls} gives their average score changes.",
        "",
        r"\begin{table}[ht]",
        r"\centering\footnotesize\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrr@{}}\toprule",
        r"Probe & $n$ & Cosine & Mean drop \\\midrule",
    ]
    labels = {
        "number_changed": "Number change",
        "quoted_literal_or_filename_changed": "Literal/filename change",
        "mismatched_task_turn": "Different-task turn",
        "negation_reversal": "Negation reversal",
    }
    for key, label in labels.items():
        rows = groups[key]
        comparison = statistics.fmean(float(row["comparison_similarity"]) for row in rows)
        drop = statistics.fmean(float(row["score_drop"]) for row in rows)
        lines.append(f"{label} & {len(rows)} & {comparison:.3f} & {drop:.3f} " + r"\\")
    lines += [
        r"\bottomrule\end{tabular*}",
        r"\caption{Mean cosine for each altered or mismatched pair; mean drop from its",
        r"baseline. Negative drops mean higher cosine for the comparison pair. Groups",
        r"have different baselines.}",
        r"\label{tab:labse_controls}\end{table}",
        "",
        r"\paragraph{Interpretation and review.} A high score can coexist with an",
        f"incorrect number, literal, or constraint. In these probes, ${higher_literal}/{len(groups['quoted_literal_or_filename_changed'])}$",
        f"literal/filename corruptions and ${higher_negation}/{len(groups['negation_reversal'])}$ negation reversals even score",
        r"higher than their unperturbed pairs. Shared English identifiers",
        r"can also contribute to similarity. Cosine therefore supplements author",
        r"review and exact-literal/alignment checks; it cannot certify semantic",
        r"accuracy or native fluency.",
        r"Between-language score differences do not establish a quality ranking.",
        r"We inspect the three lowest pairs per language and all string-level flags using AI assistance,",
        r"with dispositions released alongside the scores. This subsequent AI",
        f"inspection covers ${len(wanted)}$ unique pairs, including all ${summary['literal_diagnostic_counts']['numeric_multiset_differences']}$ numeric flags.",
        r"It finds no clear task-critical mistranslation in this selected set;",
        r"wording nuances and extraction artifacts are recorded separately. This",
        r"inspection is distinct from the author's mixed target-text and",
        r"backtranslation review and is not independent bilingual validation.",
        "",
        r"\paragraph{Reproduction.} The script",
        r"\path{scripts/run_translation_similarity.py} writes per-turn scores,",
        r"probe scores, and a provenance summary under",
        r"\path{analysis/bfcl/newstudy20261010_labse_*}. The pinned model revision",
        r"is {\footnotesize\texttt{836121a0533e5664b21c7aacc5d22951f2b8b25b}}.",
        r"Optional dependency pins and the executed environment are released.",
        r"Scoring runs locally and makes no paid model-API calls.",
        "",
    ]
    destination = ROOT / "paper/generated/newstudy20261011_translation_diagnostics.tex"
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
