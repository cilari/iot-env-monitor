"""
dashboard.py
------------
Live monitoring dashboard for the IoT environmental pipeline.

Reads directly from the SQLite store (falls back to CSV) and auto-refreshes
so newly collected readings appear without a manual reload.

Includes (per assignment brief):
  * Most-recent reading display (metric cards / indicators)
  * A time-series chart of data over time
  * At least one additional visualisation (gauge + bar chart)

Run:
    streamlit run dashboard.py
"""
import os
import sqlite3
import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import config
from storage import store_readings
from collector import fetch_live_reading
from prefill_history import fetch_history

st.set_page_config(page_title="IoT Environmental Monitor", layout="wide")

# --- Auto refresh (every 30s) ----------------------------------------------
REFRESH_MS = 30_000
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, key="datarefresh")
except Exception:
    # Lightweight fallback if the helper package is not installed.
    st.markdown(
        f'<meta http-equiv="refresh" content="{REFRESH_MS // 1000}">',
        unsafe_allow_html=True,
    )


# --- Cloud-friendly self-collection ----------------------------------------
# When a separate collector process is running (local/Docker), the dashboard
# just reads the store. When deployed to Streamlit Community Cloud there is no
# collector and the filesystem is ephemeral, so the dashboard collects for
# itself: it seeds history once and appends a fresh live reading whenever the
# newest one is stale. Set env SELF_COLLECT=1 to force it on.
STALE_AFTER_SECONDS = 120


def _newest_live_age_seconds(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT MAX(timestamp) FROM readings WHERE source='live'"
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        newest = dt.datetime.fromisoformat(row[0])
    except ValueError:
        return None
    now = dt.datetime.now(ZoneInfo(config.LOCAL_TZ)).replace(tzinfo=None)
    return (now - newest).total_seconds()


def ensure_fresh_data():
    """Seed history if empty and collect a live reading if data is stale."""
    forced = os.getenv("SELF_COLLECT", "").lower() in ("1", "true", "yes")

    # Seed historical baseline once.
    has_history = False
    if os.path.exists(config.DB_PATH):
        conn = sqlite3.connect(config.DB_PATH)
        try:
            has_history = conn.execute(
                "SELECT 1 FROM readings WHERE source='historical' LIMIT 1"
            ).fetchone() is not None
        except sqlite3.OperationalError:
            has_history = False
        conn.close()
    if not has_history:
        try:
            store_readings(fetch_history(7))
        except Exception as e:  # network hiccup shouldn't crash the page
            st.warning(f"Could not load historical data: {e}")

    # Append a live reading if none yet, if stale, or if forced.
    age = _newest_live_age_seconds(config.DB_PATH)
    if forced or age is None or age > STALE_AFTER_SECONDS:
        try:
            store_readings([fetch_live_reading()])
        except Exception as e:
            st.warning(f"Could not fetch live reading: {e}")


ensure_fresh_data()


@st.cache_data(ttl=15)
def load_data() -> pd.DataFrame:
    """Load readings from SQLite, falling back to CSV."""
    if os.path.exists(config.DB_PATH):
        conn = sqlite3.connect(config.DB_PATH)
        df = pd.read_sql_query("SELECT * FROM readings", conn)
        conn.close()
    elif os.path.exists(config.CSV_PATH):
        df = pd.read_csv(config.CSV_PATH)
    else:
        return pd.DataFrame(columns=config.FIELDS)

    # Timestamps are mixed precision (historical = minute, live = second),
    # so parse as generic ISO8601 rather than inferring one fixed format.
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    return df


df = load_data()

st.title("🌡️ IoT Environmental Monitoring Dashboard")
st.caption(f"Simulated sensor site: **{config.LOCATION_NAME}** · "
           f"data source: Open-Meteo API · auto-refresh every {REFRESH_MS//1000}s")
st.caption("Built by **Yucen (Lari) Xie**")

if df.empty:
    st.warning("No data yet. Run `python3 prefill_history.py` and `python3 collector.py` first.")
    st.stop()

# --- Sidebar filters --------------------------------------------------------
st.sidebar.header("Filters")
show_source = st.sidebar.multiselect(
    "Data source", options=sorted(df["source"].unique()),
    default=sorted(df["source"].unique()),
)
df = df[df["source"].isin(show_source)]

latest = df.iloc[-1]
live_df = df[df["source"] == "live"]
# For an IoT live monitor, the headline "most recent reading" should be the
# newest LIVE sensor reading when available (historical rows are baseline).
if not live_df.empty:
    latest = live_df.iloc[-1]

# --- Most recent reading (indicators) --------------------------------------
st.subheader("Most Recent Reading")
st.caption(f"Recorded at {latest['timestamp']:%Y-%m-%d %H:%M:%S} ({latest['source']})")
c1, c2, c3, c4 = st.columns(4)


def _delta(col):
    """Change vs the previous reading in the same series as `latest`."""
    series = live_df if not live_df.empty else df
    if len(series) < 2:
        return None
    prev = series.iloc[-2][col]
    if pd.isna(prev) or pd.isna(latest[col]):
        return None
    return round(float(latest[col]) - float(prev), 2)


c1.metric("Temperature (°C)", f"{latest['temperature']:.1f}", _delta("temperature"))
c2.metric("Humidity (%)", f"{latest['humidity']:.0f}", _delta("humidity"))
c3.metric("Pressure (hPa)", f"{latest['pressure']:.1f}", _delta("pressure"))
c4.metric("Wind (km/h)", f"{latest['wind_speed']:.1f}", _delta("wind_speed"))

st.divider()

# --- Time-series chart ------------------------------------------------------
st.subheader("Time-Series")
metric = st.selectbox(
    "Metric",
    options=["temperature", "humidity", "pressure", "wind_speed"],
    format_func=lambda m: {
        "temperature": "Temperature (°C)",
        "humidity": "Humidity (%)",
        "pressure": "Pressure (hPa)",
        "wind_speed": "Wind speed (km/h)",
    }[m],
)
fig_ts = px.line(df, x="timestamp", y=metric, color="source", markers=True)
fig_ts.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig_ts, use_container_width=True)

# --- Additional visualisations: gauge + bar --------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Current Temperature Gauge")
    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=float(latest["temperature"]),
        number={"suffix": " °C"},
        gauge={
            "axis": {"range": [-5, 45]},
            "bar": {"color": "#e45756"},
            "steps": [
                {"range": [-5, 10], "color": "#cfe8ff"},
                {"range": [10, 25], "color": "#d9f2d9"},
                {"range": [25, 45], "color": "#ffe0cc"},
            ],
        },
    ))
    gauge.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(gauge, use_container_width=True)

with col_b:
    st.subheader("Avg Temperature by Hour of Day")
    tmp = df.copy()
    tmp["hour"] = tmp["timestamp"].dt.hour
    hourly_avg = tmp.groupby("hour")["temperature"].mean().reset_index()
    fig_bar = px.bar(hourly_avg, x="hour", y="temperature",
                     labels={"hour": "Hour of day", "temperature": "Avg °C"})
    fig_bar.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

# --- Raw data + stats -------------------------------------------------------
with st.expander("Recent records & summary statistics"):
    st.write(f"Total records: **{len(df)}**  ·  live: **{len(live_df)}**  ·  "
             f"historical: **{len(df) - len(live_df)}**")
    st.dataframe(df.tail(20).iloc[::-1], use_container_width=True)
    st.write(df[["temperature", "humidity", "pressure", "wind_speed"]].describe())
