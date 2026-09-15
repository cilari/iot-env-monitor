# Technical Report — Simulated IoT Environmental Monitoring Pipeline

**Assessment 1 – Technical Implementation & Data Logging**

---

## 1. Introduction

The Internet of Things (IoT) describes networks of physical devices that sense
their environment, transmit measurements over a network, and feed centralised
systems that store and interpret the data. Environmental monitoring is one of
the most common IoT applications: temperature, humidity, air pressure and wind
sensors are deployed across smart cities, farms, factories and weather stations,
continuously streaming readings that operators visualise on live dashboards.

The objective of this assessment was to design and build a working data pipeline
that reproduces this end-to-end flow without physical hardware. Instead of a real
sensor, the system polls a public weather API that behaves like a sensor feed,
returning frequently updated environmental measurements. The pipeline then
captures, timestamps, stores and visualises those measurements exactly as an
industrial monitoring platform would.

The delivered system performs five functions required by the brief: it retrieves
live data from an online source, processes each incoming response, stores the
results as a growing time-series in two structured formats (CSV and SQLite),
displays them through an auto-refreshing monitoring dashboard, and is documented
by a clear architecture diagram and this report. A distinguishing feature of the
implementation is a historical **prefill** step: before live collection begins,
the pipeline backfills seven days of real hourly history so the dashboard has a
meaningful baseline to compare incoming live readings against, rather than
starting from an empty chart.

## 2. Data Source

The chosen data source is the **Open-Meteo API** (`open-meteo.com`), a free,
public weather service. It was selected over the suggested OpenWeather API for
three practical reasons. First, it requires **no API key or registration**, which
removes an authentication dependency and makes the project fully reproducible by
a marker. Second, it exposes **two complementary endpoints** that map neatly onto
the pipeline's needs: a *forecast/current* endpoint that returns the latest
conditions (used as the live sensor feed), and an *archive* endpoint that returns
historical hourly observations (used for prefilling). Third, it returns clean,
well-structured JSON with explicit units.

Four variables are collected, each treated as an independent "sensor channel":

| Variable | API field | Unit |
|----------|-----------|------|
| Temperature | `temperature_2m` | °C |
| Relative humidity | `relative_humidity_2m` | % |
| Surface pressure | `surface_pressure` | hPa |
| Wind speed | `wind_speed_10m` | km/h |

The simulated sensor site is **Sydney, Australia** (latitude −33.8688, longitude
151.2093), configured in a single `config.py` file so the location can be changed
in one place. The live endpoint updates every 15 minutes on the provider side,
while the collector polls it every 60 seconds, producing a dense time-series that
demonstrates the pipeline's behaviour during a demonstration.

## 3. System Architecture

The pipeline follows the classic four-stage IoT data flow, where each stage has a
single responsibility and communicates with the next through a well-defined
interface (an HTTP response or a stored row). This separation means any stage can
be modified or replaced independently — for example swapping the data source or
the dashboard tool — without rewriting the others.

```
Open-Meteo API  ->  Python collection scripts  ->  CSV + SQLite storage  ->  Streamlit dashboard  ->  User
```

**Stage 1 – Data Source.** The Open-Meteo API acts as the simulated sensor,
reachable over HTTPS and returning JSON.

**Stage 2 – Data Collection.** Two Python programs consume the API. `prefill_history.py`
runs once to backfill historical data; `collector.py` runs continuously, polling
the live endpoint on a fixed interval. Both normalise the raw JSON into a common
record structure before handing it to the storage layer.

**Stage 3 – Data Storage.** A shared `storage.py` module writes every reading to
both a CSV file (a human-readable, append-only log) and a SQLite database (a
queryable relational store). Storing to both satisfies both acceptable options in
the brief and lets the dashboard query efficiently while the CSV remains easy to
inspect or import into other tools such as Power BI or Excel.

**Stage 4 – Visualisation.** `dashboard.py` reads from the store and renders a
live web dashboard that auto-refreshes so new readings appear automatically.

The full architecture, including the data-storage fan-out and the dashboard's
primary (SQLite) and fallback (CSV) read paths, is shown in `architecture.png`
(source: `architecture.mmd` and `architecture.drawio`).

## 4. Implementation

The system is written in Python 3.13 and organised into small, focused modules.

**Configuration (`config.py`).** All tunable values — sensor coordinates, API
URLs, the list of variables, storage paths, the CSV/table schema and the 60-second
collection interval — live in one module. Every other file imports from it, so
there are no hard-coded values scattered through the codebase.

**Storage layer (`storage.py`).** This module exposes a single function,
`store_readings(rows)`, that persists a batch of reading dictionaries to both
CSV and SQLite. It lazily creates the CSV header and the SQLite table on first
use. Crucially, it performs **de-duplication**: each reading is keyed by
`(timestamp, location)`, the SQLite table declares that pair as a `PRIMARY KEY`,
and inserts use `INSERT OR IGNORE`. This makes the whole pipeline *idempotent* —
the prefill or collector can be re-run without creating duplicate rows, which is
essential for a system that is expected to run repeatedly.

**Historical prefill (`prefill_history.py`).** This script queries the archive
endpoint for the last seven days (configurable via `--days`), iterates over the
returned parallel arrays of timestamps and values, and builds one record per
hour tagged with `source = "historical"`. It filters out any future hours the
archive may return for the current day, so the baseline never contains data that
has not yet occurred.

**Live collector (`collector.py`).** This is the automation heart of the
pipeline. Its `fetch_live_reading()` function sends a request to the live
endpoint, extracts the four variables, attaches a local wall-clock timestamp at
second precision, and tags the record with `source = "live"`. The `main()` loop
calls this once per interval using `time.sleep()`, printing each reading to the
console for live evidence. Command-line flags make it flexible for both
demonstration and production-style use: `--once` takes a single reading,
`--count N` takes N readings then exits, and `--interval` overrides the cadence.
Network failures are caught so a transient API error logs a message and the loop
continues rather than crashing — a small but important reliability property for
any long-running collector.

**Dashboard (`dashboard.py`).** Built with Streamlit and Plotly, the dashboard
loads the data (from SQLite, falling back to CSV), parses timestamps, and renders
four sections that satisfy the brief's visualisation requirements:

1. **Most-recent reading** — four metric cards showing the latest temperature,
   humidity, pressure and wind speed, each with a delta versus the previous
   reading. The headline reading intentionally prioritises the newest *live*
   sample so the card reflects the current sensor state.
2. **Time-series chart** — an interactive line chart of a user-selected metric
   over time, coloured by source so the historical baseline and live readings are
   visually distinct.
3. **Additional visualisations** — a gauge indicator of the current temperature
   and a bar chart of average temperature by hour of day.
4. **Raw data & statistics** — a table of the most recent records and summary
   statistics.

Auto-refresh is handled by the `streamlit-autorefresh` component (with an HTML
meta-refresh fallback), so the dashboard re-queries the store every 30 seconds
and surfaces newly collected readings without any manual reload — the defining
characteristic of a live monitoring system.

**Automation.** During development the collector was run with `--count` to
generate bounded batches. For continuous operation it runs unbounded
(`python collector.py`), and the README documents how to schedule it with `cron`
or macOS `launchd` for hands-off, always-on collection.

## 5. Results

The pipeline was executed successfully end to end. Running `prefill_history.py`
retrieved **179 hourly historical records** for Sydney and wrote them to both
stores. The collector was then run and captured live readings such as:

```
[2026-09-15T10:45:56] T=22.0C  RH=47%  P=1009.6hPa  Wind=8.5km/h  -> stored
[2026-09-15T10:46:01] T=22.0C  RH=47%  P=1009.6hPa  Wind=8.5km/h  -> stored
```

Inspection of the storage layer confirmed both formats were populated and
consistent. The CSV begins with the expected header and holds ordered rows:

```
timestamp,location,temperature,humidity,pressure,wind_speed,source
2026-09-08T00:00,"Sydney, AU",14.9,68,1014.2,21.8,historical
...
2026-09-15T10:46:01,"Sydney, AU",22.0,47,1009.6,8.5,live
```

A query against SQLite returned a total row count matching the CSV, grouped as
179 `historical` and the collected `live` rows, with the maximum timestamp equal
to the latest live reading — confirming de-duplication and ordering both work.
The Streamlit dashboard started cleanly (HTTP 200, no runtime errors in the
server log) and rendered the metric cards, time-series chart, gauge and bar
chart, refreshing automatically as the collector appended new rows. Screenshots
of the running collector, the stored files and the dashboard are included as
demonstration evidence in the README.

## 6. Challenges and Limitations

Several practical issues were encountered and resolved during development. The
first was **duplicate readings**: because the live endpoint only updates every 15
minutes, polling every 60 seconds returns identical values, and re-running the
scripts risked storing the same record twice. This was solved with the
`(timestamp, location)` primary key and `INSERT OR IGNORE`, making the pipeline
idempotent. The second issue was the **archive endpoint returning future hours**
for the current day, which polluted the baseline with data that had not occurred;
a filter now discards any timestamp later than the moment of collection. A third
consideration was the choice of dashboard tool: the brief recommends Power BI, but
Power BI Desktop does not run natively on macOS, so a Python-based Streamlit
dashboard was used instead — it provides genuine live auto-refresh and keeps the
whole stack in one language, while the CSV output remains fully importable into
Power BI on Windows if required.

The system also has honest limitations. It monitors a **single location** and a
fixed set of four variables. The collector runs as a **single process with no
retry queue**, so if the machine sleeps, collection pauses. Storage is **local
and unbounded** — SQLite is excellent for this scale but the file grows
indefinitely and is not suited to millions of rows or concurrent writers. Finally,
because the underlying API updates only every 15 minutes, sub-minute polling adds
temporal resolution to the log but not new information.

## 7. Future Improvements

The most impactful next step would be to introduce a **message broker** such as
MQTT or AWS IoT Core between collection and storage, decoupling producers from
consumers and allowing many simulated sensors to publish concurrently — the
pattern real IoT fleets use. **Cloud deployment** would follow naturally: running
the collector on a scheduled serverless function (e.g. AWS Lambda + EventBridge)
and storing readings in a managed time-series database (such as Amazon Timestream
or InfluxDB) would remove the "machine must stay awake" limitation and scale to
many sites. On the analytics side, **alerting** (thresholds that trigger a
notification when a reading is anomalous) and **basic forecasting** would move the
system from passive monitoring toward the predictive maintenance use cases common
in industry. Adding **multiple locations**, a **data-retention/rollup policy**,
and **automated tests** around the collection and storage functions would round
out the system for production readiness. Finally, integrating **genuine hardware**
— an ESP32 or Raspberry Pi with a DHT22 sensor publishing over MQTT — would close
the loop and turn this simulation into a real IoT deployment while reusing the
same storage and dashboard layers unchanged.

## 8. Conclusion

The project delivers a complete, working IoT-style data pipeline: a live public
API stands in for a sensor, automated Python scripts collect and process the data,
a de-duplicated time-series is stored in both CSV and SQLite, and an
auto-refreshing dashboard visualises the latest state alongside a historical
baseline. The modular design, idempotent storage, and clear separation of the
four stages make the system both easy to understand and straightforward to extend
toward the cloud-scale, multi-sensor architectures used in real environmental
monitoring platforms.
