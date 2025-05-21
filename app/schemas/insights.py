from datetime import date

from pydantic import BaseModel


class InsightMetrics(BaseModel):
    """The figures the briefing is written from - always returned."""

    as_of: date
    interval: str
    current_period_revenue: float
    previous_period_revenue: float
    change_percent: float | None
    top_categories: list[dict]
    low_stock: list[dict]
    low_stock_threshold: int


class Briefing(BaseModel):
    provider: str
    headline: str
    bullets: list[str]
    metrics: InsightMetrics
