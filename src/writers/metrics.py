from influxdb_client_3 import InfluxDBClient3, Point
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.logger import logger
from src.schemas import (HeartRateMetricPoint, Metric, QuantityDataPoint,
                         SleepDataPoint)
from src.writers.common import parse_ts
from src.writers.sleep import sleep_point

_tracer = trace.get_tracer(__name__)


def write_metrics(client: InfluxDBClient3, metrics: list[Metric]) -> None:
    points = []
    for metric in metrics:
        for point in metric.data:
            if isinstance(point, SleepDataPoint):
                points.append(sleep_point(metric.name, point))
            elif isinstance(point, HeartRateMetricPoint):
                points.append(_heart_rate_point(metric.name, metric.units, point))
            elif isinstance(point, QuantityDataPoint):
                points.append(_quantity_point(metric.name, metric.units, point))
    with _tracer.start_as_current_span("influxdb.write_metrics") as span:
        span.set_attribute("db.metrics_count", len(metrics))
        span.set_attribute("db.points_count", len(points))
        try:
            client.write(record=points)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
    logger.info(
        "metrics written", metrics_count=len(metrics), points_written=len(points)
    )


def _quantity_point(name: str, units: str | None, point: QuantityDataPoint) -> Point:
    return (
        Point(name)
        .tag("units", units or "")
        .field("qty", point.qty)
        .time(parse_ts(point.date))
    )


def _heart_rate_point(
    name: str, units: str | None, point: HeartRateMetricPoint
) -> Point:
    return (
        Point(name)
        .tag("units", units or "")
        .field("min", point.Min)
        .field("avg", point.Avg)
        .field("max", point.Max)
        .time(parse_ts(point.date))
    )
