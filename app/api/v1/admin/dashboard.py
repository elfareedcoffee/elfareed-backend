from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_admin_user
from app.crud import crud_dashboard
from app.schemas.dashboard import (
    DashboardStatsResponse,
    BestSellingProduct,
    BestSellingVariant,
    LowStockVariant,
    RecentOrder
)

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    """
    Returns general statistics (orders, revenue, status distribution).
    Revenue calculates SUM(total) of all orders EXCEPT:
    - CANCELLED orders
    - ONLINE orders with FAILED payment status
    COD orders are included regardless of payment status.
    ONLINE orders with PAID status are included.
    Uses Africa/Cairo timezone for today/week/month boundaries.
    """
    return crud_dashboard.get_dashboard_stats(db)

@router.get("/best-selling-products", response_model=List[BestSellingProduct])
def get_best_selling_products(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    """Returns top products by quantity sold (ignores cancelled orders)."""
    return crud_dashboard.get_best_selling_products(db, limit=limit)

@router.get("/best-selling-variants", response_model=List[BestSellingVariant])
def get_best_selling_variants(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    """Returns top variants by quantity sold (ignores cancelled orders)."""
    return crud_dashboard.get_best_selling_variants(db, limit=limit)

@router.get("/low-stock-variants", response_model=List[LowStockVariant])
def get_low_stock_variants(
    threshold: int = Query(10, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    """Returns variants currently at or below the stock threshold."""
    return crud_dashboard.get_low_stock_variants(db, threshold=threshold, limit=limit)

@router.get("/recent-orders", response_model=List[RecentOrder])
def get_recent_orders(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    """Returns the most recently placed orders."""
    return crud_dashboard.get_recent_orders(db, limit=limit)
