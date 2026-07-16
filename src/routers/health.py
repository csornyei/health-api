from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from influxdb_client_3 import InfluxDBClient3

from src.adapters.workoutdoors import (ParsedWorkouts, WorkoutParseError,
                                       parse_workouts_payload)
from src.influxdb import (get_all_metric_names, get_influxdb_client,
                          query_metrics)
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
    logger.info(
        "get health metrics", from_=str(from_), to=str(to), metrics=metric_list or "all"
    )
    try:
        data = query_metrics(db, metric_list, from_, to)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "failed to query metrics",
            from_=str(from_),
            to=str(to),
            metrics=metric_list or "all",
            exc_info=exc,
        )
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
        raise HTTPException(
            status_code=503, detail="Failed to write metrics to database"
        ) from exc
    return {"written": {"metrics": count}}


async def parse_workouts_request(request: Request) -> ParsedWorkouts:
    try:
        payload = await request.json()
    except ValueError as exc:
        logger.warning(
            "workouts payload is not valid json",
            content_type=request.headers.get("content-type"),
            content_length=request.headers.get("content-length"),
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
        ) from exc

    try:
        return parse_workouts_payload(payload)
    except WorkoutParseError as exc:
        top_level_keys = (
            list(payload.keys())[:20] if isinstance(payload, dict) else None
        )
        workout_keys = None
        if isinstance(payload, dict):
            workouts = payload.get("data", {}).get("workouts", [])
            if workouts and isinstance(workouts[0], dict):
                workout_keys = list(workouts[0].keys())[:40]
        logger.warning(
            "unsupported workouts payload",
            parsers=["health_auto_export", "workoutdoors"],
            errors=exc.errors,
            top_level_keys=top_level_keys,
            workout_keys=workout_keys,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Unsupported workout payload", "parsers": exc.errors},
        ) from exc


@router.post("/workouts", tags=["ingest"])
def ingest_workouts(
    parsed: Annotated[ParsedWorkouts, Depends(parse_workouts_request)],
    db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)],
) -> dict:
    export = parsed.export
    count = len(export.data.workouts)
    if count == 0:
        logger.warning(
            "empty workouts export rejected",
            workout_payload_format=parsed.payload_format,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No workouts provided"
        )

    sample = [
        {"id": workout.id, "name": workout.name, "start": workout.start}
        for workout in export.data.workouts[:3]
    ]
    nested_counts = {
        "heart_rate_points": sum(
            len(workout.heartRateData) for workout in export.data.workouts
        ),
        "heart_rate_recovery_points": sum(
            len(workout.heartRateRecovery) for workout in export.data.workouts
        ),
        "active_energy_points": sum(
            len(workout.activeEnergy) for workout in export.data.workouts
        ),
        "distance_points": sum(
            len(workout.walkingAndRunningDistance) for workout in export.data.workouts
        ),
        "step_points": sum(len(workout.stepCount) for workout in export.data.workouts),
    }
    logger.info(
        "workouts export received",
        workout_payload_format=parsed.payload_format,
        workouts_count=count,
        sample_workouts=sample,
        ignored_fields=parsed.ignored_fields,
        **nested_counts,
    )
    try:
        write_workouts(db, export.data.workouts)
    except Exception as exc:
        logger.error(
            "failed to write workouts",
            workout_payload_format=parsed.payload_format,
            workouts_count=count,
            sample_workouts=sample,
            ignored_fields=parsed.ignored_fields,
            **nested_counts,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=503, detail="Failed to write workouts to database"
        ) from exc
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
        logger.error(
            "failed to write nutrition metrics", metrics_count=count, exc_info=exc
        )
        raise HTTPException(
            status_code=503, detail="Failed to write nutrition metrics to database"
        ) from exc
    return {"written": {"nutrition_metrics": count}}
