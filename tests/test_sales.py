import pytest
from httpx import AsyncClient


async def _record(client: AsyncClient, product_id: int, **overrides) -> dict:
    payload = {"product_id": product_id, "quantity_sold": 2, "sale_date": "2025-05-19"}
    payload.update(overrides)
    response = await client.post("/sales/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_sale_is_priced_from_the_product(
    client: AsyncClient, stocked_product: dict
) -> None:
    sale = await _record(client, stocked_product["id"], quantity_sold=3)
    assert float(sale["total_amount"]) == 59.97


@pytest.mark.asyncio
async def test_explicit_total_is_kept(
    client: AsyncClient, stocked_product: dict
) -> None:
    sale = await _record(client, stocked_product["id"], total_amount="10.00")
    assert float(sale["total_amount"]) == 10.00


@pytest.mark.asyncio
async def test_sale_draws_down_stock_and_writes_a_log(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(client, stocked_product["id"], quantity_sold=4)

    levels = await client.get("/inventory/")
    assert levels.json()["items"][0]["quantity"] == 96

    logs = await client.get(f"/inventory/logs/{stocked_product['id']}")
    movements = [item["quantity_change"] for item in logs.json()["items"]]
    assert -4 in movements


@pytest.mark.asyncio
async def test_sale_beyond_stock_is_rejected(
    client: AsyncClient, stocked_product: dict
) -> None:
    response = await client.post(
        "/sales/",
        json={
            "product_id": stocked_product["id"],
            "quantity_sold": 101,
            "sale_date": "2025-05-19",
        },
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["on_hand"] == 100
    assert details["requested"] == 101


@pytest.mark.asyncio
async def test_total_too_large_to_store_is_rejected_before_stock_moves(
    client: AsyncClient,
) -> None:
    product = await client.post(
        "/products/", json={"name": "Bulk lot", "price": "99999999.99"}
    )
    product_id = product.json()["id"]
    await client.post("/inventory/", json={"product_id": product_id, "quantity": 5})

    response = await client.post(
        "/sales/",
        json={"product_id": product_id, "quantity_sold": 2, "sale_date": "2025-05-19"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["max_total"] == "99999999.99"
    levels = await client.get("/inventory/")
    assert levels.json()["items"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_rejected_sale_leaves_no_trace(
    client: AsyncClient, stocked_product: dict
) -> None:
    await client.post(
        "/sales/",
        json={
            "product_id": stocked_product["id"],
            "quantity_sold": 101,
            "sale_date": "2025-05-19",
        },
    )
    sales = await client.get("/sales/")
    assert sales.json()["total"] == 0
    levels = await client.get("/inventory/")
    assert levels.json()["items"][0]["quantity"] == 100


@pytest.mark.asyncio
async def test_sale_for_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.post(
        "/sales/",
        json={"product_id": 999, "quantity_sold": 1, "sale_date": "2025-05-19"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_inactive_product_cannot_be_sold(
    client: AsyncClient, stocked_product: dict
) -> None:
    await client.delete(f"/products/{stocked_product['id']}")
    response = await client.post(
        "/sales/",
        json={
            "product_id": stocked_product["id"],
            "quantity_sold": 1,
            "sale_date": "2025-05-19",
        },
    )
    assert response.status_code == 409
    assert "inactive" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_sale_without_a_stock_record_is_404(
    client: AsyncClient, product: dict
) -> None:
    response = await client.post(
        "/sales/",
        json={
            "product_id": product["id"],
            "quantity_sold": 1,
            "sale_date": "2025-05-19",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sales_are_filtered_by_date_window(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(client, stocked_product["id"], sale_date="2025-05-01")
    await _record(client, stocked_product["id"], sale_date="2025-05-19")

    window = await client.get(
        "/sales/", params={"start_date": "2025-05-10", "end_date": "2025-05-31"}
    )
    assert window.json()["total"] == 1


@pytest.mark.asyncio
async def test_sales_are_filtered_by_category(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(client, stocked_product["id"])
    assert (await client.get("/sales/", params={"category": "Gadgets"})).json()[
        "total"
    ] == 1
    assert (await client.get("/sales/", params={"category": "Tools"})).json()[
        "total"
    ] == 0


@pytest.mark.asyncio
async def test_revenue_summary_buckets_by_month(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(
        client, stocked_product["id"], sale_date="2025-04-02", total_amount="100.00"
    )
    await _record(
        client, stocked_product["id"], sale_date="2025-05-02", total_amount="40.00"
    )
    await _record(
        client, stocked_product["id"], sale_date="2025-05-19", total_amount="60.00"
    )

    body = (await client.get("/sales/summary", params={"interval": "month"})).json()
    assert [(row["period"], float(row["revenue"])) for row in body] == [
        ("2025-04", 100.0),
        ("2025-05", 100.0),
    ]


@pytest.mark.asyncio
async def test_revenue_summary_labels_iso_weeks_across_new_year(
    client: AsyncClient, stocked_product: dict
) -> None:
    for sale_date in ("2024-12-29", "2024-12-30", "2025-01-05", "2027-01-01"):
        await _record(
            client, stocked_product["id"], sale_date=sale_date, total_amount="10.00"
        )

    body = (await client.get("/sales/summary", params={"interval": "week"})).json()
    assert [(row["period"], float(row["revenue"])) for row in body] == [
        ("2024-W52", 10.0),
        ("2025-W01", 20.0),
        ("2026-W53", 10.0),
    ]


@pytest.mark.asyncio
async def test_revenue_summary_rejects_an_unknown_interval(
    client: AsyncClient,
) -> None:
    response = await client.get("/sales/summary", params={"interval": "fortnight"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_revenue_by_category(client: AsyncClient, stocked_product: dict) -> None:
    await _record(client, stocked_product["id"], total_amount="30.00")
    body = (await client.get("/sales/summary_by_category")).json()
    assert body == [{"category": "Gadgets", "revenue": "30.00"}]


@pytest.mark.asyncio
async def test_compare_reports_the_change(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(
        client, stocked_product["id"], sale_date="2025-04-10", total_amount="100.00"
    )
    await _record(
        client, stocked_product["id"], sale_date="2025-05-10", total_amount="150.00"
    )

    body = (
        await client.get(
            "/sales/compare", params={"interval": "month", "on": "2025-05-19"}
        )
    ).json()
    assert float(body["current_period_revenue"]) == 150.0
    assert float(body["previous_period_revenue"]) == 100.0
    assert body["change_percent"] == 50.0
    assert body["current_period_start"] == "2025-05-01"


@pytest.mark.asyncio
async def test_compare_has_no_percentage_without_a_baseline(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(
        client, stocked_product["id"], sale_date="2025-05-10", total_amount="150.00"
    )
    body = (
        await client.get(
            "/sales/compare", params={"interval": "month", "on": "2025-05-19"}
        )
    ).json()
    assert body["change_percent"] is None


@pytest.mark.asyncio
async def test_csv_export_has_a_header_and_a_row(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(client, stocked_product["id"], quantity_sold=3)
    response = await client.get("/sales/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0] == (
        "id,sale_date,product_id,product_name,category,quantity_sold,total_amount"
    )
    assert lines[1].endswith("Widget A,Gadgets,3,59.97")


@pytest.mark.asyncio
async def test_csv_export_neutralises_formula_like_text(client: AsyncClient) -> None:
    product = await client.post(
        "/products/",
        json={"name": '=HYPERLINK("x")', "category": "@ops", "price": "1.00"},
    )
    product_id = product.json()["id"]
    await client.post("/inventory/", json={"product_id": product_id, "quantity": 1})
    await _record(client, product_id, quantity_sold=1)

    row = (await client.get("/sales/export.csv")).text.strip().splitlines()[1]
    assert "'=HYPERLINK" in row
    assert ",'@ops," in row


@pytest.mark.asyncio
async def test_csv_export_applies_the_list_filters(
    client: AsyncClient, stocked_product: dict
) -> None:
    await _record(client, stocked_product["id"], sale_date="2025-05-01")
    await _record(client, stocked_product["id"], sale_date="2025-05-19")

    in_window = await client.get(
        "/sales/export.csv",
        params={"start_date": "2025-05-10", "category": "Gadgets"},
    )
    assert len(in_window.text.strip().splitlines()) == 2
    other_category = await client.get("/sales/export.csv", params={"category": "Tools"})
    assert len(other_category.text.strip().splitlines()) == 1
