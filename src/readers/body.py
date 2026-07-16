from datetime import date

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import avg, daily_metric
from src.summary_schemas import Body, DailyMetric


def read_body(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
    n: int,
) -> Body:
    weight_daily = daily_metric(
        client, "weight_body_mass", "qty", "AVG", period_start, period_end, n
    )
    fat_daily = daily_metric(
        client, "body_fat_percentage", "qty", "AVG", period_start, period_end, n
    )

    weight = (
        DailyMetric(daily=weight_daily, avg=avg(weight_daily))
        if any(v is not None for v in weight_daily)
        else None
    )
    fat = (
        DailyMetric(daily=fat_daily, avg=avg(fat_daily))
        if any(v is not None for v in fat_daily)
        else None
    )

    return Body(weight_kg=weight, body_fat_pct=fat)
