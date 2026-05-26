import calendar
from datetime import date, timedelta
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from influxdb_client_3 import InfluxDBClient3

from src.influxdb import get_influxdb_client
from src.logger import logger
from src.readers import read_energy, read_fitness, read_recovery, read_sleep, read_training
from src.summary_schemas import Body, SummaryMeta, SummaryResponse

router = APIRouter(prefix="/health")


class SummaryType(str, Enum):
    week = "week"
    twoweeks = "twoweeks"
    month = "month"


def _compute_period(ref: date, summary_type: SummaryType) -> tuple[date, date]:
    if summary_type == SummaryType.month:
        period_start = ref.replace(day=1)
        period_end = ref.replace(day=calendar.monthrange(ref.year, ref.month)[1])
    elif summary_type == SummaryType.twoweeks:
        period_start = ref - timedelta(days=13)
        period_end = ref
    else:
        period_start = ref - timedelta(days=6)
        period_end = ref
    return period_start, period_end


@router.get("/summary", tags=["summary"])
def get_summary(
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
    end_date: Annotated[date, Query()],
    summary_type: Annotated[SummaryType, Query()],
) -> SummaryResponse:
    period_start, period_end = _compute_period(end_date, summary_type)
    n = (period_end - period_start).days + 1
    logger.info(
        "summary requested",
        summary_type=summary_type,
        period_start=str(period_start),
        period_end=str(period_end),
        days=n,
    )

    try:
        training, active_daily, _ = read_training(db, period_start, period_end, n)
        energy = read_energy(db, active_daily, period_start, period_end, n)
        recovery = read_recovery(db, summary_type.value, period_start, period_end, n)
        sleep, sleep_summary = read_sleep(db, period_start, period_end)
        fitness = read_fitness(db, period_start, period_end)
    except Exception as exc:
        logger.error("summary query failed", exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to build summary") from exc

    return SummaryResponse(
        meta=SummaryMeta(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            summary_type=summary_type.value,
            days=n,
        ),
        recovery=recovery,
        sleep=sleep,
        sleep_summary=sleep_summary,
        training=training,
        energy=energy,
        fitness=fitness,
        body=Body(),
    )