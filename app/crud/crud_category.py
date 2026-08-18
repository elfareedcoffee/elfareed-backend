from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.db.models.product import Category, CategoryTranslation
from app.schemas.category import CategoryCreate, CategoryUpdate

def get_active_categories(db: Session):
    return db.query(Category).options(joinedload(Category.translations)).filter(Category.is_active == True).order_by(Category.sort_order).all()

def get_all_categories(db: Session):
    return db.query(Category).options(joinedload(Category.translations)).order_by(Category.sort_order).all()

def get_category_by_id(db: Session, category_id: UUID):
    return db.query(Category).options(joinedload(Category.translations)).filter(Category.id == category_id).first()

def create_category(db: Session, obj_in: CategoryCreate):
    db_obj = Category(
        is_active=obj_in.is_active,
        sort_order=obj_in.sort_order
    )
    db.add(db_obj)
    db.flush() # flush to get ID
    
    for t_in in obj_in.translations:
        db_translation = CategoryTranslation(
            category_id=db_obj.id,
            language=t_in.language,
            name=t_in.name,
            description=t_in.description
        )
        db.add(db_translation)
        
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update_category(db: Session, db_obj: Category, obj_in: CategoryUpdate):
    if obj_in.is_active is not None:
        db_obj.is_active = obj_in.is_active
    if obj_in.sort_order is not None:
        db_obj.sort_order = obj_in.sort_order
        
    if obj_in.translations is not None:
        # Simplest approach: delete old translations and insert new ones
        # Real world apps might update existing by language enum
        db.query(CategoryTranslation).filter(CategoryTranslation.category_id == db_obj.id).delete()
        for t_in in obj_in.translations:
            db.add(CategoryTranslation(
                category_id=db_obj.id,
                language=t_in.language,
                name=t_in.name,
                description=t_in.description
            ))
            
    db.commit()
    db.refresh(db_obj)
    return db_obj

def toggle_category_status(db: Session, db_obj: Category, is_active: bool):
    db_obj.is_active = is_active
    db.commit()
    db.refresh(db_obj)
    return db_obj
