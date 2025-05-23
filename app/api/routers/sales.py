from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import Pagination, get_sale_service, pagination
from app.core.security import require_api_key
from app.repositories.periods import IntervalName
from app.schemas.common import Page
from app.schemas.sales import (
    CategoryRevenue,
    RevenueBucket,
    RevenueComparison,
    SaleCreate,
    SaleRead,
)
from app.services.sales import SaleService

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post(
    "/",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def record_sale(
    payload: SaleCreate,
    service: SaleService = Depends(get_sale_service),
) -> SaleRead:
    """Record a sale, price it from the product, and draw down stock."""
    return await service.record(payload)


@router.get("/", response_model=Page[SaleRead])
async def list_sales(
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: int | None = None,
    category: str | None = None,
    page: Pagination = Depends(pagination),
    service: SaleService = Depends(get_sale_service),
) -> Page[SaleRead]:
    items, total = await service.list(
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category=category,
        offset=page.offset,
        limit=page.limit,
    )
    return Page[SaleRead](
        items=items, total=total, limit=page.limit, offset=page.offset
    )


@router.get("/export.csv", response_class=StreamingResponse)
async def export_sales(
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: int | None = None,
    category: str | None = None,
    service: SaleService = Depends(get_sale_service),
) -> StreamingResponse:
    """The same filters as `GET /sales`, delivered as a spreadsheet."""
    body = await service.export_csv(
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        category=category,
    )
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sales.csv"'},
    )


@router.get("/summary", response_model=list[RevenueBucket])
async def revenue_summary(
    interval: IntervalName = "month",
    start_date: date | None = None,
    end_date: date | None = None,
    service: SaleService = Depends(get_sale_service),
) -> list[RevenueBucket]:
    return await service.revenue_by_period(
        interval, start_date=start_date, end_date=end_date
    )


@router.get("/summary_by_category", response_model=list[CategoryRevenue])
async def revenue_by_category(
    start_date: date | None = None,
    end_date: date | None = None,
    service: SaleService = Depends(get_sale_service),
) -> list[CategoryRevenue]:
    return await service.revenue_by_category(start_date=start_date, end_date=end_date)


@router.get("/compare", response_model=RevenueComparison)
async def compare_revenue(
    interval: IntervalName = "month",
    on: date | None = Query(
        None, description="Treat this date as today. Defaults to the server date."
    ),
    service: SaleService = Depends(get_sale_service),
) -> RevenueComparison:
    return await service.compare(interval, on or date.today())
