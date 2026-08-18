from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal

from app.db.models.order import Order, OrderItem, OrderStatusEnum, PaymentMethodEnum, PaymentStatusEnum
from app.db.models.product import ProductVariant, Product, ProductTranslation, LanguageEnum

EGYPT_TZ = ZoneInfo("Africa/Cairo")

def get_egypt_time_bounds():
    now = datetime.now(EGYPT_TZ)
    
    # Today boundary (Midnight to Midnight next day)
    today_start = datetime.combine(now.date(), time.min, tzinfo=EGYPT_TZ)
    
    # This Week boundary
    # In Egypt, the work week typically starts on Sunday.
    # Python's weekday() gives Monday=0, Sunday=6.
    # To find the most recent Sunday:
    days_since_sunday = (now.weekday() + 1) % 7
    week_start = datetime.combine(now.date() - timedelta(days=days_since_sunday), time.min, tzinfo=EGYPT_TZ)
    
    # This Month boundary (1st of the current month)
    month_start = datetime.combine(now.date().replace(day=1), time.min, tzinfo=EGYPT_TZ)
    
    return today_start, week_start, month_start

def get_dashboard_stats(db: Session) -> Dict[str, Any]:
    today_start, week_start, month_start = get_egypt_time_bounds()
    
    # Basic Counts
    total_orders = db.query(Order).count()
    
    orders_today = db.query(Order).filter(Order.created_at >= today_start).count()
    orders_this_week = db.query(Order).filter(Order.created_at >= week_start).count()
    orders_this_month = db.query(Order).filter(Order.created_at >= month_start).count()
    
    # Revenue Calculations
    # Revenue is calculated as SUM(total) for all orders EXCEPT:
    # - CANCELLED
    # - ONLINE + FAILED
    # COD is included regardless of payment status (as pending cash).
    # ONLINE + PAID is included.
    rev_query = db.query(func.sum(Order.total)).filter(
        Order.order_status != OrderStatusEnum.CANCELLED,
        ~((Order.payment_method == PaymentMethodEnum.ONLINE) & (Order.payment_status == PaymentStatusEnum.FAILED))
    )
    
    revenue_today = rev_query.filter(Order.created_at >= today_start).scalar() or Decimal('0.00')
    revenue_this_week = rev_query.filter(Order.created_at >= week_start).scalar() or Decimal('0.00')
    revenue_this_month = rev_query.filter(Order.created_at >= month_start).scalar() or Decimal('0.00')
    
    # Status metrics
    pending_orders_count = db.query(Order).filter(Order.order_status == OrderStatusEnum.PENDING).count()
    
    status_counts = db.query(Order.order_status, func.count(Order.id)).group_by(Order.order_status).all()
    orders_by_status = {status.value: count for status, count in status_counts}
    
    return {
        "total_orders": total_orders,
        "orders_today": orders_today,
        "orders_this_week": orders_this_week,
        "orders_this_month": orders_this_month,
        "revenue_today": revenue_today,
        "revenue_this_week": revenue_this_week,
        "revenue_this_month": revenue_this_month,
        "pending_orders_count": pending_orders_count,
        "orders_by_status": orders_by_status
    }

def get_best_selling_products(db: Session, limit: int = 5):
    # Aggregating over order items, ignoring cancelled orders
    # We join Order to filter out CANCELLED.
    results = db.query(
        OrderItem.product_name_ar,
        OrderItem.product_name_en,
        func.sum(OrderItem.quantity).label("total_quantity_sold"),
        func.sum(OrderItem.total_price).label("total_revenue")
    ).join(Order).filter(
        Order.order_status != OrderStatusEnum.CANCELLED,
        ~((Order.payment_method == PaymentMethodEnum.ONLINE) & (Order.payment_status == PaymentStatusEnum.FAILED))
    ).group_by(
        OrderItem.original_product_id,
        OrderItem.product_name_ar,
        OrderItem.product_name_en
    ).order_by(desc("total_quantity_sold")).limit(limit).all()
    
    return [
        {
            "product_name_ar": r.product_name_ar,
            "product_name_en": r.product_name_en,
            "total_quantity_sold": int(r.total_quantity_sold or 0),
            "total_revenue": r.total_revenue or Decimal('0.00')
        }
        for r in results
    ]

def get_best_selling_variants(db: Session, limit: int = 5):
    results = db.query(
        OrderItem.product_name_ar,
        OrderItem.product_name_en,
        OrderItem.weight_grams,
        OrderItem.grind_type,
        func.sum(OrderItem.quantity).label("total_quantity_sold"),
        func.sum(OrderItem.total_price).label("total_revenue")
    ).join(Order).filter(
        Order.order_status != OrderStatusEnum.CANCELLED,
        ~((Order.payment_method == PaymentMethodEnum.ONLINE) & (Order.payment_status == PaymentStatusEnum.FAILED))
    ).group_by(
        OrderItem.original_product_id,
        OrderItem.product_name_ar,
        OrderItem.product_name_en,
        OrderItem.weight_grams,
        OrderItem.grind_type
    ).order_by(desc("total_quantity_sold")).limit(limit).all()
    
    return [
        {
            "product_name_ar": r.product_name_ar,
            "product_name_en": r.product_name_en,
            "weight_grams": r.weight_grams,
            "grind_type": r.grind_type,
            "total_quantity_sold": int(r.total_quantity_sold or 0),
            "total_revenue": r.total_revenue or Decimal('0.00')
        }
        for r in results
    ]

def get_low_stock_variants(db: Session, threshold: int = 10, limit: int = 10):
    # Requires joining ProductVariant to Product, and to ProductTranslation
    results = db.query(
        ProductVariant.id,
        ProductVariant.stock_quantity,
        ProductVariant.weight_grams,
        ProductVariant.grind_type,
        ProductTranslation.name,
        ProductTranslation.language
    ).join(Product, ProductVariant.product_id == Product.id).join(
        ProductTranslation, Product.id == ProductTranslation.product_id
    ).filter(
        ProductVariant.stock_quantity <= threshold,
        ProductVariant.is_active == True,
        Product.is_active == True
    ).order_by(ProductVariant.stock_quantity.asc()).limit(limit * 2).all()
    
    # Since we get two rows per variant (ar and en), we need to group them in python
    # limit*2 is a heuristic, but to do it properly in SQL we'd join twice or aggregate.
    # Grouping in python:
    variants = {}
    for r in results:
        vid = r.id
        if vid not in variants:
            variants[vid] = {
                "variant_id": r.id,
                "weight_grams": r.weight_grams,
                "grind_type": r.grind_type.value if hasattr(r.grind_type, 'value') else r.grind_type,
                "stock_quantity": r.stock_quantity,
                "product_name_ar": "",
                "product_name_en": ""
            }
        
        if r.language == LanguageEnum.ar:
            variants[vid]["product_name_ar"] = r.name
        elif r.language == LanguageEnum.en:
            variants[vid]["product_name_en"] = r.name
            
    # Sort and limit in python to ensure exact `limit` variants
    sorted_variants = sorted(variants.values(), key=lambda x: x["stock_quantity"])
    return sorted_variants[:limit]

def get_recent_orders(db: Session, limit: int = 5):
    orders = db.query(Order).order_by(desc(Order.created_at)).limit(limit).all()
    return [
        {
            "order_id": o.id,
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "total": o.total,
            "order_status": o.order_status.value,
            "created_at": o.created_at
        }
        for o in orders
    ]
