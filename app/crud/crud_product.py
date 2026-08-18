from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.db.models.product import Product, ProductTranslation, ProductVariant
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.variant import VariantCreate
from app.crud.crud_variant import create_variant

def get_active_products(db: Session, category_id: UUID = None):
    query = db.query(Product).options(
        joinedload(Product.translations),
        joinedload(Product.variants)
    ).filter(Product.is_active == True)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
        
    products = query.all()
    # Filter out inactive variants in memory so we don't expose them publicly
    for p in products:
        p.variants = [v for v in p.variants if v.is_active]
        
    return products

def get_all_products(db: Session, category_id: UUID = None):
    query = db.query(Product).options(
        joinedload(Product.translations),
        joinedload(Product.variants)
    )
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
        
    return query.all()

def get_product_by_id(db: Session, product_id: UUID):
    return db.query(Product).options(
        joinedload(Product.translations),
        joinedload(Product.variants)
    ).filter(Product.id == product_id).first()

def create_product(db: Session, obj_in: ProductCreate):
    db_obj = Product(
        category_id=obj_in.category_id,
        is_active=obj_in.is_active,
        image_url=obj_in.image_url
    )
    db.add(db_obj)
    db.flush()
    
    for t_in in obj_in.translations:
        db_translation = ProductTranslation(
            product_id=db_obj.id,
            language=t_in.language,
            name=t_in.name,
            description=t_in.description
        )
        db.add(db_translation)
        
    db.commit()
    db.refresh(db_obj)
    
    # Process initial variants if provided
    if obj_in.variants:
        for v_in in obj_in.variants:
            create_variant(db, db_obj.id, v_in)
            
    # Refresh again to load relationships
    return get_product_by_id(db, db_obj.id)

def update_product(db: Session, db_obj: Product, obj_in: ProductUpdate, translations=None):
    if obj_in.category_id is not None:
        db_obj.category_id = obj_in.category_id
    if obj_in.is_active is not None:
        db_obj.is_active = obj_in.is_active
    if obj_in.image_url is not None:
        db_obj.image_url = obj_in.image_url
        
    if translations is not None:
        db.query(ProductTranslation).filter(ProductTranslation.product_id == db_obj.id).delete()
        for t_in in translations:
            db.add(ProductTranslation(
                product_id=db_obj.id,
                language=t_in.language,
                name=t_in.name,
                description=t_in.description
            ))
            
    db.commit()
    db.refresh(db_obj)
    return db_obj

def toggle_product_status(db: Session, db_obj: Product, is_active: bool):
    db_obj.is_active = is_active
    db.commit()
    db.refresh(db_obj)
    return db_obj

from app.schemas.product import ProductTranslationsUpdateRequest

def update_product_translations(db: Session, db_obj: Product, obj_in: ProductTranslationsUpdateRequest):
    existing = {t.language: t for t in db_obj.translations}
    
    for t_in in obj_in.translations:
        if t_in.language in existing:
            existing_t = existing[t_in.language]
            existing_t.name = t_in.name
            existing_t.description = t_in.description
        else:
            db.add(ProductTranslation(
                product_id=db_obj.id,
                language=t_in.language,
                name=t_in.name,
                description=t_in.description
            ))
            
    db.commit()
    db.refresh(db_obj)
    return get_product_by_id(db, db_obj.id)

