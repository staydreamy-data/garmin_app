import json
from pathlib import Path

import duckdb
import pytest

from airflow.exceptions import AirflowFailException
from include.pipelines.raw_to_bronze.cleanup_service import cleanup_stage_batch
from include.pipelines.raw_to_bronze.load_service import append_to_bronze
from include.pipelines.raw_to_bronze.reporting_service import log_run_summary
from include.pipelines.raw_to_bronze.transform_service import stage_asset_batch


def _pipeline_config(tmp_path: Path) -> dict:
    return {
        "source_path": str(tmp_path / "raw"),
        "staging_path": str(tmp_path / "stage"),
        "quarantine_dir": str(tmp_path / "quarantine"),
        "duckdb_path": str(tmp_path / "duckdb" / "garmin.duckdb"),
        "assets": {
            "activities": {
                "enabled": True,
                "source_folder": "activities",
                "extract": {"payload_kind": "list"},
                "target": {"target_table": "activities"},
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


def test_raw_to_bronze_service_flow_success(tmp_path: Path):
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
    load_result = append_to_bronze(
        run_date=run_date, asset_name="activities", raw_config=config
    )
    cleanup_result = cleanup_stage_batch(
        run_date=run_date,
        asset_names=["activities"],
        raw_config=config,
    )
    summary = log_run_summary([transform_result], [load_result], cleanup_result)

    assert transform_result["rows_valid"] == 2
    assert load_result["rows_loaded"] == 2
    assert summary["rows_valid"] == 2
    assert summary["rows_loaded"] == 2
    assert summary["rows_invalid"] == 0

    with duckdb.connect(str(tmp_path / "duckdb" / "garmin.duckdb")) as con:
        row_count = con.execute(
            'SELECT COUNT(*) FROM "bronze"."activities"'
        ).fetchone()[0]
    assert row_count == 2

    assert not (tmp_path / "stage" / "activities" / f"dt={run_date}").exists()


def test_raw_to_bronze_service_flow_fails_quality_gate_on_invalid(tmp_path: Path):
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
    load_result = append_to_bronze(
        run_date=run_date, asset_name="activities", raw_config=config
    )
    cleanup_result = cleanup_stage_batch(
        run_date=run_date,
        asset_names=["activities"],
        raw_config=config,
    )

    assert transform_result["rows_invalid"] == 1
    assert load_result["rows_loaded"] == 0

    with pytest.raises(AirflowFailException, match="invalid_rows=1"):
        log_run_summary([transform_result], [load_result], cleanup_result)
