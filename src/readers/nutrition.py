from datetime import date

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import daily_metric
from src.summary_schemas import Nutrition, NutritionStat


def read_nutrition(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
    n: int,
) -> Nutrition:
    def _stat(measurement: str) -> NutritionStat:
        daily = daily_metric(
            client, measurement, "qty", "SUM", period_start, period_end, n
        )
        populated = [v for v in daily if v is not None]
        total = round(sum(populated), 2) if populated else None
        return NutritionStat(daily=daily, total=total)

    return Nutrition(
        vitamin_b12=_stat("vitamin_b12"),
        saturated_fat=_stat("saturated_fat"),
        total_fat=_stat("total_fat"),
        fiber=_stat("fiber"),
        protein=_stat("protein"),
        dietary_energy=_stat("dietary_energy"),
        carbohydrates=_stat("carbohydrates"),
    )
