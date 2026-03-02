"""
# Garmin Ingest DAG

Daily Garmin ingestion pipeline with backfill support.

## Behavior
- Schedule: `@daily`
- Catchup: enabled (`catchup=True`) so historical runs/backfills are supported.
- Logical date: Airflow `{{ ds }}` is passed to the pipeline as the activity date.

## Configuration
Pipeline settings are loaded from `include/config/pipelines_config.yaml`
using pipeline key `garmin_ingest`.

Expected config fields:
- `storage_root`: base output directory.
- `activities_folder`: folder for raw activities payloads.
- `assets`: per-activity extraction config (for example `heartrate`, `splits`).

## Output
Raw activities and configured asset payloads are written as JSON files
partitioned by date (`dt=<YYYY-MM-DD>`).
"""

from airflow.sdk import dag, task
from pendulum import datetime
from include.pipelines.ingest import ingest_garmin_activities_by_date
from include.helpers.config import load_config


PIPELINE_NAME = "garmin_ingest"


@dag(
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=True,
    doc_md=__doc__,
    default_args={"retries": 0},
    tags=["garmin"],
)
def garmin_ingest():
    @task
    def ingest_activities(run_date: str):
        """Load config and ingest Garmin activities plus configured assets for one logical date."""

        config = load_config("garmin_ingest")
        assets = config.get("assets", [])
        storage_root = config.get("storage_root")
        activities_folder = config.get("activities_folder")
        ingest_garmin_activities_by_date(
            run_date, storage_root, activities_folder, assets
        )

    ingest_activities("{{ ds }}")


garmin_ingest()
