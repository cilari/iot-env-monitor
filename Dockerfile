# Python 3.12 has mature prebuilt wheels for pandas/numpy/pyarrow, which avoids
# the native segfault seen with the source-built pandas on Python 3.13.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Streamlit dashboard port
EXPOSE 8501

# Persist the time-series data outside the container
VOLUME ["/app/data"]

# Default command runs the dashboard; the collector service overrides this
# in docker-compose.yml.
CMD ["streamlit", "run", "src/dashboard.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
