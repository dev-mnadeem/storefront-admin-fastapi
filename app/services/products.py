from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.products import Product
from app.repositories.products import ProductRepository
from app.schemas.products import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, session: AsyncSession, repo: ProductRepository) -> None:
        self.session = session
        self.repo = repo

    async def get(self, product_id: int) -> Product:
        product = await self.repo.get(product_id)
        if product is None:
            raise NotFoundError(f"No product with id {product_id}.")
        return product

    async def list(
        self,
        *,
        search: str | None,
        category: str | None,
        is_active: bool | None,
        offset: int,
        limit: int,
    ) -> tuple[Sequence[Product], int]:
        return await self.repo.list(
            search=search,
            category=category,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )

    async def create(self, data: ProductCreate) -> Product:
        if await self.repo.get_by_name(data.name) is not None:
            raise ConflictError(
                f"A product named {data.name!r} already exists.", name=data.name
            )
        product = await self.repo.add(data)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update(self, product_id: int, data: ProductUpdate) -> Product:
        product = await self.get(product_id)
        changes = data.model_dump(exclude_unset=True)
        new_name = changes.get("name")
        if new_name and new_name != product.name:
            clash = await self.repo.get_by_name(new_name)
            if clash is not None:
                raise ConflictError(
                    f"A product named {new_name!r} already exists.", name=new_name
                )
        for field, value in changes.items():
            setattr(product, field, value)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def deactivate(self, product_id: int) -> Product:
        """Retire a product without deleting the sales history that cites it."""
        product = await self.get(product_id)
        product.is_active = False
        await self.session.commit()
        await self.session.refresh(product)
        return product
