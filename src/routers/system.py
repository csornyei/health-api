from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from influxdb_client_3 import InfluxDBClient3

from src.influxdb import get_influxdb_client
from src.logger import logger

router = APIRouter()


@router.get("/healthz", tags=["system"])
def healthcheck(db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)]) -> dict:
    try:
        db.query("SELECT 1", language="sql")
    except Exception as exc:
        logger.error("healthcheck: database ping failed", exc_info=exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}


@router.get("/readyz", tags=["system"])
def readiness() -> dict:
    return {"status": "ok"}
