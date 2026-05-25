import src.logger
from fastapi import FastAPI
from src.logger import logger
from src.routers.health import router as health_router
from src.settings import get_settings

app = FastAPI()
app.include_router(health_router, prefix="/api/v1")

settings = get_settings()
logger.info("startup", influxdb_host=settings.influxdb_host, influxdb_database=settings.influxdb_database)
