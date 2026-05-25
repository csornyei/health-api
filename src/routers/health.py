from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from influxdb_client_3 import InfluxDBClient3

from src.influxdb import get_all_metric_names, get_influxdb_client, query_metrics
from src.logger import logger
from src.schemas import HealthExport
from src.writers import write_metrics, write_workouts

router = APIRouter(prefix="/health")


@router.get("/metrics")
def list_metrics(
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    names = get_all_metric_names(db)
    logger.info("list metrics", count=len(names))
    return {"metrics": names}


@router.get("/")
def get_health_metrics(
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    metrics: Annotated[str | None, Query()] = None,
) -> dict:
    metric_list = [m.strip() for m in metrics.split(",")] if metrics else []
    logger.info("get health metrics", from_=str(from_), to=str(to), metrics=metric_list or "all")
    data = query_metrics(db, metric_list, from_, to)
    return {"data": data}


@router.post("/")
def parse_health_export(
    export: HealthExport,
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    logger.info(
        "health export received",
        metrics_count=len(export.data.metrics),
        workouts_count=len(export.data.workouts),
    )
    write_metrics(db, export.data.metrics)
    write_workouts(db, export.data.workouts)

    return {
        "written": {
            "metrics": len(export.data.metrics),
            "workouts": len(export.data.workouts),
        }
    }
