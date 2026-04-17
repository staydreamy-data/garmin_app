import logging
from pathlib import Path
from datetime import datetime
from garminconnect import Garmin
import json
from collections import defaultdict
from airflow.hooks.base import BaseHook

METHOD_REGISTRY: dict[str, str] = {
    "splits": "get_activity_splits",
    "activity_details": "get_activity_details",
    "workouts": "get_workout_by_id",
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


def _get_activity_date(activity: dict, fallback_date: str) -> str:
    activity_date = activity.get("startTimeLocal") or activity.get("startTimeGMT")
    if isinstance(activity_date, str) and len(activity_date) >= 10:
        return activity_date[:10]
    return fallback_date


def _write_activities_file(
    storage_root: str,
    activities_folder: str,
    activity_date: str,
    ingestion_time: str,
    activities: list,
):
    """
    Write the raw activities payload to a JSON file in the appropriate date partition.

    Args:
        storage_root: Base directory for output files.
        activities_folder: Folder name for raw activities payloads.
        activity_date: Date string (YYYY-MM-DD) used for partitioning.
        ingestion_time: ISO timestamp string for when the ingestion is happening.
        activities: List of activity dicts to write.

    Returns:
        The full path to the directory where the activities were written.
    """
    if not activities:
        logging.info(f"No activities to write for date: {activity_date}")
        return

    full_location_path = f"{storage_root}/{activities_folder}/dt={activity_date}"
    Path(full_location_path).mkdir(parents=True, exist_ok=True)

    with open(
        f"{full_location_path}/activities_{ingestion_time}.json", "w", encoding="utf-8"
    ) as f:
        json.dump(activities, f, indent=4)

    return full_location_path


def _ingest_assets(
    client, storage_root: str, assets: list, activity: dict, activity_date: str
):
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
        source = asset.get("source")

        if not overwrite and Path(output_file).exists():
            logging.info(
                f"Skipping {method_key} for activity {activity_id} as output already exists and overwrite is False."
            )
            continue

        method_name = METHOD_REGISTRY.get(method_key)
        if not method_name:
            logging.warning(f"No Garmin method found for key: {method_key}. Skipping.")
            continue

        method = getattr(client, method_name, None)

        if source == "activity":
            result = method(activity_id)
        elif source == "reference" and method_key == "workouts":
            workout_id = activity.get("workoutId")
            if not workout_id:
                logging.info(
                    f"No workoutId found for activity {activity_id}. Skipping workout asset."
                )
                continue
            result = method(workout_id)
        else:
            logging.warning(
                f"Unsupported source '{source}' for asset '{method_key}'. Skipping."
            )
            continue

        if not result:
            logging.info(
                f"No data returned for {method_key} of activity {activity_id}. Skipping."
            )
            continue

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

        logging.info(
            f"Ingested {method_key} for activity {activity_id} and saved to {output_file}"
        )


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

    activities = client.get_activities_by_date(
        startdate=activity_date, enddate=activity_date
    )

    _write_activities_file(
        storage_root=storage_root,
        activities_folder=activities_folder,
        activity_date=activity_date,
        ingestion_time=ingestion_time,
        activities=activities,
    )

    if not activities:
        logging.info(f"No activities found for date: {activity_date}")
        return

    logging.info(f"Retrieved {len(activities)} activities for date: {activity_date}")

    for activity in activities:
        _ingest_assets(
            client=client,
            storage_root=storage_root,
            assets=assets,
            activity=activity,
            activity_date=activity_date,
        )

    logging.info(
        f"Finished ingesting {len(activities)} activities for date: {activity_date} at location: {full_location_path}"
    )


def ingest_garmin_activities_by_date_range(
    conn_id,
    start_date: str,
    end_date: str,
    storage_root: str,
    activities_folder: str,
    assets: list,
):
    """
    Ingest Garmin activities for a date range and write them back into daily partitions.

    Flow:
        1. Login once using ``conn_id``.
        2. Download all activities for ``start_date`` to ``end_date`` in one request.
        3. Group activities by their actual activity date.
        4. Save raw activities and per-activity assets under existing daily ``dt=<date>`` partitions.

    Args:
        conn_id: Airflow connection id containing Garmin credentials.
        start_date: Start date in ``YYYY-MM-DD`` format.
        end_date: End date in ``YYYY-MM-DD`` format.
        storage_root: Base directory for output files.
        activities_folder: Folder name for raw activities payloads.
        assets: List of asset configs. Expected keys per asset:
            ``key``, ``enabled``, ``output_folder``, ``overwrite``.
    """

    client = get_garmin_client(conn_id)

    ingestion_time = datetime.now().isoformat()
    logging.info(
        f"Ingesting all the activities for date range: {start_date} to {end_date}"
    )

    activities = client.get_activities_by_date(startdate=start_date, enddate=end_date)

    if not activities:
        logging.info(f"No activities found for date range: {start_date} to {end_date}")
        return

    logging.info(
        f"Retrieved {len(activities)} activities for date range: {start_date} to {end_date}"
    )

    activities_by_date: dict[str, list] = defaultdict(list)
    for activity in activities:
        activity_date = _get_activity_date(activity, start_date)
        activities_by_date[activity_date].append(activity)

    for activity_date, daily_activities in sorted(activities_by_date.items()):
        full_location_path = _write_activities_file(
            storage_root=storage_root,
            activities_folder=activities_folder,
            activity_date=activity_date,
            ingestion_time=ingestion_time,
            activities=daily_activities,
        )
        logging.info(
            f"Ingesting {len(daily_activities)} activities for date: {activity_date} at location: {full_location_path}"
        )

        for activity in daily_activities:
            _ingest_assets(
                client=client,
                storage_root=storage_root,
                assets=assets,
                activity=activity,
                activity_date=activity_date,
            )

    logging.info(
        f"Finished ingesting {len(activities)} activities for date range: {start_date} to {end_date}"
    )
