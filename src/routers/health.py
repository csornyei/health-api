from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from influxdb_client_3 import InfluxDBClient3

from src.influxdb import get_all_metric_names, get_influxdb_client, query_metrics
from src.logger import logger
from src.schemas import MetricsExport, NutritionExport, WorkoutsExport
from src.writers import write_metrics, write_workouts

router = APIRouter(prefix="/health")


@router.get("/metrics", tags=["metrics"])
def list_metrics(
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    try:
        names = get_all_metric_names(db)
    except Exception as exc:
        logger.error("failed to list metric names", exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to reach database") from exc
    logger.info("list metrics", count=len(names))
    return {"metrics": names}


@router.get("/", tags=["metrics"])
def get_health_metrics(
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
    from_: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    metrics: Annotated[str | None, Query()] = None,
) -> dict:
    metric_list = [m.strip() for m in metrics.split(",")] if metrics else []
    logger.info("get health metrics", from_=str(from_), to=str(to), metrics=metric_list or "all")
    try:
        data = query_metrics(db, metric_list, from_, to)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("failed to query metrics", from_=str(from_), to=str(to), metrics=metric_list or "all", exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to query metrics") from exc
    return {"data": data}


@router.post("/metrics", tags=["ingest"])
def ingest_metrics(
    export: MetricsExport,
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    count = len(export.data.metrics)
    logger.info("metrics export received", metrics_count=count)
    try:
        write_metrics(db, export.data.metrics)
    except Exception as exc:
        logger.error("failed to write metrics", metrics_count=count, exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to write metrics to database") from exc
    return {"written": {"metrics": count}}


@router.post("/workouts", tags=["ingest"])
def ingest_workouts(
    export: WorkoutsExport,
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    count = len(export.data.workouts)
    logger.info("workouts export received", workouts_count=count)
    try:
        write_workouts(db, export.data.workouts)
    except Exception as exc:
        logger.error("failed to write workouts", workouts_count=count, exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to write workouts to database") from exc
    return {"written": {"workouts": count}}


@router.post("/nutrition", tags=["ingest"])
def ingest_nutrition(
    export: NutritionExport,
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    count = len(export.data.metrics)
    logger.info("nutrition export received", metrics_count=count)
    try:
        write_metrics(db, export.data.metrics)
    except Exception as exc:
        logger.error("failed to write nutrition metrics", metrics_count=count, exc_info=exc)
        raise HTTPException(status_code=503, detail="Failed to write nutrition metrics to database") from exc
    return {"written": {"nutrition_metrics": count}}