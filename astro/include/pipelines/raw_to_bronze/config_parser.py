class ConfigError(ValueError):
    pass


def parse_pipeline_config(raw: dict) -> dict:
    if "assets" not in raw:
        raise ConfigError("Missing required field: raw_to_bronze.assets")
    return raw
