"""
Shared configuration for the IoT Environmental Monitoring pipeline.

Change LATITUDE / LONGITUDE / LOCATION_NAME to monitor a different "sensor site".
Default location is Sydney, Australia.
"""
import os

# --- Simulated sensor location ---------------------------------------------
LOCATION_NAME = "Sydney, AU"
LATITUDE = -33.8688
LONGITUDE = 151.2093
TIMEZONE = "auto"
# IANA timezone of the sensor site. Used so timestamps are always in the
# location's local time regardless of the host/container clock (containers
# usually run in UTC, which would otherwise desync live vs historical data).
LOCAL_TZ = "Australia/Sydney"

# --- API endpoints (Open-Meteo, free, no API key required) -----------------
LIVE_API_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Variables we treat as "sensor channels"
CURRENT_VARS = "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m"
HOURLY_VARS = "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m"

# --- Storage paths ----------------------------------------------------------
# config.py lives in src/, so the project root is one level up. Data is stored
# at <project_root>/data so it matches the Docker volume mount and works on
# Streamlit Cloud too.
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "readings.csv")
DB_PATH = os.path.join(DATA_DIR, "readings.db")

# CSV / table schema (order matters for the CSV header)
FIELDS = [
    "timestamp",      # ISO8601 local time of the reading
    "location",       # sensor site label
    "temperature",    # deg C
    "humidity",       # %
    "pressure",       # hPa
    "wind_speed",     # km/h
    "source",         # "live" or "historical"
]

# --- Collection cadence -----------------------------------------------------
COLLECT_INTERVAL_SECONDS = 60  # per assignment brief: every 30-60 seconds

os.makedirs(DATA_DIR, exist_ok=True)
