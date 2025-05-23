from collections.abc import Sequence

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, InvalidRequestError, NotFoundError
from app.models.inventory import Inventory
from app.models.inventory_log import InventoryLog
from app.repositories.inventory import InventoryRepository
from app.services.products import ProductService


class InventoryService:
    """Stock levels and the audit trail behind them.

    Every quantity change goes through here so that an ``inventory_logs`` row
    is written in the same transaction as the level it explains.
    """

    def __init__(
        self,
        session: AsyncSession,
        repo: InventoryRepository,
        products: ProductService,
    ) -> None:
        self.session = session
        self.repo = repo
        self.products = products

    @property
    def levels_threshold(self) -> int:
        return settings.low_stock_threshold

    async def levels(
        self,
        *,
        low_stock: bool,
        threshold: int | None,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int, int]:
        effective = settings.low_stock_threshold if threshold is None else threshold
        rows, total = await self.repo.levels(
            low_stock=low_stock, threshold=effective, offset=offset, limit=limit
        )
        items = [
            {
                "product_id": row.product_id,
                "product_name": row.product_name,
                "category": row.category,
                "quantity": row.quantity,
                "is_low_stock": row.quantity < effective,
            }
            for row in rows
        ]
        return items, total, effective

    async def open_stock(
        self, product_id: int, quantity: int, reason: str
    ) -> Inventory:
        """Create the single stock row for a product."""
        await self.products.get(product_id)
        if await self.repo.get_for_product(product_id) is not None:
            raise ConflictError(
                f"Product {product_id} already has a stock record. "
                "Use PATCH /inventory/{product_id} to adjust it.",
                product_id=product_id,
            )
        row = await self.repo.add(product_id, quantity)
        self.repo.log(product_id, quantity, reason)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def adjust(
        self, product_id: int, quantity_change: int, reason: str
    ) -> Inventory:
        if quantity_change == 0:
            raise InvalidRequestError("quantity_change must not be zero.")
        row = await self.require_stock(product_id)
        new_quantity = row.quantity + quantity_change
        if new_quantity < 0:
            raise ConflictError(
                f"Adjusting by {quantity_change} would take stock below zero.",
                product_id=product_id,
                on_hand=row.quantity,
            )
        row.quantity = new_quantity
        self.repo.log(product_id, quantity_change, reason)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def require_stock(self, product_id: int) -> Inventory:
        row = await self.repo.get_for_product(product_id)
        if row is None:
            raise NotFoundError(
                f"Product {product_id} has no stock record.", product_id=product_id
            )
        return row

    async def logs(
        self, product_id: int, *, offset: int, limit: int
    ) -> tuple[Sequence[InventoryLog], int]:
        await self.products.get(product_id)
        return await self.repo.logs_for_product(product_id, offset=offset, limit=limit)

    async def low_stock_rows(self, limit: int) -> Sequence[Row]:
        rows, _ = await self.repo.levels(
            low_stock=True,
            threshold=settings.low_stock_threshold,
            offset=0,
            limit=limit,
        )
        return rows
