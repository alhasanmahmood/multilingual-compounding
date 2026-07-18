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
  - task-level bootstrap CIs and a one-sided test of CF>1 (Delta<0)
    with Holm-Bonferroni correction across (language, backbone) cells.

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
    task_id: str                  # task identifier for paired task-level bootstrap
    language: str                 # e.g. "EN", "English", "TR", "SW"
    backbone: str                 # e.g. "model_A"
    success: int                  # full multi-turn task outcome y in {0,1}
    step_validity: list[int]      # SINGLE-TURN validity of each critical step, in order


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
                 min_log_rind: float = 0.05) -> dict:
    """
    Task-level bootstrap CIs for CF and Delta, and a one-sided test of
    Delta<0 (equivalently CF>1) with Holm-Bonferroni correction across
    non-English (language, backbone) cells.

    min_log_rind restricts CF reporting to cells where |log r_ind| is bounded
    away from 0 (i.e. r_ind bounded away from 1), per Sec. 4. Delta is always
    reported because it is well defined throughout.
    """
    rng = np.random.default_rng(seed)
    point = compute_cf(records, K, null)
    cells = [c for c in point if not _is_english(c[0])]

    # group by backbone and task id so the bootstrap resamples paired tasks
    # across all languages for the same backbone.
    task_groups_by_backbone: dict[str, dict[str, list[TaskRecord]]] = {}
    for r in records:
        task_groups_by_backbone.setdefault(r.backbone, {}).setdefault(r.task_id, []).append(r)

    boot_delta = {c: [] for c in cells}
    boot_cf = {c: [] for c in cells}
    for _ in range(n_boot):
        resampled: list[TaskRecord] = []
        for task_groups in task_groups_by_backbone.values():
            task_ids = np.array(sorted(task_groups))
            picked_task_ids = rng.choice(task_ids, size=len(task_ids), replace=True)
            for task_id in picked_task_ids:
                resampled.extend(task_groups[str(task_id)])
        bres = compute_cf(resampled, K, null)
        for c in cells:
            if c in bres:
                boot_delta[c].append(bres[c]["Delta"])
                boot_cf[c].append(bres[c]["CF"])

    # one-sided p-value for Delta<0 : fraction of bootstrap draws with Delta>=0
    raw = {}
    for c in cells:
        d = np.array(boot_delta[c], dtype=float)
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
        d = np.array(boot_delta[c], dtype=float); d = d[~np.isnan(d)]
        cf = np.array(boot_cf[c], dtype=float); cf = cf[~np.isnan(cf)]
        reportable_cf = abs(np.log(point[c]["r_ind"])) >= min_log_rind
        result[c] = {
            **point[c],
            "Delta_CI": (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))) if len(d) else (np.nan, np.nan),
            "CF_CI": (float(np.percentile(cf, 2.5)), float(np.percentile(cf, 97.5))) if len(cf) else (np.nan, np.nan),
            "p_holm": holm.get(c, np.nan),
            "CF_reportable": bool(reportable_cf),
            "compounding": bool(holm.get(c, 1.0) < 0.05 and point[c]["Delta"] < 0),
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