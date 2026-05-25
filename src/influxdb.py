from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import HTTPException
from influxdb_client_3 import InfluxDBClient3

from src.logger import logger
from src.settings import get_settings




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
    table = client.query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox'",
        language="sql",
    )
    if table is None or len(table) == 0:
        logger.debug("no metrics found in database")
        return []
    names = [row["table_name"] for row in table.to_pylist()]
    logger.debug("metric names fetched", count=len(names))
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
    for metric in metrics:
        try:
            table = client.query(
                f"SELECT * FROM \"{metric}\" WHERE time >= $start AND time <= $end ORDER BY time ASC",
                language="sql",
                query_parameters={"start": from_utc, "end": to_utc},
            )
            rows = table.to_pylist() if table is not None and len(table) > 0 else []
            logger.debug("metric query result", metric=metric, rows=len(rows))
            results[metric] = rows
        except Exception as exc:
            logger.error("metric query failed", metric=metric, exc_info=exc)
            results[metric] = []
    return results
