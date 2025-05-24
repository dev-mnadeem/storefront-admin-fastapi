import logging
from datetime import date

from app.ai.base import InsightProvider
from app.repositories.periods import period_bounds
from app.schemas.insights import Briefing, InsightMetrics
from app.services.inventory import InventoryService
from app.services.sales import SaleService

logger = logging.getLogger(__name__)

TOP_CATEGORY_LIMIT = 5
LOW_STOCK_LIMIT = 20


class InsightService:
    """Measures the dashboard's headline figures, then has them written up."""

    def __init__(
        self,
        sales: SaleService,
        inventory: InventoryService,
        provider: InsightProvider,
        fallback: InsightProvider,
    ) -> None:
        self.sales = sales
        self.inventory = inventory
        self.provider = provider
        self.fallback = fallback

    async def measure(self, interval: str, today: date) -> InsightMetrics:
        comparison = await self.sales.compare(interval, today)
        current_start, _, _ = period_bounds(interval, today)
        categories = await self.sales.repo.revenue_by_category(
            start_date=current_start, end_date=today, limit=TOP_CATEGORY_LIMIT
        )
        low_stock = await self.inventory.low_stock_rows(LOW_STOCK_LIMIT)
        return InsightMetrics(
            as_of=today,
            interval=interval,
            current_period_revenue=float(comparison.current_period_revenue),
            previous_period_revenue=float(comparison.previous_period_revenue),
            change_percent=comparison.change_percent,
            top_categories=[
                {"category": row.category, "revenue": float(row.revenue or 0)}
                for row in categories
            ],
            low_stock=[
                {
                    "product_id": row.product_id,
                    "product_name": row.product_name,
                    "quantity": row.quantity,
                }
                for row in low_stock
            ],
            low_stock_threshold=self.inventory.levels_threshold,
        )

    async def briefing(self, interval: str, today: date) -> Briefing:
        metrics = await self.measure(interval, today)
        provider = self.provider
        try:
            result = await provider.write(metrics)
        except Exception:  # noqa: BLE001 - the endpoint must still answer
            logger.exception(
                "insight provider %r failed - falling back to %r",
                provider.name,
                self.fallback.name,
            )
            provider = self.fallback
            result = await provider.write(metrics)
        return Briefing(
            provider=provider.name,
            headline=result.headline,
            bullets=result.bullets,
            metrics=metrics,
        )
