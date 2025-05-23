import csv
import io
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models.sales import Sale
from app.repositories.periods import period_bounds
from app.repositories.sales import SaleRepository
from app.schemas.sales import (
    CategoryRevenue,
    RevenueBucket,
    RevenueComparison,
    SaleCreate,
)
from app.services.inventory import InventoryService
from app.services.products import ProductService

CENTS = Decimal("0.01")
PERCENT = Decimal("100")
CSV_COLUMNS = (
    "id",
    "sale_date",
    "product_id",
    "product_name",
    "category",
    "quantity_sold",
    "total_amount",
)


class SaleService:
    def __init__(
        self,
        session: AsyncSession,
        repo: SaleRepository,
        products: ProductService,
        inventory: InventoryService,
    ) -> None:
        self.session = session
        self.repo = repo
        self.products = products
        self.inventory = inventory

    async def record(self, data: SaleCreate) -> Sale:
        """Record a sale, price it, and take the units out of stock.

        The three writes - sale, stock level, stock log - share one
        transaction, so a sale can never exist without its stock movement.
        """
        product = await self.products.get(data.product_id)
        if not product.is_active:
            raise ConflictError(
                f"Product {product.id} is inactive and cannot be sold.",
                product_id=product.id,
            )

        total = data.total_amount
        if total is None:
            total = (product.price * data.quantity_sold).quantize(
                CENTS, rounding=ROUND_HALF_UP
            )

        stock = await self.inventory.require_stock(product.id)
        if stock.quantity < data.quantity_sold:
            raise ConflictError(
                f"Only {stock.quantity} unit(s) of product {product.id} in stock.",
                product_id=product.id,
                on_hand=stock.quantity,
                requested=data.quantity_sold,
            )

        sale = await self.repo.add(
            product.id, data.quantity_sold, data.sale_date, total
        )
        stock.quantity -= data.quantity_sold
        self.inventory.repo.log(
            product.id,
            -data.quantity_sold,
            f"sale {sale.id} on {data.sale_date.isoformat()}",
        )
        await self.session.commit()
        await self.session.refresh(sale)
        return sale

    async def list(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        product_id: int | None,
        category: str | None,
        offset: int,
        limit: int,
    ) -> tuple[Sequence[Sale], int]:
        return await self.repo.list(
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            category=category,
            offset=offset,
            limit=limit,
        )

    async def revenue_by_period(
        self,
        interval: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[RevenueBucket]:
        rows = await self.repo.revenue_by_period(
            interval, start_date=start_date, end_date=end_date
        )
        return [
            RevenueBucket(period=str(row.period), revenue=_money(row.revenue))
            for row in rows
        ]

    async def revenue_by_category(
        self, *, start_date: date | None = None, end_date: date | None = None
    ) -> list[CategoryRevenue]:
        rows = await self.repo.revenue_by_category(
            start_date=start_date, end_date=end_date
        )
        return [
            CategoryRevenue(category=row.category, revenue=_money(row.revenue))
            for row in rows
        ]

    async def compare(self, interval: str, today: date) -> RevenueComparison:
        current_start, previous_start, previous_end = period_bounds(interval, today)
        current = await self.repo.revenue_between(current_start, today)
        previous = await self.repo.revenue_between(previous_start, previous_end)
        change = None
        if previous > 0:
            change = float(((current - previous) / previous * PERCENT).quantize(CENTS))
        return RevenueComparison(
            interval=interval,
            current_period_start=current_start,
            previous_period_start=previous_start,
            current_period_revenue=_money(current),
            previous_period_revenue=_money(previous),
            change_percent=change,
        )

    async def export_csv(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        product_id: int | None,
        category: str | None,
    ) -> str:
        rows = await self.repo.iter_all(
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            category=category,
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    row.id,
                    row.sale_date.isoformat(),
                    row.product_id,
                    row.product_name,
                    row.category or "",
                    row.quantity_sold,
                    f"{_money(row.total_amount)}",
                ]
            )
        return buffer.getvalue()


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)
