"""Seed the database with a small, coherent storefront.

Run with ``python -m demo_data`` (add ``--keep`` to seed without dropping the
existing tables). Everything is written through the service layer, so the
demo data obeys the same rules the API enforces: stock is logged, sales are
priced from the product and drawn out of stock.
"""

import argparse
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import Inventory, InventoryLog, Product, Sale  # noqa: F401
from app.repositories.inventory import InventoryRepository
from app.repositories.products import ProductRepository
from app.repositories.sales import SaleRepository
from app.schemas.products import ProductCreate
from app.schemas.sales import SaleCreate
from app.services.inventory import InventoryService
from app.services.products import ProductService
from app.services.sales import SaleService

TODAY = date.today()

PRODUCTS = [
    # name, category, price, is_active, opening stock
    ("Widget A", "Gadgets", Decimal("19.99"), True, 150),
    ("Widget B", "Gadgets", Decimal("29.99"), True, 20),
    ("Gizmo X", "Tools", Decimal("9.99"), True, 5),
    ("Gizmo Y", "Tools", Decimal("14.49"), False, 0),
]

SALES = [
    # product name, units, sale date
    ("Widget A", 10, TODAY),
    ("Widget A", 5, TODAY - timedelta(days=1)),
    ("Widget B", 2, TODAY),
    ("Gizmo X", 1, TODAY - timedelta(days=7)),
    ("Widget A", 8, TODAY - timedelta(days=35)),
]


async def seed(*, reset: bool = True) -> None:
    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        products = ProductService(session, ProductRepository(session))
        inventory = InventoryService(session, InventoryRepository(session), products)
        sales = SaleService(session, SaleRepository(session), products, inventory)

        by_name: dict[str, int] = {}
        for name, category, price, is_active, stock in PRODUCTS:
            product = await products.create(
                ProductCreate(
                    name=name, category=category, price=price, is_active=is_active
                )
            )
            by_name[name] = product.id
            await inventory.open_stock(product.id, stock, "initial stock")

        for name, units, sale_date in SALES:
            await sales.record(
                SaleCreate(
                    product_id=by_name[name],
                    quantity_sold=units,
                    sale_date=sale_date,
                )
            )

    await engine.dispose()
    print(f"Seeded {len(PRODUCTS)} products and {len(SALES)} sales.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Seed without dropping the existing tables first.",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset=not args.keep))


if __name__ == "__main__":
    main()
