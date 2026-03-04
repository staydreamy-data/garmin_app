"""
# Garmin Ingest DAG

"""

from airflow.sdk import dag, task
from pendulum import datetime
from include.pipelines.ingest import ingest_garmin_activities_by_date
from include.helpers.config import load_config
from include.pipelines.write_to_stage import process_entity_to_stage

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

    @task
    def get_config():
        config = load_config(PIPELINE_NAME)
        return config

    @task
    def activities_to_parquet(run_date: str, config: dict):
        process_entity_to_stage(run_date, config, entity="activities")
        # TODO: Read raw activities JSON for run_date -> transform/select columns -> validate -> write staged parquet.
        pass

    @task
    def splits_to_parquet(run_date: str, config: dict):
        # TODO: Read raw splits JSON for run_date -> transform/select columns -> validate -> write staged parquet.
        pass

    @task
    def heartrate_to_parquet(run_date: str, config: dict):
        # TODO: Read raw heartrate JSON for run_date -> transform/select columns -> validate -> write staged parquet.
        pass

    @task
    def merge_to_duckdb():
        # TODO: Read staged parquet files for run_date -> merge into DuckDB.
        pass

    @task
    def cleanup_staged_parquet():
        # TODO: Remove short-lived staged parquet files after successful merge.
        pass

    config = get_config()

    activities_task = activities_to_parquet("{{ ds }}", config)
    splits_task = splits_to_parquet("{{ ds }}", config)
    heartrate_task = heartrate_to_parquet("{{ ds }}", config)

    merge_to_duckdb_task = merge_to_duckdb()
    cleanup_staged_parquet_task = cleanup_staged_parquet()

    config >> [activities_task, splits_task, heartrate_task] >> merge_to_duckdb_task >> cleanup_staged_parquet_task

raw_to_bronze()
