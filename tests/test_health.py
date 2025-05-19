import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


@pytest.mark.asyncio
async def test_openapi_document_builds(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "/sales/export.csv" in response.json()["paths"]
