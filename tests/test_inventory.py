import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_open_stock_creates_the_record_and_a_log(
    client: AsyncClient, product: dict
) -> None:
    response = await client.post(
        "/inventory/", json={"product_id": product["id"], "quantity": 50}
    )
    assert response.status_code == 201, response.text
    assert response.json()["quantity"] == 50

    logs = await client.get(f"/inventory/logs/{product['id']}")
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["quantity_change"] == 50
    assert logs.json()["items"][0]["reason"] == "initial stock"


@pytest.mark.asyncio
async def test_opening_stock_twice_is_a_conflict(
    client: AsyncClient, stocked_product: dict
) -> None:
    response = await client.post(
        "/inventory/", json={"product_id": stocked_product["id"], "quantity": 5}
    )
    assert response.status_code == 409
    assert "PATCH" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_open_stock_for_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.post("/inventory/", json={"product_id": 999, "quantity": 5})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_adjustment_moves_the_level_and_is_logged(
    client: AsyncClient, stocked_product: dict
) -> None:
    response = await client.patch(
        f"/inventory/{stocked_product['id']}",
        json={"quantity_change": -30, "reason": "damaged in transit"},
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 70

    logs = await client.get(f"/inventory/logs/{stocked_product['id']}")
    reasons = [item["reason"] for item in logs.json()["items"]]
    assert "damaged in transit" in reasons
    assert logs.json()["total"] == 2


@pytest.mark.asyncio
async def test_adjustment_cannot_take_stock_negative(
    client: AsyncClient, stocked_product: dict
) -> None:
    response = await client.patch(
        f"/inventory/{stocked_product['id']}", json={"quantity_change": -101}
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["on_hand"] == 100


@pytest.mark.asyncio
async def test_zero_adjustment_is_rejected(
    client: AsyncClient, stocked_product: dict
) -> None:
    response = await client.patch(
        f"/inventory/{stocked_product['id']}", json={"quantity_change": 0}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_adjusting_a_product_without_stock_is_404(
    client: AsyncClient, product: dict
) -> None:
    response = await client.patch(
        f"/inventory/{product['id']}", json={"quantity_change": 5}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_levels_carry_the_product_name(
    client: AsyncClient, stocked_product: dict
) -> None:
    """One request is enough to render the stock table - no lookup per row."""
    response = await client.get("/inventory/")
    item = response.json()["items"][0]
    assert item["product_name"] == stocked_product["name"]
    assert item["category"] == "Gadgets"
    assert item["is_low_stock"] is False


@pytest.mark.asyncio
async def test_low_stock_filter_uses_the_threshold(
    client: AsyncClient, stocked_product: dict
) -> None:
    empty = await client.get("/inventory/", params={"low_stock": True})
    assert empty.json()["total"] == 0

    hit = await client.get("/inventory/", params={"low_stock": True, "threshold": 200})
    assert hit.json()["total"] == 1
    assert hit.json()["items"][0]["is_low_stock"] is True


@pytest.mark.asyncio
async def test_logs_for_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.get("/inventory/logs/999")
    assert response.status_code == 404
