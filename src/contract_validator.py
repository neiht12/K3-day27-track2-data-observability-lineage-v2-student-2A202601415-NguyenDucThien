"""Severity-aware validation for the YAML data contracts used by the lab."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
DEFAULT_ACTION = {"info": "observe", "warning": "warn", "critical": "block"}


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
    action: str | None = None,
) -> dict[str, Any]:
    severity = severity if severity in SEVERITY_ORDER else "warning"
    return {
        "check": check,
        "column": column,
        "severity": severity,
        "action": action or DEFAULT_ACTION[severity],
        "passed": bool(passed),
        "details": details,
    }


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        contract = yaml.safe_load(f)
    if not isinstance(contract, dict):
        raise ValueError("contract must be a YAML mapping")
    return contract


def _type_invalid_mask(series: pd.Series, declared_type: str) -> pd.Series:
    """Return invalid non-null values while allowing normal CSV serialization."""
    present = series.notna()
    kind = str(declared_type).strip().lower()
    if kind in {"integer", "int"}:
        numeric = pd.to_numeric(series, errors="coerce")
        return present & (numeric.isna() | ~np.isclose(numeric % 1, 0))
    if kind in {"number", "numeric", "float", "double"}:
        return present & pd.to_numeric(series, errors="coerce").isna()
    if kind in {"datetime", "timestamp", "date"}:
        parsed = pd.to_datetime(series, errors="coerce", utc=True)
        return present & parsed.isna()
    if kind in {"string", "str"}:
        return present & ~series.map(lambda value: isinstance(value, str))
    if kind in {"boolean", "bool"}:
        accepted = {True, False, 0, 1, "0", "1", "true", "false", "True", "False"}
        return present & ~series.isin(accepted)
    return present


def _freshness_reference(df: pd.DataFrame, freshness: dict[str, Any]) -> pd.Timestamp:
    reference_column = freshness.get("reference_column")
    if reference_column and reference_column in df.columns:
        parsed = pd.to_datetime(df[reference_column], errors="coerce", utc=True)
        if parsed.notna().any():
            return parsed.max()
    reference_time = freshness.get("reference_time")
    if reference_time is not None:
        parsed = pd.to_datetime(reference_time, errors="coerce", utc=True)
        if not pd.isna(parsed):
            return parsed
    return pd.Timestamp(datetime.now(timezone.utc))


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    issues: list[dict[str, Any]] = []
    columns = contract.get("columns") or contract.get("fields") or {}

    for column, raw_rules in columns.items():
        rules = raw_rules or {}
        severity = rules.get("severity", "warning")
        action = rules.get("action")
        required = bool(rules.get("required", False))

        if column not in df.columns:
            if required:
                issues.append(_issue(
                    "required_column", column=column, severity=severity, action=action,
                    passed=False, details=f"Missing required column: {column}",
                ))
            continue

        series = df[column]
        if required:
            null_count = int(series.isna().sum())
            issues.append(_issue(
                "not_null", column=column, severity=severity, action=action,
                passed=null_count == 0, details=f"null_count={null_count}",
            ))

        declared_type = rules.get("type")
        if declared_type:
            invalid_count = int(_type_invalid_mask(series, declared_type).sum())
            issues.append(_issue(
                "type", column=column, severity=severity, action=action,
                passed=invalid_count == 0,
                details=f"declared_type={declared_type}; invalid_count={invalid_count}",
            ))

        if rules.get("unique"):
            duplicate_count = int(series[series.notna()].duplicated(keep=False).sum())
            issues.append(_issue(
                "unique", column=column, severity=severity, action=action,
                passed=duplicate_count == 0, details=f"duplicate_rows={duplicate_count}",
            ))

        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_count = int((series.notna() & ~series.isin(accepted)).sum())
            issues.append(_issue(
                "accepted_values", column=column, severity=severity, action=action,
                passed=invalid_count == 0,
                details=f"invalid_count={invalid_count}; accepted={accepted}",
            ))

        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = series.notna() & numeric.isna()
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(_issue(
                "range", column=column, severity=severity, action=action,
                passed=invalid_count == 0, details=f"invalid_count={invalid_count}",
            ))

        if "min_length" in rules:
            lengths = series.dropna().astype(str).str.len()
            invalid_count = int((lengths < int(rules["min_length"])).sum())
            issues.append(_issue(
                "min_length", column=column, severity=severity, action=action,
                passed=invalid_count == 0,
                details=f"invalid_count={invalid_count}; min_length={rules['min_length']}",
            ))

    freshness = contract.get("freshness") or {}
    freshness_column = freshness.get("column")
    if freshness_column:
        severity = freshness.get("severity", "warning")
        action = freshness.get("action")
        max_delay = float(freshness.get("max_delay_minutes", 0))
        if freshness_column not in df.columns:
            issues.append(_issue(
                "freshness", column=freshness_column, severity=severity, action=action,
                passed=False, details=f"Missing freshness column: {freshness_column}",
            ))
        else:
            parsed = pd.to_datetime(df[freshness_column], errors="coerce", utc=True)
            valid = parsed.dropna()
            if valid.empty:
                issues.append(_issue(
                    "freshness", column=freshness_column, severity=severity, action=action,
                    passed=False, details="no_valid_timestamps",
                ))
            else:
                reference = _freshness_reference(df, freshness)
                delay = max(0.0, (reference - valid.max()).total_seconds() / 60.0)
                issues.append(_issue(
                    "freshness", column=freshness_column, severity=severity, action=action,
                    passed=delay <= max_delay,
                    details=f"delay_minutes={delay:.3f}; max_delay_minutes={max_delay:.3f}",
                ))

    return issues


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [issue for issue in issues if not issue.get("passed", False)]
    if min_severity is None:
        return failed
    if min_severity not in SEVERITY_ORDER:
        raise ValueError(f"Unknown severity: {min_severity}")
    threshold = SEVERITY_ORDER[min_severity]
    return [
        issue for issue in failed
        if SEVERITY_ORDER.get(issue.get("severity", "warning"), 1) >= threshold
    ]


def validation_action(issues: list[dict[str, Any]]) -> str:
    """Return the strongest operational action for failed validation checks."""
    actions = {issue.get("action", "warn") for issue in failed_issues(issues)}
    for action in ("block", "quarantine", "warn", "observe"):
        if action in actions:
            return action
    return "accept"
