from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import HTTPException
from influxdb_client_3 import InfluxDBClient3
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.logger import logger
from src.settings import get_settings

_tracer = trace.get_tracer(__name__)


def get_influxdb_client() -> Generator[InfluxDBClient3, None, None]:
    settings = get_settings()
    client = InfluxDBClient3(
        host=settings.influxdb_host,
        token=settings.influxdb_token,
        database=settings.influxdb_database,
    )
    try:
        yield client
    finally:
        client.close()


def get_all_metric_names(client: InfluxDBClient3) -> list[str]:
    with _tracer.start_as_current_span("influxdb.query_metric_names") as span:
        try:
            table = client.query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox'",
                language="sql",
            )
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        if table is None or len(table) == 0:
            logger.debug("no metrics found in database")
            span.set_attribute("db.result_count", 0)
            return []
        names = [row["table_name"] for row in table.to_pylist()]
        logger.debug("metric names fetched", count=len(names))
        span.set_attribute("db.result_count", len(names))
        return names


def query_metrics(
    client: InfluxDBClient3,
    metrics: list[str],
    from_dt: datetime,
    to_dt: datetime,
) -> dict[str, list[dict]]:
    if from_dt >= to_dt:
        raise HTTPException(status_code=400, detail="Invalid time range: 'from' must be before 'to'")

    if (to_dt - from_dt).total_seconds() > 30 * 24 * 3600:
        raise HTTPException(status_code=400, detail="Time range too large: maximum is 30 days")

    if (to_dt.tzinfo is None) or (from_dt.tzinfo is None):
        raise HTTPException(status_code=400, detail="Timestamps must be timezone-aware")

    known = get_all_metric_names(client)
    if not metrics:
        metrics = known
    else:
        unknown = set(metrics) - set(known)
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown metrics: {sorted(unknown)}")

    from_utc = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_utc = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("querying metrics", metrics=metrics, from_utc=from_utc, to_utc=to_utc)

    results: dict[str, list[dict]] = {}
    with _tracer.start_as_current_span("influxdb.query_metrics") as outer_span:
        outer_span.set_attribute("db.metrics_count", len(metrics))
        outer_span.set_attribute("db.from", from_utc)
        outer_span.set_attribute("db.to", to_utc)
        for metric in metrics:
            with _tracer.start_as_current_span("influxdb.query_metric") as span:
                span.set_attribute("db.metric", metric)
                try:
                    table = client.query(
                        f"SELECT * FROM \"{metric}\" WHERE time >= $start AND time <= $end ORDER BY time ASC",
                        language="sql",
                        query_parameters={"start": from_utc, "end": to_utc},
                    )
                    rows = table.to_pylist() if table is not None and len(table) > 0 else []
                    logger.debug("metric query result", metric=metric, rows=len(rows))
                    span.set_attribute("db.result_count", len(rows))
                    results[metric] = rows
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(StatusCode.ERROR, str(exc))
                    logger.error("metric query failed", metric=metric, exc_info=exc)
                    results[metric] = []
    return results
