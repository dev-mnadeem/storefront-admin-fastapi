import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_product_returns_201(client: AsyncClient) -> None:
    response = await client.post(
        "/products/",
        json={"name": "Gizmo X", "category": "Tools", "price": "9.99"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Gizmo X"
    assert float(body["price"]) == 9.99
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_name_is_a_conflict(client: AsyncClient, product: dict) -> None:
    response = await client.post(
        "/products/", json={"name": product["name"], "price": "1.00"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_price_must_be_positive(client: AsyncClient) -> None:
    response = await client.post(
        "/products/", json={"name": "Free thing", "price": "0"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.asyncio
async def test_list_is_paginated(client: AsyncClient) -> None:
    for index in range(5):
        await client.post("/products/", json={"name": f"Item {index}", "price": "1.00"})
    response = await client.get("/products/", params={"limit": 2, "offset": 1})
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 1


@pytest.mark.asyncio
async def test_limit_is_capped(client: AsyncClient) -> None:
    response = await client.get("/products/", params={"limit": 10_000})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_matches_name_case_insensitively(
    client: AsyncClient, product: dict
) -> None:
    response = await client.get("/products/", params={"search": "widget"})
    assert [item["id"] for item in response.json()["items"]] == [product["id"]]


@pytest.mark.asyncio
async def test_filter_by_category_and_active_flag(
    client: AsyncClient, product: dict
) -> None:
    await client.post(
        "/products/", json={"name": "Tool", "price": "2.00", "category": "Tools"}
    )
    gadgets = await client.get("/products/", params={"category": "Gadgets"})
    assert gadgets.json()["total"] == 1

    await client.delete(f"/products/{product['id']}")
    active = await client.get("/products/", params={"is_active": True})
    assert product["id"] not in [item["id"] for item in active.json()["items"]]


@pytest.mark.asyncio
async def test_get_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.get("/products/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_patch_updates_only_given_fields(
    client: AsyncClient, product: dict
) -> None:
    response = await client.patch(f"/products/{product['id']}", json={"price": "24.50"})
    assert response.status_code == 200
    body = response.json()
    assert float(body["price"]) == 24.50
    assert body["name"] == product["name"]


@pytest.mark.asyncio
async def test_patch_to_a_taken_name_is_a_conflict(
    client: AsyncClient, product: dict
) -> None:
    other = await client.post("/products/", json={"name": "Other", "price": "1.00"})
    response = await client.patch(
        f"/products/{other.json()['id']}", json={"name": product["name"]}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_is_a_soft_delete(client: AsyncClient, product: dict) -> None:
    response = await client.delete(f"/products/{product['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    still_there = await client.get(f"/products/{product['id']}")
    assert still_there.status_code == 200
