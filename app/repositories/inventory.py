from collections.abc import Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.inventory_log import InventoryLog
from app.models.products import Product


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_product(self, product_id: int) -> Inventory | None:
        result = await self.session.execute(
            select(Inventory).where(Inventory.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def levels(
        self,
        *,
        low_stock: bool = False,
        threshold: int = 10,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Row], int]:
        """Stock joined to its product in one statement.

        Returning the product name here is what keeps a dashboard from
        issuing one extra request per row.
        """
        stmt = select(
            Inventory.product_id,
            Product.name.label("product_name"),
            Product.category,
            Inventory.quantity,
        ).join(Product, Product.id == Inventory.product_id)
        if low_stock:
            stmt = stmt.where(Inventory.quantity < threshold)

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.session.execute(
            stmt.order_by(Inventory.quantity, Inventory.product_id)
            .offset(offset)
            .limit(limit)
        )
        return result.all(), int(total or 0)

    async def add(self, product_id: int, quantity: int) -> Inventory:
        row = Inventory(product_id=product_id, quantity=quantity)
        self.session.add(row)
        await self.session.flush()
        return row

    def log(self, product_id: int, quantity_change: int, reason: str) -> InventoryLog:
        entry = InventoryLog(
            product_id=product_id, quantity_change=quantity_change, reason=reason
        )
        self.session.add(entry)
        return entry

    async def logs_for_product(
        self, product_id: int, *, offset: int = 0, limit: int = 50
    ) -> tuple[Sequence[InventoryLog], int]:
        stmt = select(InventoryLog).where(InventoryLog.product_id == product_id)
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.session.execute(
            stmt.order_by(InventoryLog.created_at.desc(), InventoryLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all(), int(total or 0)
