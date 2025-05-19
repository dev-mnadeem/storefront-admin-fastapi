from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.products import Product
from app.schemas.products import ProductCreate


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _filtered(
        search: str | None, category: str | None, is_active: bool | None
    ) -> Select:
        stmt = select(Product)
        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))
        if category:
            stmt = stmt.where(Product.category == category)
        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
        return stmt

    async def get(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def get_by_name(self, name: str) -> Product | None:
        result = await self.session.execute(select(Product).where(Product.name == name))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Product], int]:
        stmt = self._filtered(search, category, is_active)
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await self.session.execute(
            stmt.order_by(Product.id).offset(offset).limit(limit)
        )
        return result.scalars().all(), int(total or 0)

    async def add(self, data: ProductCreate) -> Product:
        product = Product(**data.model_dump())
        self.session.add(product)
        await self.session.flush()
        return product
