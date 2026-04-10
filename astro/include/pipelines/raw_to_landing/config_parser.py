class ConfigError(ValueError):
    pass


def _validate_extract(asset_name: str, extract: dict):
    payload_kind = extract.get("payload_kind")
    supported_kinds = {"list", "object", "descriptor_metrics"}
    if payload_kind not in supported_kinds:
        raise ConfigError(f"{asset_name}: unsupported payload_kind '{payload_kind}'")

    if payload_kind == "object" and not extract.get("records_path"):
        raise ConfigError(f"{asset_name}: object payload requires extract.records_path")

    if payload_kind == "descriptor_metrics":
        required_fields = [
            "schema_path",
            "schema_index_field",
            "schema_key_field",
            "records_path",
            "values_path",
        ]
        missing_fields = [field for field in required_fields if not extract.get(field)]
        if missing_fields:
            raise ConfigError(
                f"{asset_name}: descriptor_metrics missing extract fields: "
                f"{missing_fields}"
            )


def parse_pipeline_config(raw: dict) -> dict:
    assets = raw.get("assets")
    if not isinstance(assets, dict):
        raise ConfigError("Missing required field: raw_to_landing.assets")

    for asset_name, asset_config in assets.items():
        if not isinstance(asset_config, dict):
            raise ConfigError(f"{asset_name}: asset config must be an object")
        if not asset_config.get("enabled", True):
            continue

        required_asset_fields = [
            "source_folder",
            "extract",
            "target_table",
            "column_mapping",
        ]
        for field in required_asset_fields:
            if field not in asset_config:
                raise ConfigError(f"{asset_name}: missing required field '{field}'")

        column_mapping = asset_config["column_mapping"]
        if not isinstance(column_mapping, list) or not column_mapping:
            raise ConfigError(f"{asset_name}: column_mapping must be a non-empty list")

        extract = asset_config["extract"]
        if not isinstance(extract, dict):
            raise ConfigError(f"{asset_name}: extract config must be an object")
        _validate_extract(asset_name, extract)

    return raw
