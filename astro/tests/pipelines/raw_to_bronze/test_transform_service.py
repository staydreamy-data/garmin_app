import json
from pathlib import Path

import polars as pl
import pytest

from include.pipelines.raw_to_bronze.config_parser import ConfigError
from include.pipelines.raw_to_bronze.transform_service import (
    _get_nested,
    _map_raw_to_staged,
    _resolve_records,
    stage_asset_batch,
)


def _base_config(tmp_path: Path) -> dict:
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
            },
            "splits": {
                "enabled": True,
                "source_folder": "splits",
                "extract": {
                    "payload_kind": "object",
                    "records_path": "lapDTOs",
                    "context_key": {"source": "activityId", "target": "activity_id"},
                },
                "target_table": "splits",
                "column_mapping": [
                    {
                        "target": "message_index",
                        "source": "messageIndex",
                        "dtype": "int64",
                        "required": True,
                    }
                ],
            },
        },
    }


def test_resolve_records_for_list_payload():
    raw_data = [{"a": 1}, {"a": 2}]
    extract = {"payload_kind": "list"}

    records = _resolve_records(raw_data, extract)

    assert records == raw_data


def test_resolve_records_for_object_payload():
    raw_data = {"lapDTOs": [{"idx": 1}, {"idx": 2}]}
    extract = {"payload_kind": "object", "records_path": "lapDTOs"}

    records = _resolve_records(raw_data, extract)

    assert records == [{"idx": 1}, {"idx": 2}]


def test_resolve_records_for_descriptor_metrics_payload():
    raw_data = {
        "activityId": 123,
        "metricDescriptors": [
            {
                "metricsIndex": 0,
                "key": "directSpeed",
                "unit": {"key": "mps", "factor": 0.1},
            },
            {
                "metricsIndex": 1,
                "key": "directHeartRate",
                "unit": {"key": "bpm", "factor": 1.0},
            },
        ],
        "activityDetailMetrics": [
            {"metrics": [3.1, 150]},
            {"metrics": [3.2, 152]},
        ],
    }
    extract = {
        "payload_kind": "descriptor_metrics",
        "schema_path": "metricDescriptors",
        "schema_index_field": "metricsIndex",
        "schema_key_field": "key",
        "schema_unit_path": "unit",
        "records_path": "activityDetailMetrics",
        "values_path": "metrics",
    }

    records = _resolve_records(raw_data, extract)

    assert records == [
        {
            "measurement_index": 0,
            "metric_index": 0,
            "metric_key": "directSpeed",
            "metric_value": 3.1,
            "unit_key": "mps",
            "unit_factor": 0.1,
        },
        {
            "measurement_index": 0,
            "metric_index": 1,
            "metric_key": "directHeartRate",
            "metric_value": 150,
            "unit_key": "bpm",
            "unit_factor": 1.0,
        },
        {
            "measurement_index": 1,
            "metric_index": 0,
            "metric_key": "directSpeed",
            "metric_value": 3.2,
            "unit_key": "mps",
            "unit_factor": 0.1,
        },
        {
            "measurement_index": 1,
            "metric_index": 1,
            "metric_key": "directHeartRate",
            "metric_value": 152,
            "unit_key": "bpm",
            "unit_factor": 1.0,
        },
    ]


def test_resolve_records_raises_for_unsupported_payload_kind():
    with pytest.raises(ConfigError, match="Unsupported payload_kind: weird"):
        _resolve_records([], {"payload_kind": "weird"})


def test_get_nested_and_map_raw_to_staged():
    records = [
        {"activityId": 10, "activityType": {"typeKey": "running"}},
        {"activityId": 11, "activityType": {"typeKey": "cycling"}},
    ]
    mapping = [
        {"target": "activity_id", "source": "activityId"},
        {"target": "activity_type", "source": "activityType.typeKey"},
    ]

    assert _get_nested(records[0], "activityType.typeKey") == "running"
    assert _get_nested(records[0], "missing.path") is None
    assert _map_raw_to_staged(records, mapping) == [
        {"activity_id": 10, "activity_type": "running"},
        {"activity_id": 11, "activity_type": "cycling"},
    ]


def test_stage_asset_batch_success_writes_staged_parquet(tmp_path: Path):
    config = _base_config(tmp_path)
    run_date = "2026-03-18"

    source_dir = tmp_path / "raw" / "activities" / f"dt={run_date}"
    source_dir.mkdir(parents=True, exist_ok=True)
    payload = [
        {"activityId": 101, "activityType": {"typeKey": "running"}},
        {"activityId": 102, "activityType": {"typeKey": "running"}},
    ]
    (source_dir / "activities_1.json").write_text(json.dumps(payload), encoding="utf-8")

    result = stage_asset_batch(
        run_date=run_date, asset_name="activities", raw_config=config
    )

    assert result == {
        "asset": "activities",
        "files_seen": 1,
        "rows_valid": 2,
        "rows_invalid": 0,
        "staged_files": 1,
    }

    staged_file = (
        tmp_path / "stage" / "activities" / f"dt={run_date}" / "activities_1.parquet"
    )
    assert staged_file.exists()
    staged_df = pl.read_parquet(staged_file)
    assert staged_df.height == 2
    assert {"ingested_at", "ingestion_date", "run_date", "source_file"}.issubset(
        set(staged_df.columns)
    )
    assert not (tmp_path / "quarantine" / "activities" / f"dt={run_date}").exists()


def test_stage_asset_batch_validation_failure_goes_to_quarantine(tmp_path: Path):
    config = _base_config(tmp_path)
    run_date = "2026-03-18"

    source_dir = tmp_path / "raw" / "activities" / f"dt={run_date}"
    source_dir.mkdir(parents=True, exist_ok=True)
    payload = [{"activityId": 201, "activityType": {}}]
    (source_dir / "activities_bad.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    result = stage_asset_batch(
        run_date=run_date, asset_name="activities", raw_config=config
    )

    assert result == {
        "asset": "activities",
        "files_seen": 1,
        "rows_valid": 0,
        "rows_invalid": 1,
        "staged_files": 0,
    }

    quarantine_file = (
        tmp_path
        / "quarantine"
        / "activities"
        / f"dt={run_date}"
        / "activities_bad.parquet"
    )
    assert quarantine_file.exists()


def test_stage_asset_batch_context_key_injection(tmp_path: Path):
    config = _base_config(tmp_path)
    run_date = "2026-03-18"

    source_dir = tmp_path / "raw" / "splits" / f"dt={run_date}"
    source_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "activityId": 3001,
        "lapDTOs": [{"messageIndex": 0}, {"messageIndex": 1}],
    }
    (source_dir / "splits_1.json").write_text(json.dumps(payload), encoding="utf-8")

    result = stage_asset_batch(
        run_date=run_date, asset_name="splits", raw_config=config
    )

    assert result["rows_valid"] == 2
    staged_file = tmp_path / "stage" / "splits" / f"dt={run_date}" / "splits_1.parquet"
    staged_df = pl.read_parquet(staged_file)
    assert staged_df["activity_id"].to_list() == [3001, 3001]
