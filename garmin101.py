
from garminconnect import Garmin
from datetime import timedelta
from dotenv import load_dotenv
import os
import json

def main():
    load_dotenv()
    # logging.info("Garmin 101: Introduction to Garmin Devices")
    print("Welcome to Garmin 101!")


    # Initialize and login
    print(os.getenv("GARMIN_EMAIL", "<YOUR_EMAIL>"))
    client = Garmin(
        os.getenv("GARMIN_EMAIL", "<YOUR_EMAIL>"),
        os.getenv("GARMIN_PASSWORD", "<YOUR_PASSWORD>")
    )


    client.login()

    # Get today's stats
    from datetime import date
    _today = (date.today()  - timedelta(days=1)).strftime('%Y-%m-%d')
    stats = client.get_stats(_today)
    stats = client.get_activities_by_date((_today))
    stats = client.get_last_activity()


    with open("stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)


    stats = client.get_activity_details(activity_id=21983458805)

    with open("stats2.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    stats = client.get_activity_splits(activity_id=21983458805)

    with open("activity_splits.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)



    # print(f"Today's stats: {stats}")

if __name__ == "__main__":
    main()