"""Dependency wiring: session -> repository -> service -> router."""

from dataclasses import dataclass

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import build_provider
from app.ai.base import InsightProvider
from app.ai.rules import RuleBasedInsightProvider
from app.core.config import Settings, get_settings, settings
from app.db.session import get_db
from app.repositories.inventory import InventoryRepository
from app.repositories.products import ProductRepository
from app.repositories.sales import SaleRepository
from app.services.insights import InsightService
from app.services.inventory import InventoryService
from app.services.products import ProductService
from app.services.sales import SaleService


@dataclass(frozen=True)
class Pagination:
    offset: int
    limit: int


def pagination(
    offset: int = Query(0, ge=0, description="Rows to skip."),
    limit: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description="Rows to return.",
    ),
) -> Pagination:
    return Pagination(offset=offset, limit=limit)


def get_product_service(db: AsyncSession = Depends(get_db)) -> ProductService:
    return ProductService(db, ProductRepository(db))


def get_inventory_service(
    db: AsyncSession = Depends(get_db),
    products: ProductService = Depends(get_product_service),
) -> InventoryService:
    return InventoryService(db, InventoryRepository(db), products)


def get_sale_service(
    db: AsyncSession = Depends(get_db),
    products: ProductService = Depends(get_product_service),
    inventory: InventoryService = Depends(get_inventory_service),
) -> SaleService:
    return SaleService(db, SaleRepository(db), products, inventory)


def get_insight_provider(
    app_settings: Settings = Depends(get_settings),
) -> InsightProvider:
    return build_provider(app_settings)


def get_insight_service(
    sales: SaleService = Depends(get_sale_service),
    inventory: InventoryService = Depends(get_inventory_service),
    provider: InsightProvider = Depends(get_insight_provider),
) -> InsightService:
    return InsightService(sales, inventory, provider, RuleBasedInsightProvider())
