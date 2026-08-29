from __future__ import annotations

import math
from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not math.isfinite(target) or not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if isinstance(bad_events, bool) or isinstance(total_events, bool):
        raise ValueError("event counts must be integers")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target, "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate, "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0, "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - burn_rate),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *, short_window_burn: float, long_window_burn: float, policy: str = "sre"
) -> dict[str, Any]:
    """Apply paired-window burn thresholds so transient spikes do not page."""
    short = float(short_window_burn)
    long = float(long_window_burn)
    if not math.isfinite(short) or not math.isfinite(long) or short < 0 or long < 0:
        raise ValueError("burn rates must be finite and non-negative")

    if short >= 14.4 and long >= 6.0:
        page, severity, tier = True, "critical", "fast_burn"
    elif short >= 6.0 and long >= 3.0:
        page, severity, tier = True, "warning", "sustained_burn"
    elif short >= 6.0:
        page, severity, tier = False, "warning", "transient_short_window_spike"
    else:
        page, severity, tier = False, "info", "within_policy"
    return {
        "page": page,
        "severity": severity,
        "reason": tier,
        "policy": policy,
        "short_window_burn": short,
        "long_window_burn": long,
    }
