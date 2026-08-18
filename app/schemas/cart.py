from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from datetime import datetime
from app.db.models.product import GrindTypeEnum

class CartItemBase(BaseModel):
    product_variant_id: UUID
    quantity: int = Field(..., gt=0)

class CartItemCreate(CartItemBase):
    pass

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)

class CartItemResponse(BaseModel):
    id: UUID
    product_variant_id: UUID
    product_id: UUID
    product_name: str
    product_image_url: Optional[str] = None
    weight_grams: int
    grind_type: GrindTypeEnum
    unit_price: Decimal
    total_price: Decimal
    quantity: int
    stock_quantity: int
    is_active: bool # False if product/variant was deactivated while in cart
    model_config = ConfigDict(from_attributes=True)

class CartResponse(BaseModel):
    id: UUID
    expires_at: datetime
    items: List[CartItemResponse] = []
    total_cart_price: Decimal = Decimal('0.00')
    model_config = ConfigDict(from_attributes=True)
