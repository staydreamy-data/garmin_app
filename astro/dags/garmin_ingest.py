"""Minimal Garmin ingest DAG that prints the templated run date. Test"""
from airflow.sdk import dag, task
from pendulum import datetime
from include.pipelines.ingest import ingest_garmin_activities_by_date
from include.helpers.config import load_config



PIPELINE_NAME = "garmin_ingest"
STORAGE_LOCATION = "include/data/raw/garmin"
ACTIVITIES_FOLDER = "activities"

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

        config = load_config("garmin_ingest")
        garmin_methods = config.get("method_tasks", [])
        ingest_garmin_activities_by_date(run_date, STORAGE_LOCATION, ACTIVITIES_FOLDER, garmin_methods)

    ingest_activities("{{ ds }}")


garmin_ingest()
