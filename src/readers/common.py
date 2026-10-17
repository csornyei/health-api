import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone
from collections.abc import Generator
from statistics import mean

import structlog
from influxdb_client_3 import InfluxDBClient3
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.settings import get_settings

_tracer = trace.get_tracer(__name__)
logger = structlog.get_logger(app_name="health-api")
_missing_measurements: ContextVar[set[str] | None] = ContextVar(
    "missing_measurements", default=None
)
_MISSING_TABLE_PATTERN = re.compile(r"table 'public\.iox\.([^']+)' not found")


def _missing_table_name(exc: Exception) -> str | None:
    match = _MISSING_TABLE_PATTERN.search(str(exc))
    return match.group(1) if match else None


@contextmanager
def capture_missing_measurements() -> Generator[set[str], None, None]:
    missing: set[str] = set()
    token = _missing_measurements.set(missing)
    try:
        yield missing
    finally:
        _missing_measurements.reset(token)


def query(client: InfluxDBClient3, sql: str, params: dict | None = None) -> list[dict]:
    with _tracer.start_as_current_span("influxdb.query") as span:
        span.set_attribute("db.query.text", sql)
        try:
            table = client.query(sql, language="sql", query_parameters=params or {})
        except Exception as exc:
            missing_table = _missing_table_name(exc)
            if missing_table is not None:
                captured = _missing_measurements.get()
                if captured is not None:
                    captured.add(missing_table)
                logger.warning(
                    "query skipped because measurement does not exist",
                    measurement=missing_table,
                )
                span.set_attribute("db.result_count", 0)
                span.set_attribute("db.measurement_missing", True)
                span.set_attribute("db.measurement", missing_table)
                return []
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        if table is None or len(table) == 0:
            span.set_attribute("db.result_count", 0)
            return []
        rows = table.to_pylist()
        span.set_attribute("db.result_count", len(rows))
        return rows


def ts(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def ts_end(d: date) -> str:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def align_daily(
    day_map: dict[date, float | None], period_start: date, n: int
) -> list[float | None]:
    return [day_map.get(period_start + timedelta(days=i)) for i in range(n)]


def avg(values: list[float | None]) -> float | None:
    populated = [v for v in values if v is not None]
    return round(mean(populated), 2) if populated else None


def row_date(row: dict, key: str) -> date:
    val = row[key]
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).date()
    return val


def summary_query_chunk_days() -> int:
    return max(1, get_settings().summary_query_chunk_days)


def daily_metric(
    client: InfluxDBClient3,
    measurement: str,
    field: str,
    agg: str,
    period_start: date,
    period_end: date,
    n: int,
) -> list[float | None]:
    """Generic daily aggregation query returning a length-N daily array."""
    day_map: dict[date, float | None] = {}

    chunk_days = summary_query_chunk_days()
    chunk_start = period_start
    while chunk_start <= period_end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), period_end)
        with _tracer.start_as_current_span("influxdb.daily_metric_chunk") as span:
            span.set_attribute("db.measurement", measurement)
            span.set_attribute("db.aggregate", agg)
            span.set_attribute("db.chunk_start", chunk_start.isoformat())
            span.set_attribute("db.chunk_end", chunk_end.isoformat())
            try:
                rows = query(
                    client,
                    f"""
                    SELECT DATE_TRUNC('day', time) AS day, {agg}("{field}") AS value
                    FROM "{measurement}"
                    WHERE time >= $start AND time <= $end
                    GROUP BY day
                    ORDER BY day
                    """,
                    {"start": ts(chunk_start), "end": ts_end(chunk_end)},
                )
            except Exception as exc:
                logger.error(
                    "daily metric chunk query failed",
                    measurement=measurement,
                    field=field,
                    aggregate=agg,
                    period_start=period_start.isoformat(),
                    period_end=period_end.isoformat(),
                    chunk_start=chunk_start.isoformat(),
                    chunk_end=chunk_end.isoformat(),
                    exc_info=exc,
                )
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

        for row in rows:
            d = row_date(row, "day")
            if row["value"] is not None:
                day_map[d] = round(float(row["value"]), 4)
        chunk_start = chunk_end + timedelta(days=1)

    return align_daily(day_map, period_start, n)


_daily_metric = daily_metric
