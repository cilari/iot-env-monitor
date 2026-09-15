"""
Storage layer for the pipeline.

Provides a single helper `store_readings()` that writes rows to BOTH:
  1. a CSV file (append-only, human-readable time-series log)
  2. a SQLite database (queryable structured storage)

De-duplication: a reading is uniquely identified by (timestamp, location).
This lets us safely re-run the prefill/collector without creating duplicates.
"""
import csv
import os
import sqlite3

import config


def _init_csv():
    """Create the CSV with a header row if it does not yet exist."""
    if not os.path.exists(config.CSV_PATH):
        with open(config.CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(config.FIELDS)


def _init_db():
    """Create the SQLite table (with a unique index) if needed."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            timestamp   TEXT NOT NULL,
            location    TEXT NOT NULL,
            temperature REAL,
            humidity    REAL,
            pressure    REAL,
            wind_speed  REAL,
            source      TEXT,
            PRIMARY KEY (timestamp, location)
        )
        """
    )
    conn.commit()
    conn.close()


def _existing_csv_keys():
    """Return set of (timestamp, location) already present in the CSV."""
    keys = set()
    if os.path.exists(config.CSV_PATH):
        with open(config.CSV_PATH, newline="") as f:
            for row in csv.DictReader(f):
                keys.add((row["timestamp"], row["location"]))
    return keys


def store_readings(rows):
    """
    Persist a list of reading dicts to CSV + SQLite.

    Each dict must contain the keys defined in config.FIELDS.
    Returns the number of NEW rows actually written (after de-duplication).
    """
    _init_csv()
    _init_db()

    existing = _existing_csv_keys()
    new_rows = [r for r in rows if (r["timestamp"], r["location"]) not in existing]

    if not new_rows:
        return 0

    # Sort chronologically so the CSV stays ordered even after prefilling.
    new_rows.sort(key=lambda r: r["timestamp"])

    # --- CSV append ---
    with open(config.CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.FIELDS)
        for r in new_rows:
            writer.writerow({k: r.get(k) for k in config.FIELDS})

    # --- SQLite upsert ---
    conn = sqlite3.connect(config.DB_PATH)
    conn.executemany(
        """
        INSERT OR IGNORE INTO readings
            (timestamp, location, temperature, humidity, pressure, wind_speed, source)
        VALUES (:timestamp, :location, :temperature, :humidity, :pressure, :wind_speed, :source)
        """,
        new_rows,
    )
    conn.commit()
    conn.close()

    return len(new_rows)
