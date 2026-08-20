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


def update_order_status(db: Session, order_id: str | uuid.UUID, new_status: OrderStatusEnum) -> Order:
    try:
        order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).with_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        old_status = order.order_status
        if old_status == new_status:
            return order
            
        # Stock adjustment rules:
        # If transitioning TO CANCELLED from an active state -> Restore stock
        if new_status == OrderStatusEnum.CANCELLED and old_status != OrderStatusEnum.CANCELLED:
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
                        
        # If transitioning FROM CANCELLED back to an active state -> Deduct stock
        elif old_status == OrderStatusEnum.CANCELLED and new_status != OrderStatusEnum.CANCELLED:
            variant_ids = [item.product_variant_id for item in order.items if item.product_variant_id]
            if variant_ids:
                variant_ids.sort()
                locked_variants = db.query(ProductVariant).filter(
                    ProductVariant.id.in_(variant_ids)
                ).order_by(ProductVariant.id).with_for_update().all()
                variant_map = {v.id: v for v in locked_variants}
                for item in order.items:
                    if item.product_variant_id and item.product_variant_id in variant_map:
                        variant_map[item.product_variant_id].stock_quantity = max(0, variant_map[item.product_variant_id].stock_quantity - item.quantity)

        # If status becomes DELIVERED, automatically mark payment as PAID if COD
        if new_status == OrderStatusEnum.DELIVERED and order.payment_method.value == "COD":
            order.payment_status = PaymentStatusEnum.PAID

        order.order_status = new_status
        db.commit()
        db.refresh(order)
        return order
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
