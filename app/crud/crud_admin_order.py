import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from fastapi import HTTPException

from app.db.models.order import Order, OrderStatusEnum, PaymentStatusEnum
from app.db.models.product import ProductVariant
from app.crud.crud_order import cancel_order

def delete_order(db: Session, order_id: str | uuid.UUID) -> dict:
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).with_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # If order was active (not cancelled or delivered), restore stock before deleting
        if order.order_status not in [OrderStatusEnum.CANCELLED, OrderStatusEnum.DELIVERED]:
            variant_ids = [item.product_variant_id for item in order.items if item.product_variant_id]
            if variant_ids:
                variant_ids.sort()
                locked_variants = db.query(ProductVariant).filter(
                    ProductVariant.id.in_(variant_ids)
                ).order_by(ProductVariant.id).with_for_update().all()
                variant_map = {v.id: v for v in locked_variants}
                for item in order.items:
                    if item.product_variant_id and item.product_variant_id in variant_map:
                        variant_map[item.product_variant_id].stock_quantity += item.quantity
        
        order_num = order.order_number
        db.delete(order)
        db.commit()
        return {"message": "Order deleted successfully", "order_number": order_num, "id": str(order_id)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def get_orders_paginated(
    db: Session,
    page: int = 1,
    size: int = 20,
    search: Optional[str] = None,
    order_status: Optional[OrderStatusEnum] = None,
    payment_status: Optional[PaymentStatusEnum] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    query = db.query(Order)
    
    if search:
        query = query.filter(
            or_(
                Order.order_number.ilike(f"%{search}%"),
                Order.customer_phone.ilike(f"%{search}%")
            )
        )
        
    if order_status:
        query = query.filter(Order.order_status == order_status)
        
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
        
    if start_date:
        query = query.filter(Order.created_at >= start_date)
        
    if end_date:
        query = query.filter(Order.created_at <= end_date)
        
    total = query.count()
    
    orders = query.order_by(desc(Order.created_at)).offset((page - 1) * size).limit(size).all()
    
    import math
    total_pages = math.ceil(total / size) if total > 0 else 0
    
    return {
        "items": orders,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages
    }

def get_order_by_id(db: Session, order_id: str | uuid.UUID) -> Order:
    order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


VALID_TRANSITIONS = {
    OrderStatusEnum.PENDING: [OrderStatusEnum.CONFIRMED, OrderStatusEnum.PREPARING, OrderStatusEnum.CANCELLED],
    OrderStatusEnum.CONFIRMED: [OrderStatusEnum.PREPARING, OrderStatusEnum.CANCELLED],
    OrderStatusEnum.PREPARING: [OrderStatusEnum.READY_FOR_DELIVERY, OrderStatusEnum.OUT_FOR_DELIVERY, OrderStatusEnum.DELIVERED, OrderStatusEnum.CANCELLED],
    OrderStatusEnum.READY_FOR_DELIVERY: [OrderStatusEnum.OUT_FOR_DELIVERY, OrderStatusEnum.DELIVERED, OrderStatusEnum.CANCELLED],
    OrderStatusEnum.OUT_FOR_DELIVERY: [OrderStatusEnum.DELIVERED, OrderStatusEnum.CANCELLED],
    OrderStatusEnum.DELIVERED: [],
    OrderStatusEnum.CANCELLED: []
}

def update_order_status(db: Session, order_id: str | uuid.UUID, new_status: OrderStatusEnum) -> Order:
    if new_status == OrderStatusEnum.CANCELLED:
        # Use existing cancellation logic for transaction-safe stock restoration
        return cancel_order(db, order_id)
        
    order = get_order_by_id(db, order_id)
    
    allowed_next_states = VALID_TRANSITIONS.get(order.order_status, [])
    
    if new_status not in allowed_next_states:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition from {order.order_status.value} to {new_status.value}"
        )
        
    order.order_status = new_status
    db.commit()
    db.refresh(order)
    return order
