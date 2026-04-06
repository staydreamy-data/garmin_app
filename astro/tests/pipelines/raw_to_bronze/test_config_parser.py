import pytest

from include.pipelines.raw_to_bronze.config_parser import (
    ConfigError,
    parse_pipeline_config,
)


def test_parse_pipeline_config_returns_raw_config_when_assets_exist():
    raw = {
        "assets": {
            "activities": {
                "enabled": True,
                "source_folder": "activities",
                "extract": {"payload_kind": "list"},
                "target_table": "activities",
                "column_mapping": [
                    {"target": "activity_id", "source": "activityId", "dtype": "int64"}
                ],
            }
        }
    }

    parsed = parse_pipeline_config(raw)

    assert parsed is raw


def test_parse_pipeline_config_raises_on_missing_assets():
    with pytest.raises(
        ConfigError, match="Missing required field: raw_to_bronze.assets"
    ):
        parse_pipeline_config({"staging_path": "include/data/stage/raw_to_bronze"})


def test_parse_pipeline_config_raises_on_missing_target_table():
    raw = {
        "assets": {
            "activities": {
                "enabled": True,
                "source_folder": "activities",
                "extract": {"payload_kind": "list"},
                "column_mapping": [
                    {"target": "activity_id", "source": "activityId", "dtype": "int64"}
                ],
            }
        }
    }

    with pytest.raises(ConfigError, match="activities: missing required field 'target_table'"):
        parse_pipeline_config(raw)


def test_parse_pipeline_config_accepts_descriptor_metrics():
    raw = {
        "assets": {
            "activity_details": {
                "enabled": True,
                "source_folder": "activity_details",
                "extract": {
                    "payload_kind": "descriptor_metrics",
                    "schema_path": "metricDescriptors",
                    "schema_index_field": "metricsIndex",
                    "schema_key_field": "key",
                    "records_path": "activityDetailMetrics",
                    "values_path": "metrics",
                },
                "target_table": "activity_details",
                "column_mapping": [
                    {
                        "target": "metric_value",
                        "source": "metric_value",
                        "dtype": "float64",
                    }
                ],
            }
        }
    }

    assert parse_pipeline_config(raw) is raw


def test_parse_pipeline_config_rejects_descriptor_metrics_with_missing_fields():
    raw = {
        "assets": {
            "activity_details": {
                "enabled": True,
                "source_folder": "activity_details",
                "extract": {
                    "payload_kind": "descriptor_metrics",
                    "schema_path": "metricDescriptors",
                    "schema_index_field": "metricsIndex",
                    "records_path": "activityDetailMetrics",
                },
                "target_table": "activity_details",
                "column_mapping": [
                    {
                        "target": "metric_value",
                        "source": "metric_value",
                        "dtype": "float64",
                    }
                ],
            }
        }
    }

    with pytest.raises(
        ConfigError, match="activity_details: descriptor_metrics missing extract fields"
    ):
        parse_pipeline_config(raw)
