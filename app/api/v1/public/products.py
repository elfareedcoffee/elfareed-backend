from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db
from app.crud import crud_product
from app.schemas.product import ProductPublicResponse
from app.schemas.variant import VariantPublicResponse
from app.core.localization import get_language, get_localized_translation
from app.db.models.product import LanguageEnum
from app.core.exceptions import APIException

router = APIRouter()

@router.get("/", response_model=List[ProductPublicResponse])
def get_products(
    category_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    products = crud_product.get_active_products(db, category_id=category_id)
    result = []
    for p in products:
        translation = get_localized_translation(p.translations, lang)
        if translation:
            variants = [
                VariantPublicResponse.model_validate(v) for v in p.variants if v.is_active
            ]
            result.append(ProductPublicResponse(
                id=p.id,
                category_id=p.category_id,
                image_url=p.image_url,
                name=translation.name,
                description=translation.description,
                variants=variants
            ))
    return result

@router.get("/{product_id}", response_model=ProductPublicResponse)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    p = crud_product.get_product_by_id(db, product_id)
    if not p or not p.is_active:
        raise APIException(status_code=404, code="PRODUCT_NOT_FOUND")
        
    translation = get_localized_translation(p.translations, lang)
    if not translation:
        raise APIException(status_code=404, code="PRODUCT_NOT_FOUND")
        
    variants = [
        VariantPublicResponse.model_validate(v) for v in p.variants if v.is_active
    ]
    
    return ProductPublicResponse(
        id=p.id,
        category_id=p.category_id,
        image_url=p.image_url,
        name=translation.name,
        description=translation.description,
        variants=variants
    )
