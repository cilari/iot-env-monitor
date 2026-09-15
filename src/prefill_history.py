"""
prefill_history.py
------------------
Backfills the CSV + SQLite store with REAL historical hourly weather data
from the Open-Meteo archive API, so the dashboard has context/baseline data
to compare against the incoming live readings.

Usage:
    python3 prefill_history.py            # last 7 days (default)
    python3 prefill_history.py --days 14  # last 14 days
"""
import argparse
import datetime as dt
from zoneinfo import ZoneInfo

import requests

import config
from storage import store_readings


def fetch_history(days: int):
    end = dt.date.today()
    start = end - dt.timedelta(days=days)

    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": config.HOURLY_VARS,
        "timezone": config.TIMEZONE,
    }
    resp = requests.get(config.ARCHIVE_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]

    now = dt.datetime.now(ZoneInfo(config.LOCAL_TZ)).replace(tzinfo=None)
    rows = []
    for i, ts in enumerate(hourly["time"]):
        # Skip future hours the archive may return for the current day.
        if dt.datetime.fromisoformat(ts) > now:
            continue
        if hourly["temperature_2m"][i] is None:
            continue
        rows.append(
            {
                "timestamp": ts,
                "location": config.LOCATION_NAME,
                "temperature": hourly["temperature_2m"][i],
                "humidity": hourly["relative_humidity_2m"][i],
                "pressure": hourly["surface_pressure"][i],
                "wind_speed": hourly["wind_speed_10m"][i],
                "source": "historical",
            }
        )
    return rows


def main():
    ap = argparse.ArgumentParser(description="Prefill store with historical data.")
    ap.add_argument("--days", type=int, default=7, help="How many days back to fetch.")
    args = ap.parse_args()

    print(f"Fetching {args.days} days of historical data for {config.LOCATION_NAME}...")
    rows = fetch_history(args.days)
    written = store_readings(rows)
    print(f"Retrieved {len(rows)} hourly records; wrote {written} new rows.")
    print(f"CSV : {config.CSV_PATH}")
    print(f"DB  : {config.DB_PATH}")


if __name__ == "__main__":
    main()
