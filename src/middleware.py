import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.logger import logger


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "unhandled request error",
                method=request.method,
                path=request.url.path,
                query=str(request.url.query),
                client=request.client.host if request.client else None,
                duration_ms=round(duration_ms, 2),
                exc_info=exc,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000

        log = logger.warning if response.status_code >= 400 else logger.info
        log(
            "access error" if response.status_code >= 400 else "access",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client=request.client.host if request.client else None,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            content_length=request.headers.get("content-length"),
            content_type=request.headers.get("content-type"),
        )

        return response
