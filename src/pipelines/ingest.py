import logging


def ingest_garmin_activities_by_date(activity_date: str, activities_destination: str):
    logging.info(
        f"Ingesting all the activities for date: {activity_date} at location: {activities_destination}"
    )

    with open(
        f"{activities_destination}/garmin_activities_{activity_date}.txt", "w"
    ) as f:
        f.write(f"Activities for {activity_date} at {activities_destination}\n")
        f.write("Activity 1: Running\n")
        f.write("Activity 2: Cycling\n")
        f.write("Activity 3: Swimming\n")
    logging.info(
        f"Finished ingesting activities for date: {activity_date} at location: {activities_destination}"
    )
