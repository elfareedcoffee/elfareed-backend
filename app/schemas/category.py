from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from app.db.models.product import LanguageEnum, GrindTypeEnum

class TranslationBase(BaseModel):
    language: LanguageEnum
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)

class CategoryTranslationCreate(TranslationBase):
    pass

class CategoryTranslationResponse(TranslationBase):
    id: UUID
    category_id: UUID
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    is_active: bool = True
    sort_order: int = 0

class CategoryCreate(CategoryBase):
    translations: List[CategoryTranslationCreate] = Field(..., min_length=1)

class CategoryUpdate(CategoryBase):
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    translations: Optional[List[CategoryTranslationCreate]] = None

class CategoryAdminResponse(CategoryBase):
    id: UUID
    translations: List[CategoryTranslationResponse]
    model_config = ConfigDict(from_attributes=True)

# Public Response (flattened)
class CategoryPublicResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
