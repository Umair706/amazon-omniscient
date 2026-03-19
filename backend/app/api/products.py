"""API routes for product detail and time-series history."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.bsr_history import BSRHistory
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.schemas.product import ProductResponse

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Inline response schemas for time-series endpoints
# ---------------------------------------------------------------------------


class BSRHistoryPoint(BaseModel):
    """Single BSR data point."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    bsr: int
    category_id: str | None = None


class BSRHistoryResponse(BaseModel):
    """BSR time-series response for a product."""

    asin: str
    items: list[BSRHistoryPoint]
    total: int


class PriceHistoryPoint(BaseModel):
    """Single price data point."""

    model_config = ConfigDict(from_attributes=True)

    time: datetime
    price: Decimal | None = None
    has_coupon: bool | None = None
    coupon_value: Decimal | None = None
    is_lightning_deal: bool | None = None
    buy_box_seller_id: str | None = None


class PriceHistoryResponse(BaseModel):
    """Price time-series response for a product."""

    asin: str
    items: list[PriceHistoryPoint]
    total: int


# ---------------------------------------------------------------------------
# GET /products/{asin} — Product detail by ASIN
# ---------------------------------------------------------------------------


@router.get("/{asin}", response_model=ProductResponse)
async def get_product_by_asin(
    asin: str,
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Return full product detail for a given ASIN."""
    normalised_asin = asin.strip().upper()
    result = await db.execute(
        select(Product).where(Product.asin == normalised_asin)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ASIN '{normalised_asin}' not found",
        )
    return ProductResponse.model_validate(product)


# ---------------------------------------------------------------------------
# GET /products/{asin}/bsr-history — BSR time-series
# ---------------------------------------------------------------------------


@router.get("/{asin}/bsr-history", response_model=BSRHistoryResponse)
async def get_bsr_history(
    asin: str,
    limit: int = Query(500, ge=1, le=5000, description="Max data points to return"),
    db: AsyncSession = Depends(get_db),
) -> BSRHistoryResponse:
    """Return BSR time-series data for a product, ordered chronologically."""
    normalised_asin = asin.strip().upper()

    # Resolve product to get product_id
    product_result = await db.execute(
        select(Product.id).where(Product.asin == normalised_asin)
    )
    product_id = product_result.scalar_one_or_none()
    if product_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ASIN '{normalised_asin}' not found",
        )

    result = await db.execute(
        select(BSRHistory)
        .where(BSRHistory.product_id == product_id)
        .order_by(BSRHistory.time.asc())
        .limit(limit)
    )
    rows = result.scalars().all()

    return BSRHistoryResponse(
        asin=normalised_asin,
        items=[BSRHistoryPoint.model_validate(r) for r in rows],
        total=len(rows),
    )


# ---------------------------------------------------------------------------
# GET /products/{asin}/price-history — Price time-series
# ---------------------------------------------------------------------------


@router.get("/{asin}/price-history", response_model=PriceHistoryResponse)
async def get_price_history(
    asin: str,
    limit: int = Query(500, ge=1, le=5000, description="Max data points to return"),
    db: AsyncSession = Depends(get_db),
) -> PriceHistoryResponse:
    """Return price time-series data for a product, ordered chronologically."""
    normalised_asin = asin.strip().upper()

    product_result = await db.execute(
        select(Product.id).where(Product.asin == normalised_asin)
    )
    product_id = product_result.scalar_one_or_none()
    if product_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ASIN '{normalised_asin}' not found",
        )

    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.time.asc())
        .limit(limit)
    )
    rows = result.scalars().all()

    return PriceHistoryResponse(
        asin=normalised_asin,
        items=[PriceHistoryPoint.model_validate(r) for r in rows],
        total=len(rows),
    )


# ---------------------------------------------------------------------------
# GET /products/{asin}/velocity — Sales velocity time-series
# ---------------------------------------------------------------------------


@router.get("/{asin}/velocity")
async def get_product_velocity(
    asin: str,
    days: int = Query(30, ge=1, le=365, description="Days of velocity data to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return sales velocity time-series and current estimates for a product."""
    normalised_asin = asin.strip().upper()

    product_result = await db.execute(
        select(Product).where(Product.asin == normalised_asin)
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ASIN '{normalised_asin}' not found",
        )

    from app.services.sales_velocity_service import SalesVelocityService

    velocity_svc = SalesVelocityService(db)
    timeseries = await velocity_svc.get_velocity_timeseries(product.id, days=days)

    return {
        "asin": normalised_asin,
        "estimated_daily_sales": product.estimated_daily_sales,
        "sales_velocity_trend": product.sales_velocity_trend,
        "last_stock_level": product.last_stock_level,
        "timeseries": timeseries,
    }
