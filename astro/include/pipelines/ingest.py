import logging
from pathlib import Path
from datetime import datetime
from garminconnect import Garmin
import json
from airflow.hooks.base import BaseHook

METHOD_REGISTRY: dict[str, str] = {
    "splits": "get_activity_splits",
    "activity_details": "get_activity_details",
}


def get_garmin_client(conn_id):
    """
    Build and authenticate a Garmin client from an Airflow connection.

    Args:
        conn_id: Airflow connection id that contains Garmin login/password.

    Returns:
        An authenticated ``garminconnect.Garmin`` client.

    Raises:
        RuntimeError: If the Airflow connection is missing/invalid or login fails.
    """
    try:
        conn = BaseHook.get_connection(conn_id)
        username = conn.login
        password = conn.password

        client = Garmin(username, password)
        client.login()
        return client
    except Exception as e:
        raise RuntimeError("Failed to login to Garmin Connect") from e


def ingest_garmin_activities_by_date(
    conn_id, activity_date: str, storage_root: str, activities_folder: str, assets: list
):
    """
    Ingest Garmin activities for a date and collect configured per-activity assets.

    Flow:
        1. Login once using ``conn_id``.
        2. Download all activities for ``activity_date``.
        3. Save raw activities under ``{storage_root}/{activities_folder}/dt=<date>``.
        4. For each activity, run enabled asset methods from ``assets`` and persist JSON output.

    Args:
        conn_id: Airflow connection id containing Garmin credentials.
        activity_date: Logical date (usually Airflow ``{{ ds }}``) used for backfill partitioning.
        storage_root: Base directory for output files.
        activities_folder: Folder name for raw activities payloads.
        assets: List of asset configs. Expected keys per asset:
            ``key``, ``enabled``, ``output_folder``, ``overwrite``.
    """

    client = get_garmin_client(conn_id)

    full_location_path = f"{storage_root}/{activities_folder}/dt={activity_date}"
    ingestion_time = datetime.now().isoformat()
    logging.info(
        f"Ingesting all the activities for date: {activity_date} at location: {full_location_path}"
    )

    Path(full_location_path).mkdir(parents=True, exist_ok=True)

    activities = client.get_activities_by_date((activity_date))

    if not activities:
        logging.info(f"No activities found for date: {activity_date}")
        return

    logging.info(f"Retrieved {len(activities)} activities for date: {activity_date}")
    

    with open(f"{full_location_path}/activities_{ingestion_time}.json", "w") as f:
        json.dump(activities, f, indent=4)

    for activity in activities:
        activity_id = activity.get("activityId")
        for asset in assets:
            enabled = asset.get("enabled")
            if not enabled:
                logging.info(
                    f"Skipping {asset['key']} for activity {activity_id} as it is disabled in the config."
                )
                continue

            method_key = asset["key"]
            output_folder = asset["output_folder"]
            overwrite = asset["overwrite"]
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
            if method_name == "get_heart_rates":
                result = method(activity_date)
            else:
                result = method(activity_id)

            if not result:
                logging.info(
                    f"No data returned for {method_key} of activity {activity_id}. Skipping."
                )
                continue

            with open(output_file, "w") as f:
                json.dump(result, f, indent=4)

            logging.info(
                f"Ingested {method_key} for activity {activity_id} and saved to {output_file}"
            )

    logging.info(
        f"Finished ingesting {len(activities)} activities for date: {activity_date} at location: {full_location_path}"
    )
