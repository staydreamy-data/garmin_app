"""
# Raw To Landing Backfill DAG

Manual raw-to-landing pipeline for date-range backfills.

## Behavior
- Schedule: none (`schedule=None`)
- Triggered manually with Airflow params `start_date` and `end_date`
- Reuses the existing raw-to-landing transform service
- Processes all enabled assets for each date in the requested range

## Configuration
Pipeline settings are loaded from `include/config/pipelines_config.yaml`
using pipeline key `raw_to_landing`.

## Output
Validated parquet is written into landing partitions for each requested date
(`dt=<YYYY-MM-DD>`).
"""

from datetime import datetime as py_datetime, timedelta
from pathlib import Path

from airflow.sdk import Param, dag, task
from pendulum import datetime

from include.helpers.config import load_config
from include.pipelines.raw_to_landing.reporting_service import log_run_summary
from include.pipelines.raw_to_landing.transform_service import stage_asset_batch

PIPELINE_NAME = "raw_to_landing_backfill"


@dag(
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    doc_md=__doc__,
    max_active_runs=1,
    default_args={"retries": 0},
    params={
        "start_date": Param(
            None,
            type=["null", "string"],
            format="date",
            title="Start Date",
            description="Backfill start date in YYYY-MM-DD format.",
        ),
        "end_date": Param(
            None,
            type=["null", "string"],
            format="date",
            title="End Date",
            description="Backfill end date in YYYY-MM-DD format.",
        ),
    },
    tags=["garmin", "backfill"],
)
def raw_to_landing_backfill():
    @task
    def get_config():
        return load_config("raw_to_landing")

    @task
    def get_enabled_assets(config: dict) -> list:
        assets = config.get("assets", {})
        return [
            asset_name
            for asset_name, asset_config in assets.items()
            if asset_config.get("enabled", True)
        ]

    @task
    def build_run_dates(
        start_date: str | None = None,
        end_date: str | None = None,
        asset_names: list[str] | None = None,
        config: dict | None = None,
    ) -> list[str]:
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date params are required.")

        start = py_datetime.strptime(start_date, "%Y-%m-%d").date()
        end = py_datetime.strptime(end_date, "%Y-%m-%d").date()
        if start > end:
            raise ValueError("start_date must be less than or equal to end_date.")

        current = start
        run_dates: list[str] = []
        while current <= end:
            run_dates.append(current.isoformat())
            current += timedelta(days=1)

        requested_dates = set(run_dates)
        raw_config = config or {}
        assets = raw_config.get("assets", {})
        source_path = raw_config.get("source_path")
        if not source_path or not asset_names:
            return run_dates

        existing_dates: set[str] = set()
        for asset_name in asset_names:
            asset_config = assets.get(asset_name, {})
            source_folder = asset_config.get("source_folder")
            if not source_folder:
                continue

            asset_source_dir = Path(source_path) / source_folder
            for partition_dir in asset_source_dir.glob("dt=*"):
                if partition_dir.is_dir():
                    partition_date = partition_dir.name.removeprefix("dt=")
                    if partition_date in requested_dates:
                        existing_dates.add(partition_date)

        return sorted(existing_dates)

    @task
    def process_run_date(run_date: str, asset_names: list[str], config: dict) -> list[dict]:
        return [
            stage_asset_batch(run_date=run_date, asset_name=asset_name, raw_config=config)
            for asset_name in asset_names
        ]

    @task
    def summarize_run(transform_results_by_date: list[list[dict]] | None) -> dict:
        flattened_results = [
            result
            for daily_results in (transform_results_by_date or [])
            for result in (daily_results or [])
        ]
        return log_run_summary(flattened_results)

    config = get_config()
    asset_names = get_enabled_assets(config)
    run_dates = build_run_dates(
        "{{ params.start_date }}",
        "{{ params.end_date }}",
        asset_names,
        config,
    )

    transformed = process_run_date.partial(
        asset_names=asset_names, config=config
    ).expand(run_date=run_dates)

    summary = summarize_run(transformed)
    transformed >> summary


raw_to_landing_backfill()
