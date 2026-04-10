import json
from pathlib import Path

import polars as pl
import pytest

from airflow.exceptions import AirflowFailException
from include.pipelines.raw_to_landing.reporting_service import log_run_summary
from include.pipelines.raw_to_landing.transform_service import stage_asset_batch


def _pipeline_config(tmp_path: Path) -> dict:
    return {
        "source_path": str(tmp_path / "raw"),
        "landing_path": str(tmp_path / "landing"),
        "quarantine_dir": str(tmp_path / "quarantine"),
        "assets": {
            "activities": {
                "enabled": True,
                "source_folder": "activities",
                "extract": {"payload_kind": "list"},
                "target_table": "activities",
                "column_mapping": [
                    {
                        "target": "activity_id",
                        "source": "activityId",
                        "dtype": "int64",
                        "required": True,
                    },
                    {
                        "target": "activity_type",
                        "source": "activityType.typeKey",
                        "dtype": "string",
                        "required": True,
                    },
                ],
            }
        },
    }


def test_raw_to_landing_service_flow_success(tmp_path: Path):
    config = _pipeline_config(tmp_path)
    run_date = "2026-03-18"
    source_dir = tmp_path / "raw" / "activities" / f"dt={run_date}"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "activities_1.json").write_text(
        json.dumps(
            [
                {"activityId": 1, "activityType": {"typeKey": "running"}},
                {"activityId": 2, "activityType": {"typeKey": "running"}},
            ]
        ),
        encoding="utf-8",
    )

    transform_result = stage_asset_batch(
        run_date=run_date, asset_name="activities", raw_config=config
    )
    summary = log_run_summary([transform_result])

    assert transform_result["rows_valid"] == 2
    assert summary["rows_valid"] == 2
    assert summary["staged_files"] == 1
    assert summary["rows_invalid"] == 0

    staged_df = pl.read_parquet(
        tmp_path / "landing" / "activities" / f"dt={run_date}" / "activities.parquet"
    )
    assert staged_df.height == 2


def test_raw_to_landing_service_flow_fails_quality_gate_on_invalid(tmp_path: Path):
    config = _pipeline_config(tmp_path)
    run_date = "2026-03-18"
    source_dir = tmp_path / "raw" / "activities" / f"dt={run_date}"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "activities_bad.json").write_text(
        json.dumps([{"activityId": 7, "activityType": {}}]),
        encoding="utf-8",
    )

    transform_result = stage_asset_batch(
        run_date=run_date, asset_name="activities", raw_config=config
    )

    assert transform_result["rows_invalid"] == 1

    with pytest.raises(AirflowFailException, match="invalid_rows=1"):
        log_run_summary([transform_result])
