from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_insight_service
from app.repositories.periods import IntervalName
from app.schemas.insights import Briefing
from app.services.insights import InsightService

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/", response_model=Briefing)
async def briefing(
    interval: IntervalName = "month",
    on: date | None = Query(
        None, description="Treat this date as today. Defaults to the server date."
    ),
    service: InsightService = Depends(get_insight_service),
) -> Briefing:
    """A written summary of the dashboard's headline figures.

    `metrics` carries every number the prose is based on, so a client can
    render the figures itself and treat the text as a caption.
    """
    return await service.briefing(interval, on or date.today())
