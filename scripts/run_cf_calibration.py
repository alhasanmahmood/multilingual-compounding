"""Reproduce an offline synthetic calibration of the compounding factor.

This script uses only the repository's metric implementation and synthetic
Bernoulli draws. It does not call a model or an external service.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multilingual_compounding.metrics import TaskRecord, bootstrap_cf, compute_cf  # noqa: E402


K = 10
P_EN_KNOWN = 0.90
P_TR_KNOWN = 0.86
LARGE_N = 10_000
SMALL_N = 8  # four benchmark tasks, each run with two seeds
TASK_COUNTS = (4, 10, 20, 25, 50)  # unique underlying task clusters
SEEDS_PER_TASK = 2
MC_REPLICATES = 200
N_BOOT = 5_000
BASE_SEED = 20261010
DEFAULT_MIN_LOG_RIND = 0.05
TASK_DIFFICULTY_BETA = (9.0, 1.0)
LANGUAGES = ("AR", "EN", "ES", "HI", "JA", "SW", "TR", "ZH")
MODELS = ("claude_sonnet46", "gemini")
NON_ENGLISH = tuple(language for language in LANGUAGES if language != "EN")
MAIN_RESULTS_PATH = REPO_ROOT / "analysis" / "bfcl" / "main_results_cf_summary.json"
SUMMARY_PATH = REPO_ROOT / "analysis" / "bfcl" / "cf_calibration_summary.json"
REPORT_PATH = REPO_ROOT / "analysis" / "bfcl" / "cf_calibration_report.md"


def generate_factor_records(
    n_tasks: int,
    p_by_language: dict[str, float],
    alpha_by_language: dict[str, float],
    *,
    k: int = K,
    seed: int,
    backbone: str = "synthetic",
) -> list[TaskRecord]:
    """Generate isolated step outcomes and full-task outcomes.

    A full task succeeds when all K isolated steps are valid and a separate
    multiplicative survival draw succeeds. This deliberately controlled
    process makes the expected task success alpha * p**K. Alpha lowers success
    and is not a recovery factor.
    """
    if n_tasks <= 0 or k <= 0:
        raise ValueError("n_tasks and k must be positive")
    if set(p_by_language) != set(alpha_by_language):
        raise ValueError("p and alpha must define the same languages")
    for language, probability in p_by_language.items():
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"p[{language}] must be between 0 and 1")
        if not 0.0 <= alpha_by_language[language] <= 1.0:
            raise ValueError(f"alpha[{language}] must be between 0 and 1")

    rng = np.random.default_rng(seed)
    records: list[TaskRecord] = []
    languages = tuple(p_by_language)
    for task_index in range(n_tasks):
        task_id = f"task_seed_{task_index:04d}"
        for language in languages:
            steps = (rng.random(k) < p_by_language[language]).astype(int).tolist()
            survives = bool(rng.random() < alpha_by_language[language])
            success = int(all(steps) and survives)
            records.append(TaskRecord(task_id, language, backbone, success, steps))
    return records


def generate_observed_rate_records(
    n_tasks: int,
    p_by_language: dict[str, float],
    task_success_by_language: dict[str, float],
    *,
    k: int = K,
    seed: int,
    backbone: str = "synthetic_observed_rate",
) -> list[TaskRecord]:
    """Sample marginal replay and task-success rates from the paper summary.

    Step replays and full-task outcomes are drawn independently. That is a
    marginal-rate power approximation, not a claim about their unobserved
    within-task dependence; it allows a full trajectory to succeed even when
    one or more isolated replay draws fail.
    """
    if n_tasks <= 0 or k <= 0:
        raise ValueError("n_tasks and k must be positive")
    if set(p_by_language) != set(task_success_by_language):
        raise ValueError("p and task success must define the same languages")
    rng = np.random.default_rng(seed)
    records: list[TaskRecord] = []
    for task_index in range(n_tasks):
        task_id = f"task_seed_{task_index:04d}"
        for language in p_by_language:
            p = p_by_language[language]
            task_success = task_success_by_language[language]
            if not 0.0 <= p <= 1.0 or not 0.0 <= task_success <= 1.0:
                raise ValueError("probabilities must be between 0 and 1")
            steps = rng.binomial(1, p, size=k).astype(int).tolist()
            success = int(rng.random() < task_success)
            records.append(
                TaskRecord(task_id, language, backbone, success, steps)
            )
    return records


def expected_factor_cf(
    p_en: float,
    p_tr: float,
    alpha_en: float,
    alpha_tr: float,
    *,
    k: int = K,
) -> float:
    """Return the large-sample CF implied by T(language)=alpha*p**K."""
    log_r_ind = k * math.log(p_tr / p_en)
    if abs(log_r_ind) <= 1e-9:
        return math.nan
    log_r_obs = log_r_ind + math.log(alpha_tr / alpha_en)
    return log_r_obs / log_r_ind


def beta_moment(order: int, alpha: float, beta: float) -> float:
    """Return E[X**order] for X ~ Beta(alpha, beta), using a stable product."""
    if order < 0 or alpha <= 0 or beta <= 0:
        raise ValueError("order must be nonnegative and beta parameters positive")
    return math.prod((alpha + i) / (alpha + beta + i) for i in range(order))


def expected_metric_pair(
    p_by_language: dict[str, list[float]],
    task_success_by_language: dict[str, float],
    *,
    k: int = K,
) -> dict[str, dict[str, float | None]]:
    """Analytic common-mean and position-specific CF/Delta for two languages."""
    if set(p_by_language) != set(task_success_by_language):
        raise ValueError("step rates and task-success rates must name the same languages")
    if len(p_by_language) != 2 or "EN" not in p_by_language:
        raise ValueError("expected exactly EN and one comparison language")
    comparison = next(language for language in p_by_language if language != "EN")
    expected: dict[str, dict[str, float | None]] = {}
    for null_name in ("common", "position"):
        t_ind: dict[str, float] = {}
        for language, positions in p_by_language.items():
            if len(positions) != k:
                raise ValueError(f"p[{language}] must have exactly K={k} positions")
            if any(not 0.0 < probability <= 1.0 for probability in positions):
                raise ValueError("step probabilities must be in (0, 1]")
            if null_name == "common":
                t_ind[language] = float(np.mean(positions) ** k)
            else:
                t_ind[language] = float(np.prod(positions))
        r_ind = t_ind[comparison] / t_ind["EN"]
        r_obs = task_success_by_language[comparison] / task_success_by_language["EN"]
        log_r_ind = math.log(r_ind)
        log_r_obs = math.log(r_obs)
        expected[null_name] = {
            "T_ind_EN": t_ind["EN"],
            "T_ind_comparison": t_ind[comparison],
            "r_ind": r_ind,
            "r_obs": r_obs,
            "CF": log_r_obs / log_r_ind if abs(log_r_ind) > 1e-9 else None,
            "Delta": log_r_obs - log_r_ind,
        }
    return expected


def repair_process_expectations(
    p_en: float,
    p_tr: float,
    repair_en: float,
    repair_tr: float,
    *,
    k: int = K,
) -> dict:
    """Expected rates when a failed full trajectory is rescued with probability rho.

    A trajectory succeeds if every isolated step is valid, or if at least one
    step is invalid and the language-specific rescue draw succeeds. Therefore
    T = p**K + rho * (1 - p**K). This additive rescue process is not the
    multiplicative survival process in ``expected_factor_cf``.
    """
    base = {"EN": p_en**k, "TR": p_tr**k}
    repair = {"EN": repair_en, "TR": repair_tr}
    task_success = {
        language: base[language] + repair[language] * (1.0 - base[language])
        for language in base
    }
    metrics = expected_metric_pair(
        {"EN": [p_en] * k, "TR": [p_tr] * k}, task_success, k=k
    )
    return {
        "p": {"EN": p_en, "TR": p_tr},
        "repair_probability_after_step_failure": repair,
        "T": task_success,
        "T_without_repair": base,
        "metrics": metrics,
    }


def generate_repair_records(
    n_tasks: int,
    *,
    p_by_language: dict[str, float],
    repair_by_language: dict[str, float],
    n_seeds: int = 1,
    k: int = K,
    seed: int,
) -> list[TaskRecord]:
    """Sample trajectories with rescue after one or more invalid isolated steps."""
    if n_tasks <= 0 or n_seeds <= 0 or k <= 0:
        raise ValueError("n_tasks, n_seeds, and k must be positive")
    if set(p_by_language) != set(repair_by_language):
        raise ValueError("p and repair must define the same languages")
    if any(not 0.0 <= p <= 1.0 for p in p_by_language.values()):
        raise ValueError("step probabilities must be between 0 and 1")
    if any(not 0.0 <= rho <= 1.0 for rho in repair_by_language.values()):
        raise ValueError("repair probabilities must be between 0 and 1")

    rng = np.random.default_rng(seed)
    records: list[TaskRecord] = []
    for task_index in range(n_tasks):
        task_id = f"task_{task_index:04d}"
        for language, probability in p_by_language.items():
            for seed_index in range(n_seeds):
                steps = (rng.random(k) < probability).astype(int).tolist()
                all_valid = all(steps)
                success = int(
                    all_valid
                    or rng.random() < repair_by_language[language]
                )
                records.append(
                    TaskRecord(
                        f"{task_id}::seed_{seed_index}",
                        language,
                        "repair",
                        success,
                        steps,
                        task_id,
                    )
                )
    return records


def generate_position_records(
    n_tasks: int,
    p_positions: dict[str, list[float]],
    *,
    seed: int,
    backbone: str = "position",
) -> list[TaskRecord]:
    """Generate independent outcomes with language-specific position difficulty."""
    if n_tasks <= 0:
        raise ValueError("n_tasks must be positive")
    lengths = {len(values) for values in p_positions.values()}
    if lengths != {K}:
        raise ValueError(f"every language must define exactly K={K} positions")
    rng = np.random.default_rng(seed)
    records: list[TaskRecord] = []
    for task_index in range(n_tasks):
        task_id = f"position_task_{task_index:05d}"
        for language, probabilities in p_positions.items():
            steps = (rng.random(K) < np.asarray(probabilities)).astype(int).tolist()
            records.append(
                TaskRecord(task_id, language, backbone, int(all(steps)), steps)
            )
    return records


def generate_shared_difficulty_records(
    n_tasks: int,
    *,
    scale_by_language: dict[str, float],
    n_seeds: int,
    alpha: float,
    beta: float,
    seed: int,
    k: int = K,
) -> list[TaskRecord]:
    """Share latent task difficulty across languages and both seed runs.

    Each task draws q ~ Beta(alpha, beta). Within a seed, each isolated step
    succeeds independently conditional on q, with probability scale_language*q.
    Both seed runs share q. Full success is all K steps valid.
    """
    if n_tasks <= 0 or n_seeds <= 0 or k <= 0:
        raise ValueError("n_tasks, n_seeds, and k must be positive")
    if any(not 0.0 < scale <= 1.0 for scale in scale_by_language.values()):
        raise ValueError("language scales must be in (0, 1]")
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("beta parameters must be positive")
    rng = np.random.default_rng(seed)
    difficulties = rng.beta(alpha, beta, size=n_tasks)
    records: list[TaskRecord] = []
    for task_index, difficulty in enumerate(difficulties):
        task_id = f"shared_difficulty_task_{task_index:05d}"
        for language, scale in scale_by_language.items():
            for seed_index in range(n_seeds):
                steps = (rng.random(k) < difficulty * scale).astype(int).tolist()
                records.append(
                    TaskRecord(
                        f"{task_id}::seed_{seed_index}",
                        language,
                        "shared_difficulty",
                        int(all(steps)),
                        steps,
                        task_id,
                    )
                )
    return records


def best_case_holm_p(m: int, n_boot: int) -> float:
    """Smallest first Holm-adjusted p under the metric's plus-one rule."""
    if m <= 0 or n_boot < 0:
        raise ValueError("m must be positive and n_boot nonnegative")
    return min(1.0, m / (n_boot + 1.0))


def minimum_resamples_for_strict_holm(
    m: int, alpha: float = 0.05
) -> int:
    """Smallest n_boot for which the best-case Holm p is strictly below alpha."""
    if m <= 0 or not 0.0 < alpha < 1.0:
        raise ValueError("m must be positive and alpha must be between 0 and 1")
    n_boot = 0
    while best_case_holm_p(m, n_boot) >= alpha:
        n_boot += 1
    return n_boot


def _number(value: Any) -> float | int | None:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (int,)):
        return int(value)
    return None


def _point_estimates(
    records: list[TaskRecord], k: int = K, null: str = "common"
) -> dict[str, dict]:
    point = compute_cf(records, K=k, null=null)
    return {
        language: {
            "n_tasks": int(values["n"]),
            "p": _number(values["p"]),
            "T": _number(values["T"]),
            "T_ind": _number(values["T_ind"]),
            "r_obs": _number(values["r_obs"]),
            "r_ind": _number(values["r_ind"]),
            "CF": _number(values["CF"]),
            "Delta": _number(values["Delta"]),
        }
        for (language, _backbone), values in point.items()
    }


def _point_estimates_both_nulls(records: list[TaskRecord]) -> dict[str, dict]:
    return {
        "common_mean": _point_estimates(records, null="common"),
        "position_specific": _point_estimates(records, null="position"),
    }


def _large_scenario(
    *,
    p_en: float,
    p_tr: float,
    alpha_en: float,
    alpha_tr: float,
    seed: int,
    bootstrap_seed: int | None = None,
) -> dict:
    records = generate_factor_records(
        LARGE_N,
        {"EN": p_en, "TR": p_tr},
        {"EN": alpha_en, "TR": alpha_tr},
        seed=seed,
    )
    result: dict[str, Any] = {
        "generator_seed": seed,
        "n_tasks_per_language": LARGE_N,
        "k": K,
        "p": {"EN": p_en, "TR": p_tr},
        "alpha": {"EN": alpha_en, "TR": alpha_tr},
        "analytic_expected_CF": _number(
            expected_factor_cf(p_en, p_tr, alpha_en, alpha_tr)
        ),
        "point_estimates": _point_estimates(records),
    }
    if bootstrap_seed is not None:
        boot = bootstrap_cf(
            records,
            K=K,
            null="common",
            n_boot=N_BOOT,
            seed=bootstrap_seed,
            min_log_rind=DEFAULT_MIN_LOG_RIND,
        )
        tr = boot[("TR", "synthetic")]
        result["bootstrap"] = {
            "n_boot": N_BOOT,
            "seed": bootstrap_seed,
            "TR_CF_CI_95": [_number(x) for x in tr["CF_CI"]],
            "TR_Delta_CI_95": [_number(x) for x in tr["Delta_CI"]],
            "TR_p_holm_single_cell": _number(tr["p_holm"]),
            "TR_CF_reportable": bool(tr["CF_reportable"]),
            "TR_compounding_rejected": bool(tr["compounding"]),
        }
    return result


def _summarize_mc(cf_values: list[float], reportable: list[bool], rejected: list[bool]) -> dict:
    finite = np.asarray([x for x in cf_values if math.isfinite(x)], dtype=float)
    if finite.size:
        percentiles = np.percentile(finite, [5, 50, 95]).tolist()
    else:
        percentiles = [None, None, None]
    return {
        "replicates": len(cf_values),
        "finite_CF_replicates": int(finite.size),
        "CF_percentiles_5_50_95": [_number(x) for x in percentiles],
        "CF_reportable_fraction": _number(np.mean(reportable)),
        "single_cell_rejection_count": int(sum(rejected)),
        "single_cell_rejection_rate": _number(np.mean(rejected)),
    }


def _small_sample_monte_carlo(
    *,
    p_by_language: dict[str, float],
    alpha_by_language: dict[str, float] | None = None,
    task_success_by_language: dict[str, float] | None = None,
    seed: int,
) -> dict:
    cf_values: list[float] = []
    reportable: list[bool] = []
    rejected: list[bool] = []
    for replicate in range(MC_REPLICATES):
        sample_seed = seed + 10_000 * replicate
        if alpha_by_language is not None:
            records = generate_factor_records(
                SMALL_N,
                p_by_language,
                alpha_by_language,
                seed=sample_seed,
                backbone="small_sample",
            )
        else:
            assert task_success_by_language is not None
            records = generate_observed_rate_records(
                SMALL_N,
                p_by_language,
                task_success_by_language,
                seed=sample_seed,
            )
        boot = bootstrap_cf(
            records,
            K=K,
            null="common",
            n_boot=N_BOOT,
            seed=sample_seed + 1,
            min_log_rind=DEFAULT_MIN_LOG_RIND,
        )
        tr = next(values for (lang, _backbone), values in boot.items() if lang == "TR")
        cf_values.append(float(tr["CF"]) if math.isfinite(float(tr["CF"])) else math.nan)
        reportable.append(bool(tr["CF_reportable"]))
        # With one non-English test, p_holm is the unadjusted bootstrap p.
        rejected.append(bool(tr["p_holm"] < 0.05 and tr["Delta"] < 0.0))
    summary = _summarize_mc(cf_values, reportable, rejected)
    summary.update(
        {
            "base_seed": seed,
            "sample_seed_schedule": "base_seed + 10000 * replicate_index",
            "bootstrap_seed_schedule": "sample_seed + 1",
            "bootstrap_resamples": N_BOOT,
            "paired_identifier_assumption": (
                "The 8 task-seed identifiers are paired across languages and are "
                "independent of one another; shared difficulty across the two seed "
                "runs of one actual task is not modeled."
            ),
        }
    )
    return summary


def _load_observed_rates(path: Path = MAIN_RESULTS_PATH) -> dict:
    summary = json.loads(path.read_text(encoding="utf-8"))
    k10 = summary["point_estimates"][str(K)]
    en = k10["EN::gemini"]
    tr = k10["TR::gemini"]
    n_tasks = int(en["n"])
    n_languages = len(summary["scope"]["languages"])
    n_models = len(summary["scope"]["models"])
    per_cell_task_trials = int(summary["scope"]["task_trials"] / (n_languages * n_models))
    per_cell_replay_trials = int(summary["scope"]["replay_trials"] / (n_languages * n_models))
    if n_tasks != per_cell_task_trials or per_cell_replay_trials != n_tasks * K:
        raise ValueError("main results trial counts do not match the stated K=10 cells")
    return {
        "source": path.relative_to(REPO_ROOT).as_posix(),
        "k": K,
        "task_trials_per_cell": n_tasks,
        "isolated_replay_trials_per_cell": per_cell_replay_trials,
        "rates_are_laplace_smoothed": True,
        "p": {"EN": float(en["p"]), "TR": float(tr["p"])},
        "T": {"EN": float(en["T"]), "TR": float(tr["T"])},
        "observed_point_estimates": {
            "EN": {"p": float(en["p"]), "T": float(en["T"]), "T_ind": float(en["T_ind"])},
            "TR": {
                "p": float(tr["p"]),
                "T": float(tr["T"]),
                "T_ind": float(tr["T_ind"]),
                "r_obs": float(tr["r_obs"]),
                "r_ind": float(tr["r_ind"]),
                "CF": float(tr["CF"]),
                "Delta": float(tr["Delta"]),
            },
        },
    }


def _family_generation_parameters(observed: dict, *, alternative: bool) -> dict:
    """Set a 14-cell family with one observed-rate alternative or all nulls."""
    p_en = observed["p"]["EN"]
    t_en = observed["T"]["EN"]
    p_tr = observed["p"]["TR"]
    t_tr = observed["T"]["TR"]
    difficulty_mean = TASK_DIFFICULTY_BETA[0] / sum(TASK_DIFFICULTY_BETA)
    difficulty_moment = beta_moment(K, *TASK_DIFFICULTY_BETA)
    relative_p = {
        "AR": 0.97,
        "ES": 0.96,
        "HI": 0.95,
        "JA": 0.94,
        "SW": 0.93,
        "TR": p_tr / p_en,
        "ZH": 0.91,
    }
    cells: dict[str, dict] = {}
    for model in MODELS:
        for language in LANGUAGES:
            if language == "EN":
                p = p_en
                task_success = t_en
            else:
                ratio = relative_p[language]
                p = p_en * ratio
                task_success = t_en * ratio**K
                if alternative and language == "TR" and model == "gemini":
                    task_success = t_tr
            step_scale = p / difficulty_mean
            all_steps_rate = step_scale**K * difficulty_moment
            repair = (task_success - all_steps_rate) / (1.0 - all_steps_rate)
            if not 0.0 <= repair <= 1.0:
                raise ValueError(
                    f"calibrated repair probability for {language}/{model} is {repair}"
                )
            cells[f"{language}::{model}"] = {
                "language": language,
                "model": model,
                "p": p,
                "T": task_success,
                "relative_p_to_EN": p / p_en,
                "step_scale_given_q": step_scale,
                "E_q_K": difficulty_moment,
                "T_all_steps_valid": all_steps_rate,
                "repair_probability_after_step_failure": repair,
            }
    return {
        "difficulty_beta": {"alpha": TASK_DIFFICULTY_BETA[0], "beta": TASK_DIFFICULTY_BETA[1]},
        "difficulty_mean": difficulty_mean,
        "cells": cells,
    }


def generate_family_records(
    n_tasks: int,
    *,
    observed: dict,
    alternative: bool,
    seed: int,
    n_seeds: int = SEEDS_PER_TASK,
) -> tuple[list[TaskRecord], dict]:
    """Generate paired 8-language x 2-model task records under a calibrated DGP.

    Each underlying task has one shared Beta difficulty, reused by every
    language, model, and seed. Within a trajectory, invalid isolated steps can
    be repaired with a language/model-specific probability chosen so the
    marginal full-task rate equals the stated conditional target.
    """
    if n_tasks <= 0 or n_seeds <= 0:
        raise ValueError("n_tasks and n_seeds must be positive")
    parameters = _family_generation_parameters(observed, alternative=alternative)
    rng = np.random.default_rng(seed)
    alpha, beta = TASK_DIFFICULTY_BETA
    task_difficulty = rng.beta(alpha, beta, size=n_tasks)
    records: list[TaskRecord] = []
    for task_index, difficulty in enumerate(task_difficulty):
        task_id = f"family_task_{task_index:04d}"
        for model in MODELS:
            for language in LANGUAGES:
                cell = parameters["cells"][f"{language}::{model}"]
                step_probability = min(1.0, difficulty * cell["step_scale_given_q"])
                repair = cell["repair_probability_after_step_failure"]
                for seed_index in range(n_seeds):
                    steps = (rng.random(K) < step_probability).astype(int).tolist()
                    all_valid = all(steps)
                    success = int(all_valid or rng.random() < repair)
                    records.append(
                        TaskRecord(
                            f"{task_id}::seed_{seed_index}",
                            language,
                            model,
                            success,
                            steps,
                            task_id,
                        )
                    )
    return records, parameters


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    """Wilson 95% interval for a Monte Carlo rejection or power proportion."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("successes and trials must define a valid proportion")
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    half_width = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
        / denominator
    )
    return [max(0.0, center - half_width), min(1.0, center + half_width)]


def _rate_result(flags: list[bool]) -> dict:
    successes = int(sum(flags))
    trials = len(flags)
    return {
        "successes": successes,
        "replicates": trials,
        "rate": successes / trials,
        "wilson_95": _wilson_interval(successes, trials),
    }


def run_task_count_curve(
    observed: dict,
    *,
    mc_replicates: int = MC_REPLICATES,
    n_boot: int = N_BOOT,
) -> dict:
    """Estimate null rejection and conditional power by unique task count."""
    if mc_replicates <= 0 or n_boot <= 0:
        raise ValueError("Monte Carlo replicates and bootstrap resamples must be positive")
    from multilingual_compounding.metrics import bootstrap_cf

    target = ("TR", "gemini")
    curve: dict[str, dict] = {}
    for count_index, n_tasks in enumerate(TASK_COUNTS):
        null_one_cell: list[bool] = []
        null_target_holm: list[bool] = []
        null_family: list[bool] = []
        alt_one_cell: list[bool] = []
        alt_target_holm: list[bool] = []
        alt_family: list[bool] = []
        for replicate in range(mc_replicates):
            for alternative, one_cell_flags, target_holm_flags, family_flags in (
                (False, null_one_cell, null_target_holm, null_family),
                (True, alt_one_cell, alt_target_holm, alt_family),
            ):
                sample_seed = (
                    BASE_SEED
                    + 1_000_000
                    + count_index * 100_000
                    + replicate * 2
                    + int(alternative)
                )
                records, _parameters = generate_family_records(
                    n_tasks,
                    observed=observed,
                    alternative=alternative,
                    seed=sample_seed,
                )
                result = bootstrap_cf(
                    records,
                    K=K,
                    null="common",
                    n_boot=n_boot,
                    seed=sample_seed + 1,
                    min_log_rind=DEFAULT_MIN_LOG_RIND,
                    cluster_unit="underlying_task",
                )
                if len(result) != 14:
                    raise ValueError(f"expected 14 non-English cells, found {len(result)}")
                target_result = result[target]
                one_cell_reject = bool(
                    target_result["p_raw"] < 0.05
                    and target_result["Delta"] < 0.0
                )
                target_holm_reject = bool(
                    target_result["p_holm"] < 0.05
                    and target_result["Delta"] < 0.0
                )
                family_reject = any(
                    values["p_holm"] < 0.05 and values["Delta"] < 0.0
                    for values in result.values()
                )
                one_cell_flags.append(one_cell_reject)
                target_holm_flags.append(target_holm_reject)
                family_flags.append(family_reject)
        curve[str(n_tasks)] = {
            "unique_underlying_tasks": n_tasks,
            "seeds_per_task": SEEDS_PER_TASK,
            "task_seed_records_per_language_model_cell": n_tasks * SEEDS_PER_TASK,
            "null_false_positive": {
                "one_cell_unadjusted": _rate_result(null_one_cell),
                "target_cell_after_14_cell_holm": _rate_result(null_target_holm),
                "familywise_any_of_14_after_holm": _rate_result(null_family),
            },
            "conditional_power": {
                "one_cell_unadjusted": _rate_result(alt_one_cell),
                "target_cell_after_14_cell_holm": _rate_result(alt_target_holm),
                "familywise_any_of_14_after_holm": _rate_result(alt_family),
            },
        }
    return {
        "target_cell": "TR::gemini",
        "number_of_non_english_cells_in_holm_family": 14,
        "mc_replicates": mc_replicates,
        "bootstrap_resamples_per_replicate": n_boot,
        "bootstrap_cluster_unit": "underlying task; both seed rows stay together",
        "sample_seed_schedule": (
            "20261010 + 1000000 + task_count_index*100000 + replicate_index*2 + condition_bit"
        ),
        "bootstrap_seed_schedule": "sample_seed + 1",
        "independent_underlying_task_assumption": (
            "Each task-count row draws independent latent difficulty across underlying task clusters. The n=4 row is not an exact reconstruction of the existing BFCL task/scenario-variant layout."
        ),
        "null_process": {
            "description": (
                "All 14 tested cells have analytic CF=1. A shared Beta(9,1) task difficulty is reused across languages, models, and two seeds; isolated steps are conditionally independent, and language/model-specific rescue probabilities calibrate T to the null ratio."
            ),
            "parameters": _family_generation_parameters(observed, alternative=False),
        },
        "alternative_process": {
            "description": (
                "The same paired task-difficulty process is used, but TR::gemini task success is set to the observed Laplace-smoothed rate. Other 13 cells remain at CF=1. The observed EN/TR replay and success rates are treated as generating probabilities."
            ),
            "parameters": _family_generation_parameters(observed, alternative=True),
            "source_observed_rates": observed,
        },
        "by_unique_task_count": curve,
    }


def _load_historical_calibration() -> dict | None:
    """Keep the already generated v1 calibration inside the upgraded summary."""
    if not SUMMARY_PATH.exists():
        return None
    current = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if current.get("metadata", {}).get("calibration_version") == 2:
        return current.get("historical_v1")
    if "scenarios" in current and "metadata" in current:
        return current
    return None


def run_calibration(
    *, mc_replicates: int = MC_REPLICATES, n_boot: int = N_BOOT
) -> dict:
    """Run analytic process checks and paired-task Monte Carlo calibration."""
    observed = _load_observed_rates()
    m_tests = 14
    previous = _load_historical_calibration()
    scenarios: dict[str, dict] = {
        "independent_steps": _large_scenario(
            p_en=P_EN_KNOWN,
            p_tr=P_TR_KNOWN,
            alpha_en=1.0,
            alpha_tr=1.0,
            seed=BASE_SEED + 1,
        ),
        "shared_multiplicative_survival": _large_scenario(
            p_en=P_EN_KNOWN,
            p_tr=P_TR_KNOWN,
            alpha_en=0.70,
            alpha_tr=0.70,
            seed=BASE_SEED + 2,
        ),
        "extra_turkish_multiplicative_degradation": _large_scenario(
            p_en=P_EN_KNOWN,
            p_tr=P_TR_KNOWN,
            alpha_en=0.70,
            alpha_tr=0.35,
            seed=BASE_SEED + 3,
            bootstrap_seed=BASE_SEED + 4,
        ),
    }

    repair_cases = {
        "same_repair_probability": (0.10, 0.10),
        "language_specific_repair_probability": (0.10, 0.15),
    }
    repair_scenarios: dict[str, dict] = {}
    for index, (name, (rho_en, rho_tr)) in enumerate(repair_cases.items()):
        analytic = repair_process_expectations(
            P_EN_KNOWN, P_TR_KNOWN, rho_en, rho_tr
        )
        records = generate_repair_records(
            LARGE_N,
            p_by_language={"EN": P_EN_KNOWN, "TR": P_TR_KNOWN},
            repair_by_language={"EN": rho_en, "TR": rho_tr},
            n_seeds=SEEDS_PER_TASK,
            seed=BASE_SEED + 10 + index,
        )
        repair_scenarios[name] = {
            "analytic": analytic,
            "n_underlying_tasks": LARGE_N,
            "seeds_per_task": SEEDS_PER_TASK,
            "point_estimates_by_null": _point_estimates_both_nulls(records),
        }

    position_rates = {
        "EN": [0.96] * 8 + [0.66] * 2,
        "TR": [0.95] * 5 + [0.77] * 5,
    }
    position_task_rates = {
        language: float(np.prod(probabilities))
        for language, probabilities in position_rates.items()
    }
    position_expected = expected_metric_pair(
        position_rates, position_task_rates, k=K
    )
    position_records = generate_position_records(
        LARGE_N, position_rates, seed=BASE_SEED + 20
    )
    position_scenario = {
        "p_by_position": position_rates,
        "analytic_T": position_task_rates,
        "analytic_metrics": position_expected,
        "n_tasks": LARGE_N,
        "point_estimates_by_null": _point_estimates_both_nulls(position_records),
    }

    beta_alpha, beta_beta = TASK_DIFFICULTY_BETA
    q_mean = beta_alpha / (beta_alpha + beta_beta)
    q_k = beta_moment(K, beta_alpha, beta_beta)
    tr_scale = P_TR_KNOWN / P_EN_KNOWN
    shared_expected_T = {
        "EN": q_k,
        "TR": tr_scale**K * q_k,
    }
    shared_expected = expected_metric_pair(
        {"EN": [q_mean] * K, "TR": [tr_scale * q_mean] * K},
        shared_expected_T,
        k=K,
    )
    shared_records = generate_shared_difficulty_records(
        LARGE_N,
        scale_by_language={"EN": 1.0, "TR": tr_scale},
        n_seeds=SEEDS_PER_TASK,
        alpha=beta_alpha,
        beta=beta_beta,
        seed=BASE_SEED + 21,
    )
    shared_difficulty = {
        "beta_parameters": {"alpha": beta_alpha, "beta": beta_beta},
        "mean_difficulty": q_mean,
        "expected_q_to_K": q_k,
        "scale_by_language": {"EN": 1.0, "TR": tr_scale},
        "analytic_T": shared_expected_T,
        "analytic_metrics": shared_expected,
        "absolute_T_over_common_T_ind": {
            "EN": shared_expected_T["EN"] / q_mean**K,
            "TR": shared_expected_T["TR"] / (tr_scale * q_mean) ** K,
        },
        "n_underlying_tasks": LARGE_N,
        "seeds_per_task": SEEDS_PER_TASK,
        "point_estimates_by_null": _point_estimates_both_nulls(shared_records),
    }

    floor_current = best_case_holm_p(m_tests, n_boot)
    expanded = run_task_count_curve(
        observed, mc_replicates=mc_replicates, n_boot=n_boot
    )
    result = {
        "metadata": {
            "calibration_version": 2,
            "upgrade_note": (
                "Supersedes the prior 80-replicate/200-bootstrap synthetic run. "
                "The prior output is preserved under historical_v1. This is an "
                "expanded synthetic analysis, not a replication of numbers in "
                "the author response."
            ),
            "script": "scripts/run_cf_calibration.py",
            "metric_implementation": "src/multilingual_compounding/metrics.py",
            "base_seed": BASE_SEED,
            "k": K,
            "large_n_underlying_tasks": LARGE_N,
            "seeds_per_task_in_clustered_scenarios": SEEDS_PER_TASK,
            "task_count_curve": list(TASK_COUNTS),
            "monte_carlo_replicates": mc_replicates,
            "bootstrap_resamples": n_boot,
            "known_process_step_rates": {"EN": P_EN_KNOWN, "TR": P_TR_KNOWN},
            "bootstrap_test": "one-sided bootstrap tail for Delta < 0 with plus-one p-value",
            "rng": "numpy.default_rng; all generator and bootstrap seeds recorded or scheduled below",
        },
        "holm_resolution": {
            "number_of_tests": m_tests,
            "n_boot": n_boot,
            "best_case_adjusted_p": floor_current,
            "strict_0_05_possible": bool(floor_current < 0.05),
            "minimum_n_boot_for_strict_holm_p_below_0_05": minimum_resamples_for_strict_holm(m_tests),
            "derivation": "raw p_min=1/(n_boot+1); first Holm adjusted p_min=min(1,14/(n_boot+1))",
        },
        "cf_exclusion_rule": {
            "metric_default_min_abs_log_rind": DEFAULT_MIN_LOG_RIND,
            "report_CF_when": "abs(log(r_ind)) >= 0.05",
            "CF_numerically_undefined_when": "abs(log(r_ind)) <= 1e-9 in compute_cf",
            "Delta_reported_when_CF_excluded": True,
        },
        "analytic_scenarios": {
            "multiplicative_survival": scenarios,
            "repair": repair_scenarios,
            "unequal_position_difficulty": position_scenario,
            "shared_task_difficulty": shared_difficulty,
        },
        "null_and_conditional_power_curves": expanded,
        "historical_v1": previous,
    }
    return result


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{float(value):.{digits}f}"


def _rate_text(value: dict) -> str:
    lo, hi = value["wilson_95"]
    return f"{value['rate']:.3f} [{lo:.3f}, {hi:.3f}] ({value['successes']}/{value['replicates']})"


def render_report(summary: dict) -> str:
    scenarios = summary["analytic_scenarios"]
    curves = summary["null_and_conditional_power_curves"]["by_unique_task_count"]
    lines = [
        "# Expanded offline calibration of the compounding factor",
        "",
        "This report uses synthetic data and the repository metric implementation. It makes no model or API calls. It supersedes the earlier 80-replicate, 200-bootstrap calibration; that output is preserved as `historical_v1` in the summary JSON. These simulations are additional analyses, not a replication of numbers in the author response.",
        "",
        f"All principal runs use fixed base seed `{summary['metadata']['base_seed']}`, K={K}, {summary['metadata']['monte_carlo_replicates']} Monte Carlo replicates, and {summary['metadata']['bootstrap_resamples']:,} task-cluster bootstrap resamples. The task-count curves use two seed runs per underlying task and preserve both rows together in the bootstrap. Wilson intervals show Monte Carlo uncertainty in the reported rejection and power rates.",
        "",
        "## Analytic process checks",
        "",
        "The table gives population rates under each stated data-generating process. For every row, CF and Delta are shown under both the common-mean null (`p^K`) and the position-specific null (`prod_k p_k`).",
        "",
        "| Process | T_EN | T_TR | Common CF / Delta | Position CF / Delta |",
        "|---|---:|---:|---:|---:|",
    ]
    independent = scenarios["multiplicative_survival"]["independent_steps"]
    shared_survival = scenarios["multiplicative_survival"]["shared_multiplicative_survival"]
    extra_survival = scenarios["multiplicative_survival"]["extra_turkish_multiplicative_degradation"]
    survival_scenarios = [
        ("Independent steps", independent, 1.0, 1.0),
        ("Shared multiplicative survival (alpha=.70)", shared_survival, 0.70, 0.70),
        ("Extra Turkish multiplicative loss (alpha=.70/.35)", extra_survival, 0.70, 0.35),
    ]
    for label, result, alpha_en, alpha_tr in survival_scenarios:
        t_en = alpha_en * P_EN_KNOWN**K
        t_tr = alpha_tr * P_TR_KNOWN**K
        cf = result["analytic_expected_CF"]
        delta = math.log((t_tr / t_en) / ((P_TR_KNOWN / P_EN_KNOWN) ** K))
        lines.append(f"| {label} | {_fmt(t_en)} | {_fmt(t_tr)} | {_fmt(cf)} / {_fmt(delta)} | {_fmt(cf)} / {_fmt(delta)} |")
    for name, label in [
        ("same_repair_probability", "Same repair probability (rho=.10)"),
        ("language_specific_repair_probability", "Language-specific repair (rho=.10/.15)"),
    ]:
        analytic = scenarios["repair"][name]["analytic"]
        common = analytic["metrics"]["common"]
        position = analytic["metrics"]["position"]
        lines.append(
            f"| {label} | {_fmt(analytic['T']['EN'])} | {_fmt(analytic['T']['TR'])} | {_fmt(common['CF'])} / {_fmt(common['Delta'])} | {_fmt(position['CF'])} / {_fmt(position['Delta'])} |"
        )
    position = scenarios["unequal_position_difficulty"]
    common = position["analytic_metrics"]["common"]
    position_metric = position["analytic_metrics"]["position"]
    lines.append(
        f"| Unequal position difficulty, independent steps | {_fmt(position['analytic_T']['EN'])} | {_fmt(position['analytic_T']['TR'])} | {_fmt(common['CF'])} / {_fmt(common['Delta'])} | {_fmt(position_metric['CF'])} / {_fmt(position_metric['Delta'])} |"
    )
    difficulty = scenarios["shared_task_difficulty"]
    common = difficulty["analytic_metrics"]["common"]
    position_metric = difficulty["analytic_metrics"]["position"]
    lines.append(
        f"| Shared Beta(9,1) task difficulty, conditional independent steps | {_fmt(difficulty['analytic_T']['EN'])} | {_fmt(difficulty['analytic_T']['TR'])} | {_fmt(common['CF'])} / {_fmt(common['Delta'])} | {_fmt(position_metric['CF'])} / {_fmt(position_metric['Delta'])} |"
    )

    extra_boot = extra_survival["bootstrap"]
    lines.extend(
        [
            "",
            "In the shared-survival model, `T = alpha * p^K`; the common alpha cancels from the English-relative ratio, giving expected CF=1 and Delta=0. Repair uses a different rule: `T = p^K + rho * (1 - p^K)`. Because the repair term is additive and its effect depends on baseline `p^K`, even the same rescue probability in both languages does not generally cancel. In the displayed repair cases, the expected values differ from the multiplicative-survival null.",
            "",
            f"The unequal-position scenario sets EN step rates to eight positions at .96 and two at .66, and TR rates to five at .95 and five at .77. Their means remain .90 and .86. The position-specific null is correctly specified, so expected CF is 1 there; the common-mean `p^K` null is misspecified. Shared task difficulty draws one `q ~ Beta(9,1)` per underlying task and reuses it across languages and seeds. It makes `T` exceed `p^K` in both languages, yet CF remains 1 for the specified shared multiplicative difficulty model. This is a conditional cancellation result, not a general claim that dependence or repair cancels.",
            "",
            f"A 5,000-resample bootstrap of the illustrative extra-Turkish-multiplicative-loss sample gives CF 95% interval `{_fmt(extra_boot['TR_CF_CI_95'][0])}` to `{_fmt(extra_boot['TR_CF_CI_95'][1])}` and Delta interval `{_fmt(extra_boot['TR_Delta_CI_95'][0])}` to `{_fmt(extra_boot['TR_Delta_CI_95'][1])}`. This is a one-cell illustration, not a 14-cell test.",
            "",
            "## Null rejection and conditional power by task count",
            "",
            "Each Monte Carlo dataset contains eight languages and two backbones, producing the full 14-cell non-English Holm family. The null datasets have analytic CF=1 in every cell. Under both null and alternative, a Beta(9,1) task difficulty is shared across the languages, models, and two seed runs. The alternative changes only Turkish/Gemini task success to the observed Laplace-smoothed rate; other cells remain under the null. Step rates and task rates are treated as generating probabilities, and language/model-specific rescue probabilities make the stated task rates attainable under this synthetic process. Task difficulty is sampled independently across underlying task clusters. The n=4 row is therefore a four-independent-cluster simulation, not an exact reconstruction of the existing BFCL task IDs and scenario variants.",
            "",
            "The one-cell column uses the target cell's unadjusted bootstrap p-value. The familywise column records whether any of the 14 Holm-adjusted cells rejects. The adjusted target column gives power for Turkish/Gemini after the full family correction.",
            "",
            "| Unique tasks | Seed rows per cell | Null one-cell false positive | Null familywise false positive | Alternative one-cell power | Alternative TR/Gemini Holm power |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for task_count in TASK_COUNTS:
        curve = curves[str(task_count)]
        null = curve["null_false_positive"]
        power = curve["conditional_power"]
        lines.append(
            f"| {task_count} | {curve['task_seed_records_per_language_model_cell']} | {_rate_text(null['one_cell_unadjusted'])} | {_rate_text(null['familywise_any_of_14_after_holm'])} | {_rate_text(power['one_cell_unadjusted'])} | {_rate_text(power['target_cell_after_14_cell_holm'])} |"
        )
    observed = summary["null_and_conditional_power_curves"]["alternative_process"]["source_observed_rates"]
    n20 = curves["20"]
    n20_target_null = n20["null_false_positive"]["target_cell_after_14_cell_holm"]
    n20_family_null = n20["null_false_positive"]["familywise_any_of_14_after_holm"]
    n20_target_power = n20["conditional_power"]["target_cell_after_14_cell_holm"]
    lines.extend(
        [
            "",
            f"At n=20, the Turkish/Gemini Holm false-positive estimate is `{_rate_text(n20_target_null)}`, the 14-cell familywise false-positive estimate is `{_rate_text(n20_family_null)}`, and the adjusted Turkish/Gemini power under the stated alternative is `{_rate_text(n20_target_power)}`.",
            "",
            f"The conditional alternative uses source rates `p_EN={_fmt(observed['p']['EN'])}`, `p_TR={_fmt(observed['p']['TR'])}`, `T_EN={_fmt(observed['T']['EN'])}`, and `T_TR={_fmt(observed['T']['TR'])}` from `{observed['source']}`. The expected Turkish/Gemini CF and Delta under these rates are `{_fmt(observed['observed_point_estimates']['TR']['CF'])}` and `{_fmt(observed['observed_point_estimates']['TR']['Delta'])}`. These power estimates are conditional on that observed effect and the synthetic shared-difficulty/repair model. They are not prospective guarantees or evidence that any task count is adequate. A prospective 20-task collection should sample five distinct scenario indices per category and preserve a horizon distribution close to the current tasks; the n=20 curve is only an idealized independent-cluster calculation.",
            "",
            f"The Monte Carlo rate intervals are Wilson 95% intervals based on {summary['metadata']['monte_carlo_replicates']} replicates. Their width remains material near a 5% error rate, especially at the smallest task counts. The 5,000 bootstrap resamples reduce the 14-cell Holm resolution floor to `{_fmt(summary['holm_resolution']['best_case_adjusted_p'], 5)}`; they add numerical resolution, not independent task information.",
            "",
            "The simulated false-positive rates, especially for the 14-cell family, are higher than the nominal 5% level under this shared-difficulty null. This indicates that the current one-sided bootstrap-tail p-value is not validated for this dependence structure. The results should not be used as confirmatory inference until the test is recalibrated or validated under a null model that matches the task and seed dependencies.",
            "",
            "## Reproduction and limits",
            "",
            "The fixed generator and bootstrap seed schedules, full process parameters, point estimates, Monte Carlo counts, and Wilson intervals are in `analysis/bfcl/cf_calibration_summary.json`. The earlier calibration remains nested under `historical_v1`; the expanded values do not reproduce the review-response simulation figures.",
            "",
            "Reproduce with `python scripts/run_cf_calibration.py`. For a shorter diagnostic run, pass `--mc-replicates` and `--bootstrap-resamples`; do not use reduced settings as the reported results.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--mc-replicates", type=int, default=MC_REPLICATES)
    parser.add_argument("--bootstrap-resamples", type=int, default=N_BOOT)
    args = parser.parse_args()

    summary = run_calibration(
        mc_replicates=args.mc_replicates,
        n_boot=args.bootstrap_resamples,
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    print(f"Wrote {args.summary.relative_to(REPO_ROOT) if args.summary.is_relative_to(REPO_ROOT) else args.summary}")
    print(f"Wrote {args.report.relative_to(REPO_ROOT) if args.report.is_relative_to(REPO_ROOT) else args.report}")


if __name__ == "__main__":
    main()
