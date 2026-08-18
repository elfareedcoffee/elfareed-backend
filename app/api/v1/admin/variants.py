from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db, get_current_admin_user
from app.crud import crud_variant, crud_product
from app.schemas.variant import VariantCreate, VariantUpdate, VariantAdminResponse

router = APIRouter(dependencies=[Depends(get_current_admin_user)])

@router.post("/product/{product_id}", response_model=VariantAdminResponse)
def create_variant(product_id: UUID, variant_in: VariantCreate, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return crud_variant.create_variant(db, product_id, variant_in)

@router.put("/{variant_id}", response_model=VariantAdminResponse)
def update_variant(variant_id: UUID, variant_in: VariantUpdate, db: Session = Depends(get_db)):
    v = crud_variant.get_variant_by_id(db, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    return crud_variant.update_variant(db, db_obj=v, obj_in=variant_in)

@router.patch("/{variant_id}/activate", response_model=VariantAdminResponse)
def activate_variant(variant_id: UUID, db: Session = Depends(get_db)):
    v = crud_variant.get_variant_by_id(db, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    return crud_variant.toggle_variant_status(db, v, True)

@router.patch("/{variant_id}/deactivate", response_model=VariantAdminResponse)
def deactivate_variant(variant_id: UUID, db: Session = Depends(get_db)):
    v = crud_variant.get_variant_by_id(db, variant_id)
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    return crud_variant.toggle_variant_status(db, v, False)
