"""Read-only checks on the refined manuscript, its inputs, and saved displays."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
ANALYSIS = ROOT / "analysis/bfcl"


def load(name: str):
    return json.loads((ANALYSIS / name).read_text(encoding="utf-8"))


def normalized(value, key=""):
    """Ignore undefined-CF NaNs and ordering of identifier-only metadata lists."""
    if isinstance(value, float) and math.isnan(value):
        return "undefined-CF"
    if isinstance(value, dict):
        return {k: normalized(v, k) for k, v in value.items()}
    if isinstance(value, list):
        rows = [normalized(v) for v in value]
        return sorted(rows) if key.endswith("task_ids") else rows
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduction-prefix", help="Also compare a separately rerun offline analysis bundle.")
    args = parser.parse_args()
    checks = []

    def check(condition, description):
        if not condition:
            raise ValueError(description)
        checks.append(description)

    main_text = (PAPER / "main.tex").read_text(encoding="utf-8")
    sources = {"main.tex": main_text}
    for item in re.findall(r"\\input\{([^}]+)\}", main_text):
        path = PAPER / (item if item.endswith(".tex") else item + ".tex")
        check(path.is_file(), f"TeX input exists: {item}")
        sources[item] = path.read_text(encoding="utf-8")
    text = "\n".join(sources.values())
    labels = set(re.findall(r"\\label\{([^}]+)\}", text))
    references = set(re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", text))
    check(references <= labels, "All internal references resolve")
    check("\u2014" not in text and "---" not in text and r"\textemdash" not in text, "No em dashes in manuscript inputs")
    cited = {key.strip() for group in re.findall(r"\\cite(?:p|t)?\{([^}]+)\}", text) for key in group.split(",")}
    bibliography = (PAPER / "references.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bibliography))
    check(cited <= keys, "All cited bibliography keys exist")
    for item in re.findall(r"\\path\{([^}]+)\}", text):
        path = item.replace(r"\_", "_")
        check(bool(list(ROOT.glob(path))) if "*" in path else (ROOT / path).exists(), f"Named artifact exists: {path}")

    # Official acl-org/acl-style-files commit d5adc823ff0f80f98c80405ca0ab66c68e684409.
    # Normalize platform line endings only; no style/content changes are allowed.
    style_hashes = {
        "acl.sty": "19dfeddc2c0e448f3926a0bef048a9db3f3611b46265b760caabd7ada4f361de",
        "acl_natbib.bst": "6fbb306202290f4b68e74ac1460a8b27398500cb6dfeb4492e74c457eae7cd1e",
    }
    for name, expected in style_hashes.items():
        actual = hashlib.sha256((PAPER / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        check(actual == expected, f"Official ACL template text unchanged: {name}")

    cf = load("newstudy20261010_expansion_cf_summary.json")
    table = (PAPER / "generated/newstudy20261010_main_table.tex").read_text(encoding="utf-8")
    figure = (PAPER / "generated/newstudy20261010_delta_figure.tex").read_text(encoding="utf-8")
    languages = ("EN", "AR", "ES", "HI", "JA", "SW", "TR", "ZH")
    for model, offset in (("gemini", .11), ("claude_sonnet46", -.11)):
        for language in languages:
            row = cf["point_estimates"]["9"][f"{language}::{model}"]
            factor = "ref." if language == "EN" else f"{row['CF']:.3f}"
            delta = "ref." if language == "EN" else f"{row['Delta']:+.3f}"
            check(f"& {language} & {row['p']:.3f} & {row['T']:.3f} & {factor} & {delta}" in table, f"Main table data: {language}/{model}")
            if language == "EN":
                continue
            row = cf["bootstrap"]["9"]["common"][f"{language}::{model}"]
            y = 7 - languages.index(language) + offset
            lower, upper = row["Delta_CI"]
            check(f"({lower:.6f},{y:.2f})--({upper:.6f},{y:.2f})" in figure, f"Scenario interval: {language}/{model}")
            check(f"({row['Delta']:.6f},{y:.2f})" in figure, f"Delta point: {language}/{model}")

    summary = load("newstudy20261010_labse_summary.json")
    with (ANALYSIS / "newstudy20261010_labse_pairs.csv").open(encoding="utf-8", newline="") as handle:
        pairs = list(csv.DictReader(handle))
    check(len(pairs) == 602, "602 direct LaBSE pairs")
    labse_tex = (PAPER / "generated/newstudy20261011_translation_diagnostics.tex").read_text(encoding="utf-8")
    for language, values in summary["pair_summary_by_language"].items():
        scores = sorted(float(row["cosine_similarity"]) for row in pairs if row["language_code"] == language)
        check(len(scores) == 86 and statistics.median(scores) == values["median"] and min(scores) == values["minimum"], f"LaBSE CSV summary: {language}")
        check(f"{language} & {values['median']:.3f} & {values['p10']:.3f} & {values['minimum']:.3f}" in labse_tex, f"LaBSE displayed distribution: {language}")
    cache = ROOT / "data/bfcl/localized_queries/newstudy20261010_bfcl_multiturn_localizations.jsonl"
    check(hashlib.sha256(cache.read_bytes()).hexdigest() == summary["provenance"]["cache_sha256"], "Collected translation cache unchanged")

    if args.reproduction_prefix:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.reproduction_prefix):
            raise ValueError("Reproduction prefix must be a simple artifact name.")
        for suffix in ("cf_summary", "decomposition_summary", "robustness_summary", "task_sensitivity_summary"):
            old = load(f"newstudy20261010_expansion_{suffix}.json")
            rerun = load(f"{args.reproduction_prefix}_{suffix}.json")
            check(normalized(old) == normalized(rerun), f"Offline analysis reproduction: {suffix}")

    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", main_text, re.S).group(1)
    word_count = len(abstract.split())
    check(word_count <= 200, "Abstract within official 200-word limit")
    print(json.dumps({"status": "passed", "checks": len(checks), "cited_keys": sorted(cited), "abstract_words": word_count, "details": checks}, indent=2))


if __name__ == "__main__":
    main()
