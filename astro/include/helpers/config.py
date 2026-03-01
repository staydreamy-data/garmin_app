import yaml
import logging
from include.constants import CONFIG_PATH
from pathlib import Path


def load_config(pipeline_name: str) -> dict:
    logging.info(f"Reading configuration for pipeline: {pipeline_name}")

    path = Path(CONFIG_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    pipelines = raw.get("pipelines", {})
    if pipeline_name not in pipelines:
        raise ValueError(f"Pipeline '{pipeline_name}' not found in config.")

    pipeline_config = pipelines[pipeline_name]
    return pipeline_config
