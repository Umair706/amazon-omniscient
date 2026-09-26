"""Production middleware for logging, error handling, and request tracking."""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with timing and request ID."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start_time = time.perf_counter()

        logger.info(
            "request_started method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time

            logger.info(
                "request_completed method=%s path=%s status=%d duration=%.3fs request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration,
                request_id,
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            return response

        except Exception as exc:
            duration = time.perf_counter() - start_time
            logger.exception(
                "request_failed method=%s path=%s duration=%.3fs request_id=%s error=%s",
                request.method,
                request.url.path,
                duration,
                request_id,
                str(exc),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """Turn unhandled exceptions into structured error responses. Every one is logged.

    NOTE: ValueError is deliberately NOT mapped to 400. Pydantic's ValidationError
    is a ValueError, so a bad stored row would otherwise be reported as the
    client's fault and never logged. Input validation already answers 422 before
    any middleware runs.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except PermissionError as exc:
            logger.warning("Forbidden %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=403, content={"detail": str(exc)})
        except FileNotFoundError as exc:
            logger.warning("Not found %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=404, content={"detail": str(exc)})
        except Exception as exc:
            logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
