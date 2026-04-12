"""
# Garmin Ingest Backfill DAG

Manual Garmin ingestion pipeline for date-range backfills.

## Behavior
- Schedule: none (`schedule=None`)
- Triggered manually with Airflow params `start_date` and `end_date`
- Activities are fetched once for the full range and then written into daily partitions

## Configuration
Pipeline settings are loaded from `include/config/pipelines_config.yaml`
using pipeline key `garmin_ingest`.

Expected config fields:
- `storage_root`: base output directory.
- `activities_folder`: folder for raw activities payloads.
- `assets`: per-activity extraction config (for example `splits`, `activity_details`).

## Output
Raw activities and configured asset payloads are written as JSON files
partitioned by actual activity date (`dt=<YYYY-MM-DD>`).
"""

from airflow.sdk import Param, dag, task
from pendulum import datetime
from include.pipelines.ingest import ingest_garmin_activities_by_date_range
from include.helpers.config import load_config


PIPELINE_NAME = "garmin_ingest_backfill"
GARMIN_CONNECTION_ID = "garmin_default"


@dag(
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    doc_md=__doc__,
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
def garmin_ingest_backfill():
    @task
    def ingest_activities(start_date: str | None = None, end_date: str | None = None):
        """Load config and ingest Garmin activities plus configured assets for one date range."""

        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date params are required.")

        config = load_config("garmin_ingest")
        assets = config.get("assets", [])
        storage_root = config.get("storage_root")
        activities_folder = config.get("activities_folder")
        ingest_garmin_activities_by_date_range(
            GARMIN_CONNECTION_ID,
            start_date,
            end_date,
            storage_root,
            activities_folder,
            assets,
        )

    ingest_activities("{{ params.start_date }}", "{{ params.end_date }}")


garmin_ingest_backfill()
