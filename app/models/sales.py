from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.products import PRICE_PRECISION, PRICE_SCALE


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        # Every analytics query filters or groups on sale_date, and the
        # per-product history reads (product_id, sale_date) together.
        Index("ix_sales_sale_date", "sale_date"),
        Index("ix_sales_product_date", "product_id", "sale_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False
    )
