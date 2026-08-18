from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db, get_current_admin_user
from app.crud import crud_category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryAdminResponse

# All routes here require admin authentication
router = APIRouter(dependencies=[Depends(get_current_admin_user)])

@router.get("/", response_model=List[CategoryAdminResponse])
def get_categories(db: Session = Depends(get_db)):
    return crud_category.get_all_categories(db)

@router.post("/", response_model=CategoryAdminResponse)
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db)):
    return crud_category.create_category(db, category_in)

@router.put("/{category_id}", response_model=CategoryAdminResponse)
def update_category(category_id: UUID, category_in: CategoryUpdate, db: Session = Depends(get_db)):
    cat = crud_category.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return crud_category.update_category(db, db_obj=cat, obj_in=category_in)

@router.patch("/{category_id}/activate", response_model=CategoryAdminResponse)
def activate_category(category_id: UUID, db: Session = Depends(get_db)):
    cat = crud_category.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return crud_category.toggle_category_status(db, cat, True)

@router.patch("/{category_id}/deactivate", response_model=CategoryAdminResponse)
def deactivate_category(category_id: UUID, db: Session = Depends(get_db)):
    cat = crud_category.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return crud_category.toggle_category_status(db, cat, False)
