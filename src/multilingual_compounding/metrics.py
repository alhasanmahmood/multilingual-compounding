"""
metrics.py
----------
Reference implementation of the compounding metrics used in
"When Do Errors Compound Across Languages?: Heterogeneous Multilingual
Reliability of Long-Horizon Agentic Tool Use".

This computes, per (language, backbone):
  - per-step validity rate p(l,b)
  - task success rate T(l,b)
  - independence-null prediction T_ind = p^K
    and the position-specific null prod_k p_k
  - the compounding factor  CF = log r_obs / log r_ind
  - the robust complement   Delta = log r_obs - log r_ind
  - task-cluster bootstrap intervals and directional tail diagnostics for
    Delta<0, with Holm adjustment across (language, backbone) cells.

This module implements only the math layer. It does not run any benchmark.
Feed it the per-task records produced by the evaluation pipeline. Each record
must include:the task id so that the bootstrap can resample tasks, not individual
language-specific rows.

Dependencies: numpy. (The implementation is pure numpy.)
    pip install numpy

Author note: verify against the manuscript before trusting the numbers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
import numpy as np

ENGLISH_LABELS = {"EN", "ENGLISH"}


@dataclass
class TaskRecord:
    """One executed task instance.

    IMPORTANT: step_validity must be the SINGLE-TURN validity of each critical
    step (the step replayed in isolation with gold preceding context), NOT the
    marginal validity of calls emitted inside the full trajectory. `success` is
    the full multi-turn task outcome. CF>1 then means the trajectory composed
    worse than the independent product of single-turn competence (compounding).
    Using in-trajectory marginal validity here makes the test circular and
    flips the sign of CF.
    """
    task_id: str                  # task-seed identifier for paired bootstrap
    language: str                 # e.g. "EN", "English", "TR", "SW"
    backbone: str                 # e.g. "model_A"
    success: int                  # full multi-turn task outcome y in {0,1}
    step_validity: list[int]      # SINGLE-TURN validity of each critical step, in order
    underlying_task_id: str | None = None  # groups multiple seeds of the same task
    task_variant_id: str | None = None  # category-specific BFCL row within a scenario family


def _is_english(label: str) -> bool:
    return label.strip().upper() in ENGLISH_LABELS


def _laplace_rate(successes: float, trials: float) -> float:
    """Add-one (Laplace) smoothing so logs are always defined (Sec. 4)."""
    return (successes + 1.0) / (trials + 2.0)


def _aggregate(records: Sequence[TaskRecord]) -> dict:
    """Compute p, T, and step-position-specific validity for one cell."""
    n_tasks = len(records)
    succ = sum(r.success for r in records)
    all_steps = [v for r in records for v in r.step_validity]
    p = _laplace_rate(sum(all_steps), len(all_steps)) if all_steps else np.nan
    T = _laplace_rate(succ, n_tasks)
    # position-specific validity p_k = mean validity at position k
    max_len = max((len(r.step_validity) for r in records), default=0)
    pos_valid = []
    for k in range(max_len):
        col = [r.step_validity[k] for r in records if len(r.step_validity) > k]
        pos_valid.append(_laplace_rate(sum(col), len(col)))
    return {"n": n_tasks, "p": p, "T": T, "p_pos": np.array(pos_valid)}


def _cell_predictions(agg: dict, K: int) -> dict:
    """Independence-null task-success predictions for one cell."""
    p = agg["p"]
    T_ind_common = p ** K
    # position-specific product over the first K positions (pad with p if short)
    p_pos = agg["p_pos"]
    if len(p_pos) >= K:
        T_ind_pos = float(np.prod(p_pos[:K]))
    elif len(p_pos) > 0:
        T_ind_pos = float(np.prod(p_pos)) * (p ** (K - len(p_pos)))
    else:
        T_ind_pos = T_ind_common
    return {"T_ind_common": T_ind_common, "T_ind_pos": T_ind_pos}


def compute_cf(records: Sequence[TaskRecord], K: int,
               null: str = "common") -> dict:
    """
    CF and Delta per (language, backbone), relative to English.
    null: "common" -> T_ind = p^K ; "position" -> prod_k p_k.
    Returns {(lang, backbone): {p, T, T_ind, r_obs, r_ind, CF, Delta}}.
    """
    by_cell: dict[tuple[str, str], list[TaskRecord]] = {}
    for r in records:
        by_cell.setdefault((r.language, r.backbone), []).append(r)

    agg = {cell: _aggregate(recs) for cell, recs in by_cell.items()}
    pred = {cell: _cell_predictions(agg[cell], K) for cell in agg}
    tkey = "T_ind_common" if null == "common" else "T_ind_pos"

    backbones = sorted({b for (_, b) in by_cell})
    out: dict[tuple[str, str], dict] = {}
    for b in backbones:
        english_cells = [cell for cell in agg if cell[1] == b and _is_english(cell[0])]
        if len(english_cells) != 1:
            raise ValueError(
                f"Expected exactly one English baseline for backbone {b}, found {english_cells}"
            )
        en_cell = english_cells[0]
        if en_cell not in agg:
            raise ValueError(f"Missing English baseline for backbone {b}")
        T_en, Tind_en = agg[en_cell]["T"], pred[en_cell][tkey]
        for (lang, bb), a in agg.items():
            if bb != b:
                continue
            T, Tind = a["T"], pred[(lang, bb)][tkey]
            r_obs = T / T_en
            r_ind = Tind / Tind_en
            if _is_english(lang):
                CF, Delta = np.nan, 0.0   # reference language
            else:
                log_obs, log_ind = np.log(r_obs), np.log(r_ind)
                Delta = log_obs - log_ind
                CF = log_obs / log_ind if abs(log_ind) > 1e-9 else np.nan
            out[(lang, b)] = {"p": a["p"], "T": T, "T_ind": Tind,
                              "r_obs": r_obs, "r_ind": r_ind,
                              "CF": CF, "Delta": Delta, "n": a["n"]}
    return out


def bootstrap_cf(records: Sequence[TaskRecord], K: int, null: str = "common",
                 n_boot: int = 1000, seed: int = 0,
                 min_log_rind: float = 0.05,
                 cluster_unit: str = "task_seed") -> dict:
    """
    Cluster bootstrap intervals for CF and Delta, plus a directional
    bootstrap-tail diagnostic for Delta<0, with Holm
    adjustment across non-English (language, backbone) cells. These tail
    probabilities are not calibrated inferential p-values; retain them as
    descriptive diagnostics only.

    min_log_rind restricts CF reporting to cells where |log r_ind| is bounded
    away from 0 (i.e. r_ind bounded away from 1), per Sec. 4. Delta is always
    reported because it is well defined throughout.

    ``task_seed`` resamples each task-variant/run-label row as a separate
    cluster. The ``underlying_task`` option groups all category variants and
    seed runs that share an underlying scenario, while keeping language rows
    paired. At least two clusters are required; a single scenario cannot
    provide a bootstrap variance estimate. Returned diagnostics record the
    resample count, seed, cluster unit, and number of sampled clusters.
    """
    if cluster_unit not in {"task_seed", "underlying_task"}:
        raise ValueError("cluster_unit must be 'task_seed' or 'underlying_task'")
    if n_boot < 1:
        raise ValueError("n_boot must be positive")

    rng = np.random.default_rng(seed)
    point = compute_cf(records, K, null)
    cells = [c for c in point if not _is_english(c[0])]
    boot_delta = {c: np.empty(n_boot, dtype=float) for c in cells}
    boot_cf = {c: np.empty(n_boot, dtype=float) for c in cells}

    # Prepare cluster-by-cell sufficient statistics once. Each draw then
    # recomputes the smoothed rates through matrix multiplication rather than
    # rebuilding TaskRecord lists 5,000 times.
    records_by_backbone: dict[str, list[TaskRecord]] = {}
    for record in records:
        records_by_backbone.setdefault(record.backbone, []).append(record)

    cluster_counts_by_backbone: dict[str, int] = {}
    for backbone, backbone_records in records_by_backbone.items():
        cluster_key = (
            (lambda r: r.task_id)
            if cluster_unit == "task_seed"
            else (lambda r: r.underlying_task_id or r.task_id)
        )
        cluster_ids = sorted({cluster_key(r) for r in backbone_records})
        if len(cluster_ids) < 2:
            raise ValueError(
                f"Bootstrap unavailable for {cluster_unit}: backbone {backbone} has "
                f"only {len(cluster_ids)} cluster(s); at least two are required"
            )
        cluster_index = {cluster_id: i for i, cluster_id in enumerate(cluster_ids)}
        language_labels = sorted({r.language for r in backbone_records})
        cell_ids = [(language, backbone) for language in language_labels]
        cell_index = {cell: i for i, cell in enumerate(cell_ids)}
        max_positions = max((len(r.step_validity) for r in backbone_records), default=0)

        shape = (len(cluster_ids), len(cell_ids))
        cluster_n = np.zeros(shape, dtype=float)
        cluster_success = np.zeros(shape, dtype=float)
        cluster_step_n = np.zeros(shape, dtype=float)
        cluster_step_success = np.zeros(shape, dtype=float)
        pos_shape = (len(cluster_ids), len(cell_ids), max_positions)
        cluster_pos_n = np.zeros(pos_shape, dtype=float)
        cluster_pos_success = np.zeros(pos_shape, dtype=float)
        for record in backbone_records:
            j = cluster_index[cluster_key(record)]
            c = cell_index[(record.language, backbone)]
            cluster_n[j, c] += 1.0
            cluster_success[j, c] += record.success
            cluster_step_n[j, c] += len(record.step_validity)
            cluster_step_success[j, c] += sum(record.step_validity)
            for position, valid in enumerate(record.step_validity):
                cluster_pos_n[j, c, position] += 1.0
                cluster_pos_success[j, c, position] += valid

        cluster_count = len(cluster_ids)
        cluster_counts_by_backbone[backbone] = cluster_count
        draw_counts = rng.multinomial(
            cluster_count,
            np.full(cluster_count, 1.0 / cluster_count),
            size=n_boot,
        ).astype(float)
        n_tasks = draw_counts @ cluster_n
        successes = draw_counts @ cluster_success
        step_trials = draw_counts @ cluster_step_n
        step_successes = draw_counts @ cluster_step_success
        p = (step_successes + 1.0) / (step_trials + 2.0)
        task_success = (successes + 1.0) / (n_tasks + 2.0)

        if null == "common":
            t_ind = p**K
        elif null == "position":
            pos_n = np.einsum("bj,jcp->bcp", draw_counts, cluster_pos_n)
            pos_success = np.einsum("bj,jcp->bcp", draw_counts, cluster_pos_success)
            pos_rates = (pos_success + 1.0) / (pos_n + 2.0)
            t_ind = np.empty_like(p)
            positions = np.arange(1, max_positions + 1)
            for c in range(len(cell_ids)):
                if max_positions:
                    observed_positions = np.max(
                        np.where(pos_n[:, c, :] > 0.0, positions[None, :], 0),
                        axis=1,
                    )
                    used_rates = np.where(
                        (positions[None, :] <= K)
                        & (positions[None, :] <= observed_positions[:, None]),
                        pos_rates[:, c, :],
                        1.0,
                    )
                    products = np.prod(used_rates, axis=1)
                else:
                    observed_positions = np.zeros(n_boot, dtype=int)
                    products = np.ones(n_boot, dtype=float)
                pad_exponent = np.maximum(K - observed_positions, 0)
                t_ind[:, c] = products * np.where(
                    pad_exponent > 0, p[:, c] ** pad_exponent, 1.0
                )
        else:
            raise ValueError("null must be 'common' or 'position'")

        en_cells = [i for i, label in enumerate(language_labels) if _is_english(label)]
        if len(en_cells) != 1:
            raise ValueError(
                f"Expected exactly one English baseline for backbone {backbone}, found "
                f"{[language_labels[i] for i in en_cells]}"
            )
        en = en_cells[0]
        for c, (language, bb) in enumerate(cell_ids):
            key = (language, bb)
            if key not in boot_delta:
                continue
            log_obs = np.log(task_success[:, c] / task_success[:, en])
            log_ind = np.log(t_ind[:, c] / t_ind[:, en])
            boot_delta[key][:] = log_obs - log_ind
            boot_cf[key][:] = np.divide(
                log_obs,
                log_ind,
                out=np.full(n_boot, np.nan, dtype=float),
                where=np.abs(log_ind) > 1e-9,
            )

    # Directional tail probability for Delta<0, retained under its legacy
    # p-value name for artifact compatibility. Calibration finds this tail is
    # not generally type-I-error calibrated for the independence null.
    raw = {}
    for c in cells:
        d = boot_delta[c]
        d = d[~np.isnan(d)]
        p_val = (np.sum(d >= 0.0) + 1) / (len(d) + 1) if len(d) else np.nan
        raw[c] = p_val

    # Holm-Bonferroni across cells
    valid = [(c, p) for c, p in raw.items() if not np.isnan(p)]
    valid.sort(key=lambda kv: kv[1])
    m = len(valid)
    holm = {}
    prev = 0.0
    for rank, (c, p) in enumerate(valid):
        adj = min(1.0, max(prev, (m - rank) * p))
        holm[c] = adj
        prev = adj

    result = {}
    for c in cells:
        d = boot_delta[c]; d = d[~np.isnan(d)]
        cf = boot_cf[c]; cf = cf[~np.isnan(cf)]
        reportable_cf = abs(np.log(point[c]["r_ind"])) >= min_log_rind
        result[c] = {
            **point[c],
            "Delta_CI": (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))) if len(d) else (np.nan, np.nan),
            "CF_CI": (float(np.percentile(cf, 2.5)), float(np.percentile(cf, 97.5))) if len(cf) else (np.nan, np.nan),
            "p_raw": float(raw[c]),
            "p_holm": holm.get(c, np.nan),
            "bootstrap_tail_probability": float(raw[c]),
            "holm_adjusted_bootstrap_tail_probability": holm.get(c, np.nan),
            "CF_reportable": bool(reportable_cf),
            "compounding": bool(holm.get(c, 1.0) < 0.05 and point[c]["Delta"] < 0),
            "inference_status": "uncalibrated_tail_diagnostic",
            "compounding_status": "legacy_diagnostic_flag_not_inferential",
            "n_boot": n_boot,
            "seed": seed,
            "cluster_unit": cluster_unit,
            "cluster_count": cluster_counts_by_backbone[c[1]],
        }
    return result


if __name__ == "__main__":
    # ---- synthetic smoke test illustrating CF>1 (compounding) ----
    # step_validity = SINGLE-TURN competence per step (isolated).
    # success       = full multi-turn outcome.
    # EN: steps compose independently -> success = all single-turn valid (CF~1).
    # TR: same single-turn competence but an extra trajectory-level "compounding
    #     hit" lowers success below the independent product -> CF>1.
    rng = np.random.default_rng(42)

    def make(lang, p_single, compound_survival, n=600, K=6, backbone="model_A"):
        recs = []
        for i in range(n):
            steps = [int(rng.random() < p_single) for _ in range(K)]
            all_valid = all(steps)
            succ = int(all_valid and (rng.random() < compound_survival))
            recs.append(TaskRecord(f"{lang}_{i}", lang, backbone, succ, steps))
        return recs

    # EN: survival 1.0 (no compounding) ; TR: survival 0.6 (strong compounding)
    data = make("EN", 0.95, 1.0) + make("TR", 0.92, 0.60)
    res = bootstrap_cf(data, K=6, null="common", n_boot=500)
    for (lang, b), v in res.items():
        print(f"{lang}/{b}: T={v['T']:.3f} p_single={v['p']:.3f} "
              f"CF={v['CF']:.2f} Delta={v['Delta']:+.3f} "
              f"DeltaCI{tuple(round(x,3) for x in v['Delta_CI'])} "
              f"p_holm={v['p_holm']:.3f} compounding={v['compounding']}")
    print("\nExpected: TR shows CF>1, Delta<0, compounding=True.")
