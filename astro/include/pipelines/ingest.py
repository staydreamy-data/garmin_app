import logging
from pathlib import Path
from datetime import datetime
from garminconnect import Garmin
import json
from airflow.hooks.base import BaseHook

METHOD_REGISTRY: dict[str, str] = {
    "heartrate": "get_activity_hr_in_timezones",
    "splits": "get_activity_splits",
}


def ingest_garmin_activities_by_date(
    activity_date: str, storage_root: str, activities_folder: str, method_tasks: list
):

    try:
        conn = BaseHook.get_connection("garmin_default")
        username = conn.login
        password = conn.password

        client = Garmin(username, password)

        client.login()
    except Exception as e:
        raise Exception(f"Failed to login to Garmin Connect: {e}")

    full_location_path = f"{storage_root}/{activities_folder}/dt={activity_date}"
    ingestion_time = datetime.now().isoformat()
    logging.info(
        f"Ingesting all the activities for date: {activity_date} at location: {full_location_path}"
    )

    Path(full_location_path).mkdir(parents=True, exist_ok=True)

    activities = client.get_activities_by_date((activity_date))

    logging.info(f"Retrieved {len(activities)} activities for date: {activity_date}")

    with open(f"{full_location_path}/activities_{ingestion_time}.json", "w") as f:
        json.dump(activities, f, indent=4)

    for activity in activities:
        activity_id = activity.get("activityId")
        for method_task in method_tasks:
            enabled = method_task.get("enabled")
            if not enabled:
                logging.info(
                    f"Skipping {method_task['key']} for activity {activity_id} as it is disabled in the config."
                )
                continue

            method_key = method_task["key"]
            output_folder = method_task["output_folder"]
            overwrite = method_task["overwrite"]
            output_path = f"{storage_root}/{output_folder}/dt={activity_date}"
            Path(output_path).mkdir(parents=True, exist_ok=True)
            output_file = f"{output_path}/{method_key}_{activity_id}.json"

            if not overwrite and Path(output_file).exists():
                logging.info(
                    f"Skipping {method_key} for activity {activity_id} as output already exists and overwrite is False."
                )
                continue

            method_name = METHOD_REGISTRY.get(method_key)
            if not method_name:
                logging.warning(
                    f"No Garmin method found for key: {method_key}. Skipping."
                )
                continue

            method = getattr(client, method_name, None)
            result = method(activity_id)

            with open(output_file, "w") as f:
                json.dump(result, f, indent=4)

            logging.info(
                f"Ingested {method_key} for activity {activity_id} and saved to {output_file}"
            )

    logging.info(
        f"Finished ingesting {len(activities)} activities for date: {activity_date} at location: {full_location_path}"
    )
