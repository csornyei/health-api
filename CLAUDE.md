# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the API server
uv run fastapi dev src/main.py

# Run any Python code
uv run python

# Add a dependency
uv add <package>

# Start InfluxDB and the Explorer UI
docker compose up -d
```

## Architecture

FastAPI app that receives Apple Health exports (via the `Health Auto Export` app) and writes them to InfluxDB 3.

**Request flow:** `POST /api/v1/health/` → validates body as `HealthExport` → `write_metrics()` writes to InfluxDB → returns parsed JSON response.

### Key files

- `src/routers/health.py` — single POST route, wires in the InfluxDB `Depends`
- `src/writers.py` — builds `Point` objects and writes to InfluxDB; contains the per-type logic for quantity, heart rate, and sleep metrics
- `src/schemas.py` — Pydantic models for the full Health Export structure; the `MetricDataPoint` union (`SleepDataPoint | HeartRateMetricPoint | QuantityDataPoint`) drives isinstance dispatch in the writer
- `src/influxdb.py` — `get_influxdb_client()` generator for FastAPI `Depends`; reads `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_DATABASE` from env

### InfluxDB write conventions

Each metric's `name` field becomes the InfluxDB measurement (table) name.

| Point type | Tags | Fields |
|---|---|---|
| `QuantityDataPoint` | `units` | `qty` |
| `HeartRateMetricPoint` | `units` | `min`, `avg`, `max` |
| `SleepDataPoint` | — | `duration_hours`, `sleep_end_ts` (unix seconds) |

Sleep uses `sleepStart` (converted to UTC) as the timestamp; all other points use their `date` field.

### Infrastructure

InfluxDB 3 Core runs locally via Docker (`docker-compose.yaml`) on port `8181`. The Explorer UI runs on port `8888`. Data is persisted to `~/.influxdb/`.
