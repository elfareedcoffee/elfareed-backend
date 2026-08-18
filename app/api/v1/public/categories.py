from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db
from app.crud import crud_category
from app.schemas.category import CategoryPublicResponse
from app.core.localization import get_language, get_localized_translation
from app.db.models.product import LanguageEnum
from app.core.exceptions import APIException

router = APIRouter()

@router.get("/", response_model=List[CategoryPublicResponse])
def get_categories(
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    categories = crud_category.get_active_categories(db)
    result = []
    for cat in categories:
        translation = get_localized_translation(cat.translations, lang)
        if translation:
            result.append(CategoryPublicResponse(
                id=cat.id,
                name=translation.name,
                description=translation.description
            ))
    return result

@router.get("/{category_id}", response_model=CategoryPublicResponse)
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    cat = crud_category.get_category_by_id(db, category_id)
    if not cat or not cat.is_active:
        raise APIException(status_code=404, code="CATEGORY_NOT_FOUND")
        
    translation = get_localized_translation(cat.translations, lang)
    if not translation:
        raise APIException(status_code=404, code="CATEGORY_NOT_FOUND")
        
    return CategoryPublicResponse(
        id=cat.id,
        name=translation.name,
        description=translation.description
    )
