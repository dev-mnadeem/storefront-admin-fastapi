from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.products import PRICE_PRECISION, PRICE_SCALE


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(gt=0, max_digits=PRICE_PRECISION, decimal_places=PRICE_SCALE)
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    """Every field optional - this is a PATCH body."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(
        default=None, gt=0, max_digits=PRICE_PRECISION, decimal_places=PRICE_SCALE
    )
    is_active: bool | None = None

    @model_validator(mode="after")
    def _required_columns_stay_set(self) -> "ProductUpdate":
        # Omitting a field leaves it alone; sending null for a NOT NULL column
        # would otherwise reach the database and fail as a 500.
        cleared = sorted(
            name
            for name in ("name", "price", "is_active")
            if name in self.model_fields_set and getattr(self, name) is None
        )
        if cleared:
            raise ValueError(f"{', '.join(cleared)} cannot be null")
        return self


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
