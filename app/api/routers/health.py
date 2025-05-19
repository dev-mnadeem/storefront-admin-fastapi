from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.db.session import get_db
from app.schemas.common import HealthStatus

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthStatus)
async def health(db: AsyncSession = Depends(get_db)) -> HealthStatus:
    """Liveness plus a real round trip to the database."""
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - reported, not raised
        database = "unavailable"
    return HealthStatus(
        status="ok" if database == "ok" else "degraded",
        database=database,
        version=__version__,
    )
