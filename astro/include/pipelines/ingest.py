import logging
from pathlib import Path
from datetime import datetime
from garminconnect import Garmin
import os
import json
from airflow.hooks.base import BaseHook

def ingest_garmin_activities_by_date(activity_date: str, storage_location: str, activities_folder: str):
    
    try:
        conn = BaseHook.get_connection("garmin_default")
        username = conn.login
        logging.info(f"Retrieved Garmin Connect credentials for user: {username}")
        password = conn.password

        client = Garmin(
            username,
            password
        )

        client.login()
    except Exception as e:
        raise Exception(f"Failed to login to Garmin Connect: {e}")

    full_location_path = f"{storage_location}/{activities_folder}/dt={activity_date}"
    ingestion_time = datetime.now().isoformat()
    logging.info(f"Ingesting all the activities for date: {activity_date} at location: {full_location_path}")

    Path(full_location_path).mkdir(parents=True, exist_ok=True)

    activities = client.get_activities_by_date((activity_date))

    with open(f"{full_location_path}/activities_{ingestion_time}.json", "w") as f:
        json.dump(activities, f, indent=4)
    logging.info(f"Finished ingesting {len(activities)} activities for date: {activity_date} at location: {full_location_path}")
