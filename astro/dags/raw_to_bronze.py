"""
# Garmin Ingest DAG

"""

from airflow.sdk import dag, task
from pendulum import datetime
from include.helpers.config import load_config
from include.pipelines.write_to_stage import process_entity_to_stage, duckdb_append_files_to_table
from include.pipelines.raw_to_bronze.transform_service import stage_asset_batch

PIPELINE_NAME = "raw_to_bronze"


@dag(
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    doc_md=__doc__,
    max_active_runs=1,
    default_args={"retries": 0},
    tags=["garmin"],
)
def raw_to_bronze():
    # TODO(raw_to_bronze roadmap):
    # 1) Keep get_config as the single config loader and pass config to downstream tasks via XCom.
    # 2) Add per-entity config fields in pipelines_config.yaml: primary_key, update_ts, required_columns, paths.
    # 3) Implement parallel transform tasks (activities/splits/heartrate) to read raw JSON and write staged parquet.
    # 4) In each transform, add lineage fields: raw_file, processed_at, run_id, record_hash.
    # 5) Validate with Polars + Pandera (required core schema, allow extra columns for drift tolerance).
    # 6) Add invalid-record handling (quarantine table/file + row-level validation metrics).
    # 7) Add one downstream merge task that serially writes to a shared DuckDB file using MERGE.
    # 8) Use key + update_ts merge semantics so Bronze stays unique/current and idempotent.
    # 9) Add cleanup task to remove short-lived staged parquet after successful merge.
    # 10) Add tests for DAG topology, validation behavior, and merge idempotency.
    # 11) add dictionary load get_devices() (init.py) get_device_settings(device_id) (init.py)

    @task
    def get_config():
        return load_config(PIPELINE_NAME)

    @task
    def get_enabled_assets(config: dict) -> list:
        assets = config.get("assets", {})
        return [asset_name for asset_name, asset_config in assets.items() if asset_config.get("enabled", True)]

    @task
    def transform_asset(run_date: str, asset_name: str, config: dict) -> dict:
        return stage_asset_batch(run_date=run_date, asset_name=asset_name, raw_config=config)


    @task
    def activities_to_parquet(run_date: str, config: dict):
        return stage_asset_batch(run_date=run_date, asset_name="activities", raw_config=config)

    # @task
    # def splits_to_parquet(run_date: str, config: dict):
    #     process_entity_to_stage(run_date, config, entity="splits")

    # @task
    # def activity_details_to_parquet(run_date: str, config: dict):
    #     # TODO: Read raw heartrate JSON for run_date -> transform/select columns -> validate -> write staged parquet.
    #     pass

    @task
    def merge_to_duckdb(run_date: str, config: dict):
        duckdb_path = config["duckdb_path"]
        schema_name = "bronze"

        for asset_name in config["assets"].keys():
            column_mapping = config["assets"][asset_name]["column_mapping"]
            parquet_files_path = f"{config["staging_path"]}/{asset_name}/dt={run_date}"
            duckdb_append_files_to_table(duckdb_path=duckdb_path, schema_name=schema_name, 
                                     table_name=asset_name, parquet_files_path=parquet_files_path,
                                     column_mapping=column_mapping)


    @task
    def cleanup_staged_parquet():
        # TODO: Remove short-lived staged parquet files after successful merge.
        pass

    config = get_config()

    activities_task = activities_to_parquet("{{ ds }}", config)
    # splits_task = splits_to_parquet("{{ ds }}", config)
    # activity_details_task = activity_details_to_parquet("{{ ds }}", config)

    asset_names = get_enabled_assets(config)
    # transform_asset.partial(run_date="{{ ds }}", config=config).expand(asset_name=asset_names)

    # merge_to_duckdb_task = merge_to_duckdb("{{ ds }}", config)
    # cleanup_staged_parquet_task = cleanup_staged_parquet()

    # config >> [transform_asset] >> merge_to_duckdb_task >> cleanup_staged_parquet_task

raw_to_bronze()
