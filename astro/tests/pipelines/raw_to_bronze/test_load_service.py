from pathlib import Path

import duckdb
import polars as pl
import pytest

from include.pipelines.raw_to_bronze.config_parser import ConfigError
from include.pipelines.raw_to_bronze.load_service import (
    _build_duckdb_columns,
    append_to_bronze,
)


def _base_config(tmp_path: Path) -> dict:
    return {
        "staging_path": str(tmp_path / "stage"),
        "duckdb_path": str(tmp_path / "duckdb" / "garmin.duckdb"),
        "assets": {
            "activities": {
                "source_folder": "activities",
                "extract": {"payload_kind": "list"},
                "target_table": "activities",
                "column_mapping": [
                    {"target": "activity_id", "dtype": "int64"},
                    {"target": "activity_type", "dtype": "string"},
                ],
            }
        },
    }


def test_build_duckdb_columns_includes_metadata():
    columns = _build_duckdb_columns(
        [
            {"target": "activity_id", "dtype": "int64"},
            {"target": "activity_type", "dtype": "string"},
        ]
    )

    assert columns == [
        ("activity_id", "BIGINT"),
        ("activity_type", "VARCHAR"),
        ("ingested_at", "TIMESTAMP"),
        ("ingestion_date", "DATE"),
        ("run_date", "DATE"),
        ("source_file", "VARCHAR"),
    ]


def test_append_to_bronze_returns_zero_when_no_staged_files(tmp_path: Path):
    config = _base_config(tmp_path)

    result = append_to_bronze(
        run_date="2026-03-18",
        asset_name="activities",
        raw_config=config,
    )

    assert result == {"asset": "activities", "files_found": 0, "rows_loaded": 0}


def test_append_to_bronze_appends_rows_from_stage_partition(tmp_path: Path):
    config = _base_config(tmp_path)
    run_date = "2026-03-18"

    stage_dir = tmp_path / "stage" / "activities" / f"dt={run_date}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "activity_id": [1001, 1002],
            "activity_type": ["running", "running"],
            "ingested_at": ["2026-03-18T10:00:00", "2026-03-18T10:00:00"],
            "ingestion_date": ["2026-03-18", "2026-03-18"],
            "run_date": ["2026-03-18", "2026-03-18"],
            "source_file": ["activities_1.json", "activities_1.json"],
        }
    )
    df.write_parquet(stage_dir / "activities_1.parquet")

    result = append_to_bronze(
        run_date=run_date, asset_name="activities", raw_config=config
    )
    assert result == {"asset": "activities", "files_found": 1, "rows_loaded": 2}

    with duckdb.connect(str(tmp_path / "duckdb" / "garmin.duckdb")) as con:
        row_count = con.execute(
            'SELECT COUNT(*) FROM "bronze"."activities"'
        ).fetchone()[0]
    assert row_count == 2


def test_append_to_bronze_raises_for_unknown_asset(tmp_path: Path):
    config = _base_config(tmp_path)

    with pytest.raises(
        ConfigError, match="Asset 'unknown' not found in raw_to_bronze.assets"
    ):
        append_to_bronze(
            run_date="2026-03-18",
            asset_name="unknown",
            raw_config=config,
        )
