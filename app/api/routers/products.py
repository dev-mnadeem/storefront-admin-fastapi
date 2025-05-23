from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Pagination, get_product_service, pagination
from app.core.security import require_api_key
from app.schemas.common import Page
from app.schemas.products import ProductCreate, ProductRead, ProductUpdate
from app.services.products import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_product(
    payload: ProductCreate,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.create(payload)


@router.get("/", response_model=Page[ProductRead])
async def list_products(
    search: str | None = Query(None, description="Case-insensitive name match."),
    category: str | None = None,
    is_active: bool | None = None,
    page: Pagination = Depends(pagination),
    service: ProductService = Depends(get_product_service),
) -> Page[ProductRead]:
    items, total = await service.list(
        search=search,
        category=category,
        is_active=is_active,
        offset=page.offset,
        limit=page.limit,
    )
    return Page[ProductRead](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.get(product_id)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    dependencies=[Depends(require_api_key)],
)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.update(product_id, payload)


@router.delete(
    "/{product_id}",
    response_model=ProductRead,
    dependencies=[Depends(require_api_key)],
)
async def deactivate_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    """Soft delete: the row stays so historical sales still resolve."""
    return await service.deactivate(product_id)
