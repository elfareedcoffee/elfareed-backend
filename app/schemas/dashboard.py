from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class DashboardStatsResponse(BaseModel):
    total_orders: int
    orders_today: int
    orders_this_week: int
    orders_this_month: int
    
    revenue_today: Decimal
    revenue_this_week: Decimal
    revenue_this_month: Decimal
    
    pending_orders_count: int
    orders_by_status: Dict[str, int]
    
class BestSellingProduct(BaseModel):
    product_name_ar: str
    product_name_en: str
    total_quantity_sold: int
    total_revenue: Decimal

class BestSellingVariant(BaseModel):
    product_name_ar: str
    product_name_en: str
    weight_grams: int
    grind_type: str
    total_quantity_sold: int
    total_revenue: Decimal

class LowStockVariant(BaseModel):
    variant_id: UUID
    product_name_ar: str
    product_name_en: str
    weight_grams: int
    grind_type: str
    stock_quantity: int

class RecentOrder(BaseModel):
    order_id: UUID
    order_number: str
    customer_name: str
    total: Decimal
    order_status: str
    created_at: datetime
