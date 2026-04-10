"""
# Garmin Ingest DAG

"""

from airflow.sdk import dag, task
from pendulum import datetime
from include.helpers.config import load_config
from include.pipelines.raw_to_landing.transform_service import stage_asset_batch
from include.pipelines.raw_to_landing.reporting_service import log_run_summary

PIPELINE_NAME = "raw_to_landing"


@dag(
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    doc_md=__doc__,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["garmin"],
)
def raw_to_landing():
    # TODO(raw_to_landing roadmap):
    # 1) Keep get_config as the single config loader and pass config to downstream tasks via XCom.
    # 2) Add per-entity config fields in pipelines_config.yaml: primary_key, update_ts, required_columns, paths.
    # 3) Implement parallel transform tasks (activities/splits/heartrate) to read raw JSON and write staged parquet.
    # 4) In each transform, add lineage fields: raw_file, processed_at, run_id, record_hash.
    # 5) Validate with Polars + Pandera (required core schema, allow extra columns for drift tolerance).
    # 6) Add invalid-record handling (quarantine table/file + row-level validation metrics).
    # 7) Keep staged parquet as the durable handoff layer for dbt/DuckDB models.
    # 8) Add tests for DAG topology, validation behavior, and deterministic reruns.
    # 9) add dictionary load get_devices() (init.py) get_device_settings(device_id) (init.py)

    @task
    def get_config():
        return load_config(PIPELINE_NAME)

    @task
    def get_enabled_assets(config: dict) -> list:
        assets = config.get("assets", {})
        return [
            asset_name
            for asset_name, asset_config in assets.items()
            if asset_config.get("enabled", True)
        ]

    @task
    def transform_asset(run_date: str, asset_name: str, config: dict) -> dict:
        return stage_asset_batch(
            run_date=run_date, asset_name=asset_name, raw_config=config
        )

    @task
    def summarize_run(transform_results: list[dict]) -> dict:
        return log_run_summary(transform_results)

    config = get_config()

    asset_names = get_enabled_assets(config)
    transformed = transform_asset.partial(run_date="{{ ds }}", config=config).expand(
        asset_name=asset_names
    )

    summary = summarize_run(transformed)
    transformed >> summary


raw_to_landing()
