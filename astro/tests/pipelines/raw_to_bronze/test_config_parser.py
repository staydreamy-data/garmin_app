import pytest

from include.pipelines.raw_to_bronze.config_parser import ConfigError, parse_pipeline_config


def test_parse_pipeline_config_returns_raw_config_when_assets_exist():
    raw = {"assets": {"activities": {"enabled": True}}}

    parsed = parse_pipeline_config(raw)

    assert parsed is raw


def test_parse_pipeline_config_raises_on_missing_assets():
    with pytest.raises(
        ConfigError, match="Missing required field: raw_to_bronze.assets"
    ):
        parse_pipeline_config({"staging_path": "include/data/stage/raw_to_bronze"})
