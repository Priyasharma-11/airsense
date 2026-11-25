"""Centralised exception handling -> consistent JSON error envelope:
{"error": {"code": "...", "message": "...", "details": ...}, "request_id": "..."}"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("airsense.errors")


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(AppError):
    status_code, code = status.HTTP_404_NOT_FOUND, "not_found"


class Conflict(AppError):
    status_code, code = status.HTTP_409_CONFLICT, "conflict"


class Unauthorized(AppError):
    status_code, code = status.HTTP_401_UNAUTHORIZED, "unauthorized"


class Forbidden(AppError):
    status_code, code = status.HTTP_403_FORBIDDEN, "forbidden"


class Unprocessable(AppError):
    status_code, code = status.HTTP_422_UNPROCESSABLE_CONTENT, "unprocessable"


class ServiceUnavailable(AppError):
    status_code, code = status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable"


def _body(request: Request, code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details},
            "request_id": getattr(request.state, "request_id", None)}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status_code,
                            headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
                   for e in exc.errors()]
        return JSONResponse(_body(request, "validation_error", "Invalid request.", details),
                            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}.get(
            exc.status_code, "http_error")
        return JSONResponse(_body(request, code, str(exc.detail)), status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(_body(request, "internal_error", "An unexpected error occurred."),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
