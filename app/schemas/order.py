from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from app.db.models.order import PaymentMethodEnum, PaymentStatusEnum, OrderStatusEnum
import re

PHONE_REGEX = re.compile(r"^\+20(10|11|12|15)[0-9]{8}$")

class OrderItemResponse(BaseModel):
    id: UUID
    product_variant_id: Optional[UUID] = None
    product_name_ar: str
    product_name_en: str
    weight_grams: int
    grind_type: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    customer_name: str = Field(..., max_length=255)
    customer_phone: str = Field(..., description="Egyptian phone number starting with +20", max_length=20)
    customer_email: Optional[str] = Field(None, max_length=255)
    governorate: str = Field(..., max_length=255)
    city: str = Field(..., max_length=255)
    delivery_address: str = Field(..., max_length=1024)
    delivery_notes: Optional[str] = Field(None, max_length=2000)
    payment_method: PaymentMethodEnum
    
    @field_validator('customer_phone')
    def validate_phone(cls, v):
        if not PHONE_REGEX.match(v):
            raise ValueError('Invalid Egyptian phone number format. Must start with +20 followed by 10/11/12/15 and 8 digits.')
        return v

class OrderItemInput(BaseModel):
    product_variant_id: UUID
    quantity: int = Field(1, ge=1, le=100)

class OrderCreate(OrderBase):
    items: Optional[List[OrderItemInput]] = None

class OrderResponse(OrderBase):
    id: UUID
    order_number: str
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal
    payment_status: PaymentStatusEnum
    order_status: OrderStatusEnum
    created_at: datetime
    items: List[OrderItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class OrderCheckoutResponse(OrderResponse):
    tracking_token: UUID

class OrderRecoverRequest(BaseModel):
    order_number: str = Field(..., max_length=50)
    customer_phone: str = Field(..., max_length=20)

class OrderPaginatedResponse(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    size: int
    total_pages: int
    
class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatusEnum
