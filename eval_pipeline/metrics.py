"""
Metrics module — per-outcome, with bootstrap 95% CIs.

Computes:
  - MAE
  - Spearman ρ
  - Quadratic-weighted Cohen's κ
  - ICC(2,1)  (two-way random, absolute agreement, single measures)
  - Exact accuracy  (predicted rounded == actual rounded)
  - Adjacent accuracy (|predicted_round - actual_round| <= 1)
  - Bland-Altman bias + LoA
  - Inter-run SD
  - HEADLINE: Δ-correlation = Spearman between (pred_post - actual_pre) and (actual_post - actual_pre)

All estimation-based, no NHST. Bootstrap CIs use percentile method.
"""

import math
import warnings
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from scipy import stats
from sklearn.metrics import cohen_kappa_score


# ---------------------------------------------------------------------------
# Bootstrap helper
# ---------------------------------------------------------------------------

def _bootstrap_ci(
    func,
    *arrays,
    n_boot: int = 2000,
    ci: float = 0.95,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Compute bootstrap CI for a statistic function.

    func(*arrays) -> scalar
    Returns (point_estimate, lower, upper)
    """
    rng = np.random.default_rng(seed)
    n = len(arrays[0])
    point = func(*arrays)
    boot_stats = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sampled = [a[idx] for a in arrays]
        try:
            val = func(*sampled)
            if np.isfinite(val):
                boot_stats.append(val)
        except Exception:
            pass
    if len(boot_stats) < 10:
        return point, float("nan"), float("nan")
    alpha = (1 - ci) / 2
    lo = float(np.percentile(boot_stats, 100 * alpha))
    hi = float(np.percentile(boot_stats, 100 * (1 - alpha)))
    return float(point), lo, hi


# ---------------------------------------------------------------------------
# Individual metric functions (operate on numpy arrays)
# ---------------------------------------------------------------------------

def mae(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - actual)))


def spearman(pred: np.ndarray, actual: np.ndarray) -> float:
    if len(pred) < 3:
        return float("nan")
    r, _ = stats.spearmanr(pred, actual)
    return float(r) if np.isfinite(r) else float("nan")


def qwk(pred: np.ndarray, actual: np.ndarray, scale_lo: int = 1, scale_hi: int = 7) -> float:
    """Quadratic-weighted Cohen's κ."""
    if len(pred) < 2:
        return float("nan")
    pred_r = np.clip(np.round(pred), scale_lo, scale_hi).astype(int)
    actual_r = np.clip(np.round(actual), scale_lo, scale_hi).astype(int)
    labels = list(range(scale_lo, scale_hi + 1))
    try:
        # cohen_kappa_score divides by expected agreement, which is 0 when a
        # rater is constant (degenerate) → emits a RuntimeWarning and returns
        # nan. Suppress the warning and report nan cleanly.
        with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            k = cohen_kappa_score(actual_r, pred_r, labels=labels, weights="quadratic")
        return float(k) if np.isfinite(k) else float("nan")
    except Exception:
        return float("nan")


def icc21(pred: np.ndarray, actual: np.ndarray) -> float:
    """
    ICC(2,1) — two-way random, absolute agreement, single measures.

    Using the formula:
      MSB = between-subjects variance
      MSW = within-subjects variance
      MSE = residual (error)
      ICC(2,1) = (MSB - MSE) / (MSB + (k-1)*MSE + k/n*(MSR - MSE))
    where k=2 raters, n=subjects.

    Simplified for k=2:
      grand mean, row means, col means, residuals
    """
    n = len(pred)
    if n < 3:
        return float("nan")
    data = np.column_stack([actual, pred])  # n x 2
    k = 2
    grand_mean = np.mean(data)
    row_means = np.mean(data, axis=1)
    col_means = np.mean(data, axis=0)

    SS_between = k * np.sum((row_means - grand_mean) ** 2)
    SS_within = np.sum((data - row_means[:, None]) ** 2)
    SS_cols = n * np.sum((col_means - grand_mean) ** 2)
    SS_error = SS_within - SS_cols

    df_between = n - 1
    df_within = n * (k - 1)
    df_cols = k - 1
    df_error = df_within - df_cols

    if df_between <= 0 or df_error <= 0:
        return float("nan")

    MS_between = SS_between / df_between
    MS_error = SS_error / df_error
    MS_cols = SS_cols / df_cols if df_cols > 0 else 0

    denom = MS_between + (k - 1) * MS_error + (k / n) * (MS_cols - MS_error)
    if denom == 0:
        return float("nan")
    icc = (MS_between - MS_error) / denom
    return float(icc)


def exact_accuracy(pred: np.ndarray, actual: np.ndarray, scale_lo: int = 1, scale_hi: int = 7) -> float:
    pred_r = np.clip(np.round(pred), scale_lo, scale_hi).astype(int)
    actual_r = np.clip(np.round(actual), scale_lo, scale_hi).astype(int)
    return float(np.mean(pred_r == actual_r))


def adjacent_accuracy(pred: np.ndarray, actual: np.ndarray, scale_lo: int = 1, scale_hi: int = 7) -> float:
    pred_r = np.clip(np.round(pred), scale_lo, scale_hi).astype(int)
    actual_r = np.clip(np.round(actual), scale_lo, scale_hi).astype(int)
    return float(np.mean(np.abs(pred_r - actual_r) <= 1))


def bland_altman(pred: np.ndarray, actual: np.ndarray) -> Tuple[float, float, float]:
    """Returns (bias, lower_loa, upper_loa)."""
    diff = pred - actual
    bias = float(np.mean(diff))
    sd = float(np.std(diff, ddof=1)) if len(diff) > 1 else float("nan")
    lo = bias - 1.96 * sd
    hi = bias + 1.96 * sd
    return bias, lo, hi


def delta_correlation(
    pred_post: np.ndarray,
    actual_pre: np.ndarray,
    actual_post: np.ndarray,
) -> float:
    """
    Δ-correlation: Spearman between (predicted_post - actual_pre) and (actual_post - actual_pre).
    Measures whether the model captures change from baseline.
    """
    delta_pred = pred_post - actual_pre
    delta_actual = actual_post - actual_pre
    if len(delta_pred) < 3 or np.std(delta_pred) == 0 or np.std(delta_actual) == 0:
        return float("nan")
    r, _ = stats.spearmanr(delta_pred, delta_actual)
    return float(r) if np.isfinite(r) else float("nan")


# ---------------------------------------------------------------------------
# Full per-outcome metric bundle with CIs
# ---------------------------------------------------------------------------

def compute_metrics(
    pred: np.ndarray,
    actual: np.ndarray,
    actual_pre: Optional[np.ndarray] = None,
    scale_lo: int = 1,
    scale_hi: int = 7,
    n_boot: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Compute the full metric bundle for one outcome.

    Returns dict with point estimates and (lo, hi) CI tuples.
    """
    pred = np.asarray(pred, dtype=float)
    actual = np.asarray(actual, dtype=float)
    n = len(pred)

    result: Dict[str, Any] = {"n": n}

    # --- MAE ---
    mae_val, mae_lo, mae_hi = _bootstrap_ci(mae, pred, actual, n_boot=n_boot, seed=seed)
    result["mae"] = (mae_val, mae_lo, mae_hi)

    # --- Spearman ρ ---
    rho_val, rho_lo, rho_hi = _bootstrap_ci(spearman, pred, actual, n_boot=n_boot, seed=seed)
    result["spearman"] = (rho_val, rho_lo, rho_hi)

    # --- QWK ---
    qwk_fn = lambda p, a: qwk(p, a, scale_lo, scale_hi)
    qwk_val, qwk_lo, qwk_hi = _bootstrap_ci(qwk_fn, pred, actual, n_boot=n_boot, seed=seed)
    result["qwk"] = (qwk_val, qwk_lo, qwk_hi)

    # --- ICC(2,1) ---
    icc_val, icc_lo, icc_hi = _bootstrap_ci(icc21, pred, actual, n_boot=n_boot, seed=seed)
    result["icc21"] = (icc_val, icc_lo, icc_hi)

    # --- Accuracy ---
    ea_fn = lambda p, a: exact_accuracy(p, a, scale_lo, scale_hi)
    ea_val, ea_lo, ea_hi = _bootstrap_ci(ea_fn, pred, actual, n_boot=n_boot, seed=seed)
    result["exact_acc"] = (ea_val, ea_lo, ea_hi)

    adj_fn = lambda p, a: adjacent_accuracy(p, a, scale_lo, scale_hi)
    adj_val, adj_lo, adj_hi = _bootstrap_ci(adj_fn, pred, actual, n_boot=n_boot, seed=seed)
    result["adjacent_acc"] = (adj_val, adj_lo, adj_hi)

    # --- Bland-Altman ---
    bias, ba_lo, ba_hi = bland_altman(pred, actual)
    result["ba_bias"] = bias
    result["ba_loa"] = (ba_lo, ba_hi)

    # --- Δ-correlation ---
    if actual_pre is not None and len(actual_pre) == n:
        actual_pre = np.asarray(actual_pre, dtype=float)
        dc_fn = lambda p, a_post: delta_correlation(p, actual_pre[:len(p)], a_post)
        dc_val, dc_lo, dc_hi = _bootstrap_ci(dc_fn, pred, actual, n_boot=n_boot, seed=seed)
        result["delta_corr"] = (dc_val, dc_lo, dc_hi)
    else:
        result["delta_corr"] = (float("nan"), float("nan"), float("nan"))

    return result


def compute_interrun_sd(per_run_preds: List[np.ndarray]) -> np.ndarray:
    """
    Compute per-participant inter-run standard deviation across k runs.
    per_run_preds: list of arrays, each shape (n_participants,)
    Returns array of shape (n_participants,) with SD per participant.
    """
    stacked = np.stack(per_run_preds, axis=1)  # (n_participants, k_runs)
    return np.std(stacked, axis=1, ddof=1)
