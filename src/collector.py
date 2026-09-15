"""
collector.py
------------
The automated data collection component of the pipeline.

Behaviour:
  * Sends a request to the Open-Meteo live API (acts as our "sensor").
  * Extracts temperature, humidity, pressure and wind speed.
  * Timestamps and stores the reading to CSV + SQLite.
  * Repeats automatically every COLLECT_INTERVAL_SECONDS.

Usage:
    python3 collector.py              # run forever, one reading per interval
    python3 collector.py --once       # take a single reading and exit
    python3 collector.py --count 10   # take 10 readings then exit
"""
import argparse
import datetime as dt
import time
from zoneinfo import ZoneInfo

import requests

import config
from storage import store_readings


def fetch_live_reading():
    """Query the live API and return a single normalised reading dict."""
    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "current": config.CURRENT_VARS,
        "timezone": config.TIMEZONE,
    }
    resp = requests.get(config.LIVE_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    cur = resp.json()["current"]

    # Use the sensor site's local wall-clock time (not the host/container clock)
    # so live timestamps stay consistent with the historical data.
    timestamp = dt.datetime.now(ZoneInfo(config.LOCAL_TZ)).strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "timestamp": timestamp,
        "location": config.LOCATION_NAME,
        "temperature": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "pressure": cur.get("surface_pressure"),
        "wind_speed": cur.get("wind_speed_10m"),
        "source": "live",
    }


def collect_once():
    try:
        reading = fetch_live_reading()
    except requests.RequestException as e:
        print(f"[{dt.datetime.now():%H:%M:%S}] API request failed: {e}")
        return
    written = store_readings([reading])
    status = "stored" if written else "duplicate (skipped)"
    print(
        f"[{reading['timestamp']}] "
        f"T={reading['temperature']}C  "
        f"RH={reading['humidity']}%  "
        f"P={reading['pressure']}hPa  "
        f"Wind={reading['wind_speed']}km/h  -> {status}"
    )


def main():
    ap = argparse.ArgumentParser(description="Live environmental data collector.")
    ap.add_argument("--once", action="store_true", help="Collect a single reading and exit.")
    ap.add_argument("--count", type=int, default=0, help="Collect N readings then exit (0 = infinite).")
    ap.add_argument("--interval", type=int, default=config.COLLECT_INTERVAL_SECONDS,
                    help="Seconds between readings.")
    args = ap.parse_args()

    print(f"Collector started for {config.LOCATION_NAME} "
          f"(interval={args.interval}s). Press Ctrl+C to stop.")

    if args.once:
        collect_once()
        return

    n = 0
    try:
        while True:
            collect_once()
            n += 1
            if args.count and n >= args.count:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nCollector stopped by user.")


if __name__ == "__main__":
    main()
