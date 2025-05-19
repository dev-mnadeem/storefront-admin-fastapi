"""Domain errors and the handlers that turn them into HTTP responses.

Services raise these. Routers never build error responses by hand, so every
failure leaves the API with the same JSON shape:
``{"error": {"code": "...", "message": "...", "details": {...}}}``.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

HTTP_422 = 422


class DomainError(Exception):
    """Base class for errors that map onto an HTTP status code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class InvalidRequestError(DomainError):
    status_code = HTTP_422
    code = "invalid_request"


class UnauthorizedError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=HTTP_422,
            content=error_body(
                "invalid_request",
                "Request body or query parameters failed validation.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )
