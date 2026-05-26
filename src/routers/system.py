from typing import Annotated

from fastapi import APIRouter, Depends
from influxdb_client_3 import InfluxDBClient3

from src.influxdb import get_influxdb_client

router = APIRouter()


@router.get("/healthz")
def healthcheck(db: Annotated[InfluxDBClient3, Depends(get_influxdb_client)]) -> dict:
    db.query("SELECT 1", language="sql")
    return {"status": "ok"}


@router.get("/readyz")
def readiness() -> dict:
    return {"status": "ok"}
