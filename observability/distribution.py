from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return np.sort(array[np.isfinite(array)])


def _ks_statistic(left: np.ndarray, right: np.ndarray) -> float:
    points = np.sort(np.unique(np.concatenate((left, right))))
    left_cdf = np.searchsorted(left, points, side="right") / left.size
    right_cdf = np.searchsorted(right, points, side="right") / right.size
    return float(np.max(np.abs(left_cdf - right_cdf)))


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect location and shape drift with an empirical two-sample KS test."""
    current = _finite(current_values)
    baseline = _finite(baseline_values)
    if current.size < 2 or baseline.size < 2:
        return {"is_anomaly": False, "score": 0.0, "method": "ks_robust", "reason": "insufficient_input"}

    ks = _ks_statistic(current, baseline)
    critical = min(1.0, 1.36 * np.sqrt((current.size + baseline.size) / (current.size * baseline.size)))
    baseline_median = float(np.median(baseline))
    current_median = float(np.median(current))
    mad = float(np.median(np.abs(baseline - baseline_median)))
    if mad <= np.finfo(float).eps:
        fallback_scale = max(abs(baseline_median) * 0.01, 1e-9)
        robust_shift = abs(current_median - baseline_median) / fallback_scale
    else:
        robust_shift = abs(current_median - baseline_median) / (1.4826 * mad)
    shifted = ks > critical or robust_shift >= ratio_threshold
    return {
        "is_anomaly": bool(shifted),
        "score": float(ks),
        "method": "ks_robust",
        "reason": (
            f"ks={ks:.4f}, critical={critical:.4f}, "
            f"baseline_median={baseline_median:.3f}, current_median={current_median:.3f}, "
            f"robust_shift={robust_shift:.3f}"
        ),
        "ks_statistic": float(ks),
        "robust_location_shift": float(robust_shift),
    }
