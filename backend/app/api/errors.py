from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.common import ApiErrorBody, ApiErrorCode, ApiErrorEnvelope


class ApiError(Exception):
    def __init__(
        self,
        code: ApiErrorCode,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(
    code: ApiErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = ApiErrorEnvelope(
        error=ApiErrorBody(code=code, message=message, details=details or {}),
    )
    return envelope.model_dump(mode="json")


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


def json_safe(value: Any) -> Any:
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


async def validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            ApiErrorCode.INVALID_REQUEST,
            "Request validation failed.",
            {"errors": json_safe(exc.errors())},
        ),
    )


async def http_exception_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    if exc.status_code == 404:
        code = ApiErrorCode.INVALID_REQUEST
        message = "Not found."
    else:
        code = ApiErrorCode.INTERNAL_ERROR
        message = str(exc.detail) if exc.detail else "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(code, message),
    )


async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_payload(
            ApiErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred.",
        ),
    )


def not_implemented(code: ApiErrorCode, message: str) -> ApiError:
    return ApiError(
        code=code,
        message=message,
        status_code=501,
        details={"reason": "not_implemented"},
    )
