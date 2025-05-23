"""API-key authentication for mutating endpoints."""

import logging
import secrets

from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError

logger = logging.getLogger(__name__)


def require_api_key(request: Request) -> None:
    """FastAPI dependency guarding writes.

    If ``ADMIN_API_KEY`` is unset the guard is a no-op, so a reviewer can run
    the API with no configuration at all. The startup log says so out loud.
    """
    settings: Settings = get_settings()
    if settings.admin_api_key is None:
        return
    presented = request.headers.get(settings.api_key_header)
    if presented is None or not secrets.compare_digest(
        presented, settings.admin_api_key
    ):
        raise UnauthorizedError(f"Missing or invalid {settings.api_key_header} header.")


def log_auth_mode() -> None:
    settings = get_settings()
    if settings.admin_api_key is None:
        logger.warning(
            "ADMIN_API_KEY is not set - write endpoints are unauthenticated."
        )
