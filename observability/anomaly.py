"""Small, dependency-light anomaly detectors for operational metrics."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite_values(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return array[np.isfinite(array)]


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = _finite_values(history)
    current = float(current)
    if not np.isfinite(current):
        return {"is_anomaly": True, "score": float("inf"), "method": "zscore", "reason": "current_not_finite"}
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std <= np.finfo(float).eps:
        score = 0.0 if np.isclose(current, mean) else float("inf")
    else:
        score = abs(current - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    values = _finite_values(history)
    current = float(current)
    if not np.isfinite(current):
        return {"is_anomaly": True, "score": float("inf"), "method": "mad", "reason": "current_not_finite"}
    if values.size < 5:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad <= np.finfo(float).eps:
        fallback_scale = max(abs(median) * 0.01, 1e-9)
        score = abs(current - median) / fallback_scale
    else:
        score = 0.6745 * abs(current - median) / mad
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "mad":
        return mad_detector(current, history, threshold=max(threshold, 3.5))
    if method != "auto":
        raise ValueError(f"Unsupported method: {method}")

    full_history = list(history)
    segmented = context.get("same_segment_history")
    segmented_history = list(segmented) if segmented is not None else []
    use_segment = len(_finite_values(segmented_history)) >= 3
    candidate_history = segmented_history if use_segment else full_history
    if len(_finite_values(candidate_history)) >= 5:
        result = mad_detector(current, candidate_history, threshold=max(threshold, 3.5))
        result["method"] = "auto:mad_segment" if use_segment else "auto:mad"
    else:
        result = zscore_detector(current, candidate_history, threshold=threshold)
        result["method"] = "auto:zscore"

    if context.get("known_event"):
        result["is_anomaly"] = False
        result["reason"] += f"; suppressed_known_event={context['known_event']}"
    if context.get("day_of_week") is not None:
        result["reason"] += f"; day_of_week={context['day_of_week']}"
    return result
