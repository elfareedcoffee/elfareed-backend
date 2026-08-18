from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db, get_current_admin_user
from app.crud import crud_product, crud_category
from app.schemas.product import ProductCreate, ProductUpdate, ProductAdminResponse, ProductTranslationsUpdateRequest

router = APIRouter(dependencies=[Depends(get_current_admin_user)])

@router.get("/", response_model=List[ProductAdminResponse])
def get_products(category_id: Optional[UUID] = Query(None), db: Session = Depends(get_db)):
    return crud_product.get_all_products(db, category_id)

@router.get("/{product_id}", response_model=ProductAdminResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p

@router.put("/{product_id}/translations", response_model=ProductAdminResponse)
def update_product_translations(product_id: UUID, translations_in: ProductTranslationsUpdateRequest, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return crud_product.update_product_translations(db, db_obj=p, obj_in=translations_in)


@router.post("/", response_model=ProductAdminResponse)
def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    cat = crud_category.get_category_by_id(db, product_in.category_id)
    if not cat:
        raise HTTPException(status_code=400, detail="Category does not exist")
    return crud_product.create_product(db, product_in)

@router.put("/{product_id}", response_model=ProductAdminResponse)
def update_product(product_id: UUID, product_in: ProductUpdate, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    if product_in.category_id:
        cat = crud_category.get_category_by_id(db, product_in.category_id)
        if not cat:
            raise HTTPException(status_code=400, detail="Category does not exist")
            
    # Note: translations update would require a separate translation payload or be included in ProductUpdate
    # For now, this just updates base product fields
    return crud_product.update_product(db, db_obj=p, obj_in=product_in)

@router.patch("/{product_id}/activate", response_model=ProductAdminResponse)
def activate_product(product_id: UUID, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return crud_product.toggle_product_status(db, p, True)

@router.patch("/{product_id}/deactivate", response_model=ProductAdminResponse)
def deactivate_product(product_id: UUID, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return crud_product.toggle_product_status(db, p, False)

@router.delete("/{product_id}")
def delete_product_endpoint(product_id: UUID, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    crud_product.delete_product(db, p)
    return {"message": "Product deleted successfully", "id": str(product_id)}

from fastapi import UploadFile, File
from app.services import storage

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/x-png",
    "image/webp", "image/gif", "image/svg+xml", "image/avif", "image/heic", "image/heif"
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif", ".heic", ".heif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.post("/{product_id}/image", response_model=ProductAdminResponse)
async def upload_product_image(
    product_id: UUID, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    try:
        p = crud_product.get_product_by_id(db, product_id)
        if not p:
            raise HTTPException(status_code=404, detail="Product not found")

        content_type = (file.content_type or "").lower().split(";")[0].strip()
        filename = (file.filename or "").lower()
        import os
        _, ext = os.path.splitext(filename)

        if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only JPEG, PNG, WebP, GIF, SVG, and AVIF images are allowed."
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit.")

        old_image_url = p.image_url

        effective_mime = content_type if content_type in ALLOWED_MIME_TYPES else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png")

        # 1. Upload the new image first
        try:
            new_image_url = storage.upload_product_image(file_bytes, effective_mime)
        except Exception as e:
            # If new upload fails, old image is kept untouched.
            import logging
            logging.getLogger(__name__).error(f"Image upload exception: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
            
        # 2. Verify and commit DB update
        try:
            p.image_url = new_image_url
            db.commit()
            db.refresh(p)
        except Exception as e:
            db.rollback()
            # DB update failed -> Attempt to clean up the newly uploaded image
            try:
                storage.delete_product_image(new_image_url)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Failed to update database")
            
        # 3. Clean up old image only after successful DB update
        if old_image_url:
            try:
                storage.delete_product_image(old_image_url)
            except Exception as e:
                # Do not fail the request if cleanup fails, log it instead
                import logging
                logging.getLogger(__name__).warning(f"Failed to delete orphaned image: {old_image_url}")
                
        return p
    finally:
        await file.close()

@router.delete("/{product_id}/image", response_model=ProductAdminResponse)
def delete_product_image(product_id: UUID, db: Session = Depends(get_db)):
    p = crud_product.get_product_by_id(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if p.image_url:
        storage.delete_product_image(p.image_url)
        p.image_url = None
        db.commit()
        db.refresh(p)
        
    return p
