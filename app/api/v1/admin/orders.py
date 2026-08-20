from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from typing import Optional
from datetime import datetime

from app.api.deps import get_db, get_current_admin_user
from app.crud import crud_admin_order
from app.schemas.order import OrderResponse, OrderPaginatedResponse, OrderStatusUpdateRequest
from app.db.models.order import OrderStatusEnum, PaymentStatusEnum

router = APIRouter()

@router.get("/", response_model=OrderPaginatedResponse)
def list_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    order_status: Optional[OrderStatusEnum] = None,
    payment_status: Optional[PaymentStatusEnum] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    return crud_admin_order.get_orders_paginated(
        db=db, page=page, size=size, search=search,
        order_status=order_status, payment_status=payment_status,
        start_date=start_date, end_date=end_date
    )

@router.get("/{order_id}", response_model=OrderResponse)
def get_order_details(
    order_id: UUID,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    order = crud_admin_order.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    status_update: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    return crud_admin_order.update_order_status(db, order_id, status_update.status)

@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    return crud_admin_order.cancel_order(db, order_id)

@router.delete("/{order_id}")
def delete_order_endpoint(
    order_id: UUID,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin_user)
):
    return crud_admin_order.delete_order(db, order_id)
