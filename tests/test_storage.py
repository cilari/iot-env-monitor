"""
Unit tests for the storage layer.

Run:  python -m pytest tests/ -q      (or)   python tests/test_storage.py
"""
import os
import sys
import tempfile
import importlib

# Make src/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _fresh_modules(tmpdir):
    """Import config + storage with DATA_DIR redirected to a temp dir."""
    import config
    config.DATA_DIR = tmpdir
    config.CSV_PATH = os.path.join(tmpdir, "readings.csv")
    config.DB_PATH = os.path.join(tmpdir, "readings.db")
    import storage
    importlib.reload(storage)
    return config, storage


def _sample_row(ts="2026-01-01T00:00:00", source="live"):
    return {
        "timestamp": ts,
        "location": "Test City",
        "temperature": 20.0,
        "humidity": 50,
        "pressure": 1010.0,
        "wind_speed": 5.0,
        "source": source,
    }


def test_store_writes_new_rows():
    with tempfile.TemporaryDirectory() as tmp:
        _, storage = _fresh_modules(tmp)
        written = storage.store_readings([_sample_row("2026-01-01T00:00:00"),
                                          _sample_row("2026-01-01T00:01:00")])
        assert written == 2


def test_store_deduplicates():
    with tempfile.TemporaryDirectory() as tmp:
        _, storage = _fresh_modules(tmp)
        storage.store_readings([_sample_row("2026-01-01T00:00:00")])
        # Same (timestamp, location) should not be written again.
        written = storage.store_readings([_sample_row("2026-01-01T00:00:00")])
        assert written == 0


def test_csv_and_db_stay_in_sync():
    import csv
    import sqlite3
    with tempfile.TemporaryDirectory() as tmp:
        config, storage = _fresh_modules(tmp)
        rows = [_sample_row(f"2026-01-01T00:0{i}:00") for i in range(3)]
        storage.store_readings(rows)
        with open(config.CSV_PATH) as f:
            csv_rows = list(csv.DictReader(f))
        conn = sqlite3.connect(config.DB_PATH)
        db_count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        conn.close()
        assert len(csv_rows) == 3
        assert db_count == 3


if __name__ == "__main__":
    test_store_writes_new_rows()
    test_store_deduplicates()
    test_csv_and_db_stay_in_sync()
    print("All storage tests passed.")
