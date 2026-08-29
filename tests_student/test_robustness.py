from datetime import datetime, timedelta, timezone

import pandas as pd

from observability.anomaly import detect_anomaly, mad_detector
from observability.distribution import detect_distribution_shift
from observability.lineage import get_column_downstream
from observability.rag_metrics import detect_embedding_norm_shift
from observability.slo import evaluate_multiwindow_burn
from src.contract_validator import validate_dataframe, validation_action


def test_contract_detects_type_drift_and_assigns_block_action():
    contract = {
        "columns": {
            "order_id": {"required": True, "type": "integer", "severity": "critical"},
            "amount": {"type": "number", "severity": "critical"},
        }
    }
    issues = validate_dataframe(pd.DataFrame({"order_id": [1.5], "amount": ["oops"]}), contract)
    failed = [issue for issue in issues if not issue["passed"]]
    assert {issue["column"] for issue in failed if issue["check"] == "type"} == {"order_id", "amount"}
    assert validation_action(issues) == "block"


def test_contract_detects_wall_clock_freshness():
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    contract = {
        "columns": {"updated_at": {"required": True, "type": "datetime"}},
        "freshness": {"column": "updated_at", "max_delay_minutes": 30, "severity": "warning"},
    }
    issues = validate_dataframe(pd.DataFrame({"updated_at": [old.isoformat()]}), contract)
    assert any(issue["check"] == "freshness" and not issue["passed"] for issue in issues)


def test_auto_mad_handles_outlier_and_detects_drop():
    history = [100, 101, 99, 100, 102, 98, 1000]
    assert detect_anomaly(100, history, method="auto")["is_anomaly"] is False
    assert detect_anomaly(20, history, method="auto")["is_anomaly"] is True


def test_zero_mad_detects_changed_value():
    assert mad_detector(11, [10, 10, 10, 10, 10])["is_anomaly"] is True


def test_distribution_detects_shape_shift_with_same_mean():
    baseline = [0] * 50 + [10] * 50
    current = [5] * 100
    assert detect_distribution_shift(current, baseline)["is_anomaly"] is True


def test_multiwindow_requires_sustained_burn():
    assert evaluate_multiwindow_burn(short_window_burn=20, long_window_burn=8)["page"] is True
    assert evaluate_multiwindow_burn(short_window_burn=20, long_window_burn=1)["page"] is False


def test_column_lineage_is_transitive_and_cycle_safe():
    graph = {"raw.a": ["stg.a"], "stg.a": ["mart.a"], "mart.a": ["stg.a", "dashboard.a"]}
    assert get_column_downstream(graph, "raw.a") == ["stg.a", "mart.a", "dashboard.a"]


def test_embedding_norm_distribution_shift():
    result = detect_embedding_norm_shift([2.0] * 20, [1.0] * 20)
    assert result["is_anomaly"] is True
    assert result["metric"] == "embedding_norm_distribution"
