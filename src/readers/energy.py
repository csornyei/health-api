from datetime import date
from statistics import mean

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import daily_metric
from src.summary_schemas import Energy


def read_energy(
    client: InfluxDBClient3,
    active_daily: list[float | None],
    period_start: date,
    period_end: date,
    n: int,
) -> Energy:
    basal_daily = daily_metric(
        client, "basal_energy_burned", "qty", "SUM", period_start, period_end, n
    )
    tdee_daily: list[float | None] = [
        round(a + b, 2) if a is not None and b is not None else None
        for a, b in zip(active_daily, basal_daily)
    ]
    populated_tdee = [v for v in tdee_daily if v is not None]
    avg_tdee = int(mean(populated_tdee)) if populated_tdee else None
    return Energy(
        active_kcal_daily=active_daily,
        basal_kcal_daily=basal_daily,
        tdee_daily=tdee_daily,
        avg_tdee=avg_tdee,
    )
