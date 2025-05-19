from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory import MAX_UNITS
from app.models.products import PRICE_PRECISION, PRICE_SCALE


class SaleBase(BaseModel):
    product_id: int = Field(gt=0)
    quantity_sold: int = Field(gt=0, le=MAX_UNITS)
    sale_date: date


class SaleCreate(SaleBase):
    """``total_amount`` is optional.

    Leave it out and the service prices the sale from the product's own
    ``price``, which is the only figure the client cannot forge.
    """

    total_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=PRICE_PRECISION, decimal_places=PRICE_SCALE
    )


class SaleRead(SaleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_amount: Decimal


class RevenueBucket(BaseModel):
    period: str
    revenue: Decimal


class CategoryRevenue(BaseModel):
    category: str | None
    revenue: Decimal


class RevenueComparison(BaseModel):
    interval: str
    current_period_start: date
    previous_period_start: date
    current_period_revenue: Decimal
    previous_period_revenue: Decimal
    change_percent: float | None = Field(
        description="None when the previous period had no revenue to compare to."
    )
