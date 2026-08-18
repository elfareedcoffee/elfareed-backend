from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.db.models.product import LanguageEnum
from app.schemas.variant import VariantCreate, VariantAdminResponse, VariantPublicResponse

class ProductTranslationBase(BaseModel):
    language: LanguageEnum
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., max_length=4000)

class ProductTranslationCreate(ProductTranslationBase):
    pass

class ProductTranslationResponse(ProductTranslationBase):
    id: UUID
    product_id: UUID
    model_config = ConfigDict(from_attributes=True)

class ProductTranslationsUpdateRequest(BaseModel):
    translations: List[ProductTranslationCreate] = Field(..., min_length=1)

    @field_validator('translations')
    def check_duplicate_languages(cls, v):
        langs = [t.language for t in v]
        if len(langs) != len(set(langs)):
            raise ValueError('Duplicate languages are not allowed in translations.')
        return v

class ProductBase(BaseModel):
    category_id: UUID
    is_active: bool = True
    image_url: Optional[str] = Field(None, max_length=1024)

class ProductCreate(ProductBase):
    translations: List[ProductTranslationCreate] = Field(..., min_length=1)
    variants: Optional[List[VariantCreate]] = None

class ProductUpdate(BaseModel):
    category_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    image_url: Optional[str] = Field(None, max_length=1024)

class ProductAdminResponse(ProductBase):
    id: UUID
    translations: List[ProductTranslationResponse]
    variants: List[VariantAdminResponse] = []
    model_config = ConfigDict(from_attributes=True)

class ProductPublicResponse(BaseModel):
    id: UUID
    category_id: UUID
    image_url: Optional[str] = None
    name: str
    description: str
    variants: List[VariantPublicResponse] = []
    model_config = ConfigDict(from_attributes=True)
