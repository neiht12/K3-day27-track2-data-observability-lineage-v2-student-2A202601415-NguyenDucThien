#!/usr/bin/env python3
"""Reusable GX suite/checkpoint plus severity-aware operational actions."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP_ROOT = ROOT / ".tmp"
TEMP_ROOT.mkdir(exist_ok=True)
tempfile.tempdir = str(TEMP_ROOT)

try:
    import great_expectations as gx
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def build_checkpoint(context: object, batch_definition: object) -> object:
    """Build named GX objects so validation can be reused and audited."""
    suite = gx.ExpectationSuite(name="orders_contract_suite")
    suite = context.suites.add(suite)
    expectations = [
        gx.expectations.ExpectColumnToExist(column="order_id", severity="critical"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id", severity="critical"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="order_id", severity="critical"),
        gx.expectations.ExpectColumnValuesToBeOfType(column="order_id", type_="int64", severity="critical"),
        gx.expectations.ExpectColumnValuesToBeBetween(column="amount", min_value=0, severity="critical"),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="currency", value_set=["USD", "VND"], severity="critical"
        ),
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status",
            value_set=["pending", "completed", "refunded", "cancelled"],
            severity="warning",
        ),
    ]
    for expectation in expectations:
        suite.add_expectation(expectation)

    validation = gx.ValidationDefinition(
        name="orders_validation_definition", data=batch_definition, suite=suite
    )
    validation = context.validation_definitions.add(validation)
    checkpoint = gx.Checkpoint(
        name="orders_contract_checkpoint", validation_definitions=[validation]
    )
    return context.checkpoints.add(checkpoint)


def operational_action(success: bool, source: Path) -> dict[str, str | bool | None]:
    """Block and quarantine failed batches; accept successful batches."""
    if success:
        return {"success": True, "action": "accept", "quarantine_path": None}
    destination_dir = ROOT / "data" / "quarantine"
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_dir / f"orders_{stamp}.csv"
    shutil.copy2(source, destination)
    return {
        "success": False,
        "action": "block_and_quarantine",
        "quarantine_path": str(destination.relative_to(ROOT)),
    }


def main() -> None:
    source = ROOT / "data" / "incoming" / "orders.csv"
    dataframe = pd.read_csv(source)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas("orders_pandas")
    asset = data_source.add_dataframe_asset(name="orders_dataframe")
    batch_definition = asset.add_batch_definition_whole_dataframe("whole_orders")
    checkpoint = build_checkpoint(context, batch_definition)
    result = checkpoint.run(batch_parameters={"dataframe": dataframe})
    action = operational_action(bool(result.success), source)

    report = {
        "checkpoint": "orders_contract_checkpoint",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        **action,
    }
    report_path = ROOT / "reports" / "gx_latest.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
