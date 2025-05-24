import pytest
from httpx import AsyncClient

from app.core import security
from app.core.config import Settings


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "s3cret-admin-key"
    monkeypatch.setattr(security, "get_settings", lambda: Settings(admin_api_key=key))
    return key


@pytest.mark.asyncio
async def test_writes_are_open_when_no_key_is_configured(
    client: AsyncClient,
) -> None:
    response = await client.post("/products/", json={"name": "Open", "price": "1.00"})
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_write_without_the_header_is_401(
    client: AsyncClient, api_key: str
) -> None:
    response = await client.post(
        "/products/", json={"name": "Guarded", "price": "1.00"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_write_with_the_header_succeeds(
    client: AsyncClient, api_key: str
) -> None:
    response = await client.post(
        "/products/",
        json={"name": "Guarded", "price": "1.00"},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_reads_never_need_the_header(client: AsyncClient, api_key: str) -> None:
    assert (await client.get("/products/")).status_code == 200
    assert (await client.get("/health")).status_code == 200


def test_blank_api_key_env_var_means_unset() -> None:
    """`ADMIN_API_KEY=` in a compose file must not become a valid key."""
    assert Settings(admin_api_key="").admin_api_key is None
    assert Settings(anthropic_api_key="  ").anthropic_api_key is None
