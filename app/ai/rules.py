"""The deterministic briefing writer.

Every sentence is assembled from figures the caller measured, so the output
is reproducible and testable. This is also the fallback whenever a model
provider is unavailable or errors.
"""

from app.ai.base import ProviderResult
from app.schemas.insights import InsightMetrics

TOP_CATEGORIES_NAMED = 3
LOW_STOCK_NAMED = 5


class RuleBasedInsightProvider:
    name = "rules"

    async def write(self, metrics: InsightMetrics) -> ProviderResult:
        return ProviderResult(
            headline=self._headline(metrics), bullets=self._bullets(metrics)
        )

    @staticmethod
    def _headline(m: InsightMetrics) -> str:
        current = f"{m.current_period_revenue:,.2f}"
        if m.current_period_revenue == 0 and m.previous_period_revenue == 0:
            return f"No revenue recorded this {m.interval} or last."
        if m.change_percent is None:
            return (
                f"Revenue so far this {m.interval} is {current}, "
                f"with no revenue in the previous {m.interval} to compare against."
            )
        direction = "up" if m.change_percent >= 0 else "down"
        return (
            f"Revenue so far this {m.interval} is {current}, "
            f"{direction} {abs(m.change_percent):,.2f}% on the previous {m.interval} "
            f"({m.previous_period_revenue:,.2f})."
        )

    @staticmethod
    def _bullets(m: InsightMetrics) -> list[str]:
        bullets: list[str] = []

        if m.top_categories:
            named = m.top_categories[:TOP_CATEGORIES_NAMED]
            parts = [
                f"{row['category'] or 'uncategorised'} {row['revenue']:,.2f}"
                for row in named
            ]
            bullets.append("Revenue by category: " + ", ".join(parts) + ".")
        else:
            bullets.append("No sales have been recorded yet.")

        if m.low_stock:
            named = m.low_stock[:LOW_STOCK_NAMED]
            parts = [f"{row['product_name']} ({row['quantity']})" for row in named]
            more = len(m.low_stock) - len(named)
            tail = f", and {more} more" if more > 0 else ""
            bullets.append(
                f"{len(m.low_stock)} product(s) below the low-stock threshold of "
                f"{m.low_stock_threshold}: " + ", ".join(parts) + tail + "."
            )
        else:
            bullets.append(
                f"No product is below the low-stock threshold of "
                f"{m.low_stock_threshold}."
            )

        if m.change_percent is not None and m.change_percent < 0:
            bullets.append(
                f"This {m.interval} is behind the previous one - the gap is "
                f"{m.previous_period_revenue - m.current_period_revenue:,.2f}."
            )
        return bullets
