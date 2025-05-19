from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory import MAX_UNITS
from app.models.inventory_log import DEFAULT_REASON


class InventoryBase(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=0, le=MAX_UNITS)


class InventoryCreate(InventoryBase):
    """Set stock for a product to an absolute quantity."""

    reason: str = Field(default="initial stock", max_length=255)


class InventoryAdjust(BaseModel):
    """Move stock by a relative amount - the audited path."""

    quantity_change: int = Field(
        ge=-MAX_UNITS,
        le=MAX_UNITS,
        description="Positive to receive stock, negative to write it off.",
    )
    reason: str = Field(default=DEFAULT_REASON, max_length=255)


class InventoryRead(InventoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class InventoryLevel(BaseModel):
    """Stock joined to its product, so a dashboard needs one request."""

    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    category: str | None
    quantity: int
    is_low_stock: bool
