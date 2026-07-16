from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.logger import logger, setup_logging
from src.middleware import AccessLogMiddleware
from src.routers.health import router as health_router
from src.routers.summary import router as summary_router
from src.routers.system import router as system_router
from src.routers.test import router as test_router
from src.settings import get_settings
from src.telemetry import setup_tracing
from src.validation import validation_errors

settings = get_settings()
setup_logging(json_logs=settings.json_logs, log_level=settings.log_level)
setup_tracing(service_name="health-api", settings=settings)

app = FastAPI()
FastAPIInstrumentor().instrument_app(app)
app.add_middleware(AccessLogMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = await request.body()
    errors = validation_errors(exc.errors())
    logger.warning(
        "request validation failed",
        method=request.method,
        path=request.url.path,
        query=str(request.url.query),
        client=request.client.host if request.client else None,
        content_type=request.headers.get("content-type"),
        content_length=request.headers.get("content-length"),
        body_bytes=len(body),
        body_preview=body[:2000].decode("utf-8", errors="replace"),
        errors=errors,
    )
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "errors": errors},
    )


app.include_router(health_router, prefix="/api/v1")
app.include_router(test_router, prefix="/api/v1")
app.include_router(summary_router, prefix="/api/v1")
app.include_router(system_router)

logger.info(
    "startup",
    influxdb_host=settings.influxdb_host,
    influxdb_database=settings.influxdb_database,
)
