from datetime import date

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderResult
from app.ai.factory import build_provider
from app.ai.rules import RuleBasedInsightProvider
from app.api.deps import get_insight_provider
from app.core.config import Settings
from app.main import app
from app.schemas.insights import InsightMetrics

METRICS = InsightMetrics(
    as_of=date(2025, 5, 19),
    interval="month",
    current_period_revenue=150.0,
    previous_period_revenue=100.0,
    change_percent=50.0,
    top_categories=[{"category": "Gadgets", "revenue": 150.0}],
    low_stock=[{"product_id": 3, "product_name": "Gizmo X", "quantity": 5}],
    low_stock_threshold=10,
)


class ExplodingProvider:
    name = "exploding"

    async def write(self, metrics: InsightMetrics) -> ProviderResult:
        raise RuntimeError("no API key, no network, no luck")


@pytest.mark.asyncio
async def test_rule_based_headline_quotes_the_measured_figures() -> None:
    result = await RuleBasedInsightProvider().write(METRICS)
    assert result.headline == (
        "Revenue so far this month is 150.00, up 50.00% on the previous month (100.00)."
    )
    assert "Gadgets 150.00" in result.bullets[0]
    assert "Gizmo X (5)" in result.bullets[1]


@pytest.mark.asyncio
async def test_rule_based_writer_handles_an_empty_store() -> None:
    empty = METRICS.model_copy(
        update={
            "current_period_revenue": 0.0,
            "previous_period_revenue": 0.0,
            "change_percent": None,
            "top_categories": [],
            "low_stock": [],
        }
    )
    result = await RuleBasedInsightProvider().write(empty)
    assert result.headline == "No revenue recorded this month or last."
    assert result.bullets[0] == "No sales have been recorded yet."
    assert "No product is below the low-stock threshold of 10." in result.bullets


def test_factory_defaults_to_the_rule_based_writer() -> None:
    provider = build_provider(Settings(insight_provider="rules"))
    assert provider.name == "rules"


def test_factory_falls_back_when_no_key_is_configured() -> None:
    provider = build_provider(
        Settings(insight_provider="anthropic", anthropic_api_key=None)
    )
    assert provider.name == "rules"


@pytest.mark.asyncio
async def test_briefing_endpoint_reports_real_numbers(
    client: AsyncClient, stocked_product: dict
) -> None:
    await client.post(
        "/sales/",
        json={
            "product_id": stocked_product["id"],
            "quantity_sold": 5,
            "sale_date": "2025-05-10",
            "total_amount": "150.00",
        },
    )
    response = await client.get(
        "/insights/", params={"interval": "month", "on": "2025-05-19"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "rules"
    assert body["metrics"]["current_period_revenue"] == 150.0
    assert body["metrics"]["top_categories"] == [
        {"category": "Gadgets", "revenue": 150.0}
    ]
    assert "150.00" in body["headline"]


@pytest.mark.asyncio
async def test_briefing_falls_back_when_the_provider_fails(
    client: AsyncClient, stocked_product: dict
) -> None:
    app.dependency_overrides[get_insight_provider] = ExplodingProvider
    try:
        response = await client.get(
            "/insights/", params={"interval": "month", "on": "2025-05-19"}
        )
    finally:
        app.dependency_overrides.pop(get_insight_provider)
    assert response.status_code == 200
    assert response.json()["provider"] == "rules"
    assert response.json()["headline"]
