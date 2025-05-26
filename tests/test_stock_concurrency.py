import asyncio
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import ConflictError
from app.db.base import Base
from app.models import Inventory, InventoryLog, Product, Sale
from app.repositories.inventory import InventoryRepository
from app.repositories.products import ProductRepository
from app.repositories.sales import SaleRepository
from app.schemas.sales import SaleCreate
from app.services.inventory import InventoryService
from app.services.products import ProductService
from app.services.sales import SaleService


@pytest.mark.asyncio
async def test_independent_requests_cannot_sell_the_same_last_unit(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'stock.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        product = Product(name="Last unit", price=Decimal("10.00"), is_active=True)
        session.add(product)
        await session.flush()
        product_id = product.id
        session.add(Inventory(product_id=product_id, quantity=1))
        await session.commit()

    ready = asyncio.Event()
    arrivals = 0

    class SynchronizedProducts(ProductService):
        async def get(self, product_id):
            nonlocal arrivals
            product = await super().get(product_id)
            arrivals += 1
            if arrivals == 2:
                ready.set()
            await ready.wait()
            return product

    async def buy():
        async with sessions() as session:
            products = SynchronizedProducts(session, ProductRepository(session))
            inventory = InventoryService(
                session, InventoryRepository(session), products
            )
            sales = SaleService(session, SaleRepository(session), products, inventory)
            try:
                await sales.record(
                    SaleCreate(
                        product_id=product_id,
                        quantity_sold=1,
                        sale_date=date(2025, 5, 19),
                    )
                )
                return "sold"
            except ConflictError:
                await session.rollback()
                return "conflict"

    try:
        outcomes = await asyncio.wait_for(asyncio.gather(buy(), buy()), timeout=10)
        assert sorted(outcomes) == ["conflict", "sold"]
        async with sessions() as session:
            assert await session.scalar(select(Inventory.quantity)) == 0
            assert await session.scalar(select(func.count()).select_from(Sale)) == 1
            assert (
                await session.scalar(select(func.count()).select_from(InventoryLog))
                == 1
            )
    finally:
        await engine.dispose()
