from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from app.db.models.product import GrindTypeEnum

class VariantBase(BaseModel):
    weight_grams: int = Field(..., gt=0)
    grind_type: GrindTypeEnum
    price: Decimal = Field(..., ge=0, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True

class VariantCreate(VariantBase):
    pass

class VariantUpdate(BaseModel):
    weight_grams: Optional[int] = Field(None, gt=0)
    grind_type: Optional[GrindTypeEnum] = None
    price: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    stock_quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class VariantAdminResponse(VariantBase):
    id: UUID
    product_id: UUID
    model_config = ConfigDict(from_attributes=True)

class VariantPublicResponse(BaseModel):
    id: UUID
    weight_grams: int
    grind_type: GrindTypeEnum
    price: Decimal
    stock_quantity: int
    model_config = ConfigDict(from_attributes=True)
