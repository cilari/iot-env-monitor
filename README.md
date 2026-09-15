# IoT Environmental Monitoring — Data Pipeline

A simulated IoT environmental monitoring system that collects **live** weather
data from a public API, stores it as a growing time-series in **CSV + SQLite**,
and visualises it on an **auto-refreshing dashboard**. Historical data is
pre-loaded first so the dashboard has a baseline to compare live readings against.

```
Open-Meteo API -> Python collector -> CSV + SQLite -> Streamlit dashboard
```

**Live demo:** _add your Streamlit Community Cloud URL here after deploying_

## Project structure

```
iot-env-monitor/
├── src/
│   ├── config.py           # central configuration (location, API, paths)
│   ├── storage.py          # CSV + SQLite writer with de-duplication
│   ├── prefill_history.py  # one-off historical backfill (baseline)
│   ├── collector.py        # automated live collection loop ("the sensor")
│   └── dashboard.py        # Streamlit + Plotly live dashboard
├── tests/
│   └── test_storage.py     # unit tests for the storage layer
├── docs/
│   ├── architecture.png    # system architecture diagram (+ .mmd / .drawio)
│   └── TECHNICAL_REPORT.md  # written report
├── data/                   # generated time-series (gitignored)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Setup (native macOS / Linux)

```bash
cd iot-env-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
```

## Run the pipeline (native)

The collector and dashboard run **at the same time**, in two terminals. You do
not run one then the other — both stay running, and the dashboard refreshes
itself every 30 seconds.

```bash
# terminal 1 — backfill baseline, then collect live data continuously
python src/prefill_history.py --days 7
python src/collector.py

# terminal 2 — dashboard (open the printed URL, default http://localhost:8501)
streamlit run src/dashboard.py
```

## Run with Docker / Finch (recommended)

Uses a clean Python 3.12 environment and starts everything with one command.
`finch` and `docker` are interchangeable here.

```bash
docker compose up --build       # add -d to run in the background
```

Three services share the `./data` volume:
- `prefill` — backfills 7 days of history, then exits
- `collector` — collects a live reading every 60s (auto-restarts)
- `dashboard` — served at **http://localhost:8501**

Stop with `docker compose down` (your `data/` persists on the host).

## Deploy to Streamlit Community Cloud (free public URL)

Streamlit Cloud only runs the dashboard (no separate collector, ephemeral
filesystem). The dashboard is built to handle this: on each refresh it **seeds
the historical baseline and appends a fresh live reading itself** whenever the
data is stale (`ensure_fresh_data()` in `src/dashboard.py`).

1. Push this repo to GitHub.
2. Go to https://share.streamlit.io → **New app** → pick your repo/branch.
3. Set **Main file path** to `src/dashboard.py`.
4. (Optional) Under **Advanced settings → Secrets/vars**, add `SELF_COLLECT="1"`
   to force a live fetch on every refresh.
5. Deploy. Copy the public URL into the "Live demo" line above and your resume.

> Note: Community Cloud apps sleep after inactivity and their disk is ephemeral,
> so the accumulated live points reset when the app wakes — the historical
> baseline and current reading are re-fetched automatically on load.

## Run the tests

```bash
python tests/test_storage.py        # or: python -m pytest tests/ -q
```

## Troubleshooting: "Python quit unexpectedly" / dashboard won't connect

A native segfault caused by a Python 3.13 dependency mismatch (`pandas 2.2.2`
has no 3.13 wheel, so pip builds it against a mismatched NumPy). Fixes:

- **Easiest:** use Docker/Finch (clean Python 3.12), or
- **Local fix:** `pip install --only-binary=:all: -r requirements.txt`
  (pinned to `pandas==2.2.3`, the first pandas with a Python 3.13 wheel).

## Data source

[Open-Meteo](https://open-meteo.com/) — free, no API key.
Live: `https://api.open-meteo.com/v1/forecast` ·
Archive: `https://archive-api.open-meteo.com/v1/archive`.
