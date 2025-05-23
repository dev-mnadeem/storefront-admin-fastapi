from fastapi import APIRouter, Depends, Query, status

from app.api.deps import Pagination, get_inventory_service, pagination
from app.core.security import require_api_key
from app.schemas.common import Page
from app.schemas.inventory import (
    InventoryAdjust,
    InventoryCreate,
    InventoryLevel,
    InventoryRead,
)
from app.schemas.inventory_log import InventoryLogRead
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/", response_model=Page[InventoryLevel])
async def list_levels(
    low_stock: bool = False,
    threshold: int | None = Query(
        None, ge=0, description="Overrides LOW_STOCK_THRESHOLD for this request."
    ),
    page: Pagination = Depends(pagination),
    service: InventoryService = Depends(get_inventory_service),
) -> Page[InventoryLevel]:
    items, total, _ = await service.levels(
        low_stock=low_stock,
        threshold=threshold,
        offset=page.offset,
        limit=page.limit,
    )
    return Page[InventoryLevel](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


@router.post(
    "/",
    response_model=InventoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def open_stock(
    payload: InventoryCreate,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryRead:
    """Create the stock record for a product that has none yet."""
    return await service.open_stock(
        payload.product_id, payload.quantity, payload.reason
    )


@router.patch(
    "/{product_id}",
    response_model=InventoryRead,
    dependencies=[Depends(require_api_key)],
)
async def adjust_stock(
    product_id: int,
    payload: InventoryAdjust,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryRead:
    """Move stock by a relative amount and write the audit row."""
    return await service.adjust(product_id, payload.quantity_change, payload.reason)


@router.get("/logs/{product_id}", response_model=Page[InventoryLogRead])
async def product_logs(
    product_id: int,
    page: Pagination = Depends(pagination),
    service: InventoryService = Depends(get_inventory_service),
) -> Page[InventoryLogRead]:
    items, total = await service.logs(product_id, offset=page.offset, limit=page.limit)
    return Page[InventoryLogRead](
        items=items, total=total, limit=page.limit, offset=page.offset
    )
