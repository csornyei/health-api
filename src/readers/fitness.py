from datetime import date

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import query, ts, ts_end
from src.summary_schemas import Fitness


def read_fitness(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
) -> Fitness:
    current_rows = query(
        client,
        'SELECT qty FROM "vo2_max" WHERE time <= $end ORDER BY time DESC LIMIT 1',
        {"end": ts_end(period_end)},
    )
    prior_rows = query(
        client,
        'SELECT qty FROM "vo2_max" WHERE time < $start ORDER BY time DESC LIMIT 1',
        {"start": ts(period_start)},
    )

    current = float(current_rows[0]["qty"]) if current_rows else None
    prior = float(prior_rows[0]["qty"]) if prior_rows else None
    delta = (
        round(current - prior, 2) if current is not None and prior is not None else None
    )

    return Fitness(vo2_max_current=current, vo2_max_prior=prior, vo2_max_delta=delta)
