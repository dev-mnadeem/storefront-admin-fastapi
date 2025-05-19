from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.products import Product
from app.models.sales import Sale
from app.repositories.periods import period_expression

TOP_CATEGORY_LIMIT = 5


class SaleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @property
    def dialect(self) -> str:
        return self.session.get_bind().dialect.name

    @staticmethod
    def _filtered(
        start_date: date | None,
        end_date: date | None,
        product_id: int | None,
        category: str | None,
    ) -> Select:
        stmt = select(Sale)
        if category:
            stmt = stmt.join(Product, Product.id == Sale.product_id).where(
                Product.category == category
            )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        if product_id:
            stmt = stmt.where(Sale.product_id == product_id)
        return stmt

    async def list(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        product_id: int | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Sale], int]:
        stmt = self._filtered(start_date, end_date, product_id, category)
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.session.execute(
            stmt.order_by(Sale.sale_date.desc(), Sale.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all(), int(total or 0)

    async def iter_all(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        product_id: int | None = None,
        category: str | None = None,
    ) -> Sequence[Row]:
        """Sales joined to product names, ordered, for the CSV export."""
        stmt = (
            select(
                Sale.id,
                Sale.sale_date,
                Sale.product_id,
                Product.name.label("product_name"),
                Product.category,
                Sale.quantity_sold,
                Sale.total_amount,
            )
            .join(Product, Product.id == Sale.product_id)
            .order_by(Sale.sale_date, Sale.id)
        )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        if product_id:
            stmt = stmt.where(Sale.product_id == product_id)
        if category:
            stmt = stmt.where(Product.category == category)
        result = await self.session.execute(stmt)
        return result.all()

    async def add(
        self, product_id: int, quantity_sold: int, sale_date: date, total: Decimal
    ) -> Sale:
        sale = Sale(
            product_id=product_id,
            quantity_sold=quantity_sold,
            sale_date=sale_date,
            total_amount=total,
        )
        self.session.add(sale)
        await self.session.flush()
        return sale

    async def revenue_by_period(
        self,
        interval: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Sequence[Row]:
        bucket = period_expression(self.dialect, interval, Sale.sale_date)
        stmt = select(
            bucket.label("period"), func.sum(Sale.total_amount).label("revenue")
        )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        result = await self.session.execute(stmt.group_by(bucket).order_by(bucket))
        return result.all()

    async def revenue_by_category(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[Row]:
        stmt = (
            select(
                Product.category,
                func.sum(Sale.total_amount).label("revenue"),
            )
            .select_from(Sale)
            .join(Product, Product.id == Sale.product_id)
            .group_by(Product.category)
            .order_by(func.sum(Sale.total_amount).desc())
        )
        if start_date:
            stmt = stmt.where(Sale.sale_date >= start_date)
        if end_date:
            stmt = stmt.where(Sale.sale_date <= end_date)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.all()

    async def revenue_between(self, start: date, end: date) -> Decimal:
        total = await self.session.scalar(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
                Sale.sale_date >= start, Sale.sale_date <= end
            )
        )
        return Decimal(str(total or 0))
