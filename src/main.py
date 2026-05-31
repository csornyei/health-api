from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.logger import logger
from src.routers.health import router as health_router
from src.routers.summary import router as summary_router
from src.routers.system import router as system_router
from src.routers.test import router as test_router
from src.settings import get_settings
from src.telemetry import setup_tracing

setup_tracing(service_name="health-api", settings=get_settings() )

app = FastAPI()
FastAPIInstrumentor().instrument_app(app)
app.include_router(health_router, prefix="/api/v1")
app.include_router(test_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(system_router)

settings = get_settings()
logger.info("startup", influxdb_host=settings.influxdb_host, influxdb_database=settings.influxdb_database)
