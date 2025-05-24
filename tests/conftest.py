"""Test harness.

Every test runs against a fresh in-memory SQLite database. That is only
possible because no query in the project hard-codes MySQL syntax - the
period bucketing goes through the dialect registry in
``app.repositories.periods``.
"""

from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Inventory, InventoryLog, Product, Sale  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
def today() -> date:
    return date(2025, 5, 19)


@pytest.fixture
def yesterday(today: date) -> date:
    return today - timedelta(days=1)


@pytest_asyncio.fixture
async def product(client: AsyncClient) -> dict:
    response = await client.post(
        "/products/",
        json={
            "name": "Widget A",
            "category": "Gadgets",
            "price": "19.99",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture
async def stocked_product(client: AsyncClient, product: dict) -> dict:
    response = await client.post(
        "/inventory/", json={"product_id": product["id"], "quantity": 100}
    )
    assert response.status_code == 201, response.text
    return product
