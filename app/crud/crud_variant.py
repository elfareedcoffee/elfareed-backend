from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from uuid import UUID
from app.db.models.product import ProductVariant
from app.schemas.variant import VariantCreate, VariantUpdate

def get_variant_by_id(db: Session, variant_id: UUID):
    return db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()

def create_variant(db: Session, product_id: UUID, obj_in: VariantCreate):
    db_obj = ProductVariant(
        product_id=product_id,
        weight_grams=obj_in.weight_grams,
        grind_type=obj_in.grind_type,
        price=obj_in.price,
        stock_quantity=obj_in.stock_quantity,
        is_active=obj_in.is_active
    )
    try:
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Variant with this weight and grind type already exists for this product")

def update_variant(db: Session, db_obj: ProductVariant, obj_in: VariantUpdate):
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
        
    try:
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Variant with this weight and grind type already exists for this product")

def toggle_variant_status(db: Session, db_obj: ProductVariant, is_active: bool):
    db_obj.is_active = is_active
    db.commit()
    db.refresh(db_obj)
    return db_obj
