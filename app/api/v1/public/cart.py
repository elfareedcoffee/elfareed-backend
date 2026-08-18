from typing import Optional
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from uuid import UUID
from decimal import Decimal

from app.api.deps import get_db, get_cart_id
from app.crud import crud_cart, crud_product, crud_variant
from app.core.exceptions import APIException
from app.core.limiter import limiter
from app.schemas.cart import CartResponse, CartItemResponse, CartItemCreate, CartItemUpdate
from app.core.localization import get_language, get_localized_translation
from app.db.models.product import LanguageEnum, ProductVariant, Product

router = APIRouter()

def _build_cart_response(db: Session, cart, lang: LanguageEnum) -> CartResponse:
    if not cart:
        return None
        
    items = []
    total_cart_price = Decimal('0.00')
    
    for item in cart.items:
        variant = db.query(ProductVariant).filter(ProductVariant.id == item.product_variant_id).first()
        product = db.query(Product).filter(Product.id == variant.product_id).first()
        translation = get_localized_translation(product.translations, lang)
        
        is_active = variant.is_active and product.is_active
        unit_price = variant.price
        total_price = unit_price * item.quantity
        
        items.append(CartItemResponse(
            id=item.id,
            product_variant_id=variant.id,
            product_id=product.id,
            product_name=translation.name if translation else "Unknown",
            product_image_url=product.image_url,
            weight_grams=variant.weight_grams,
            grind_type=variant.grind_type,
            unit_price=unit_price,
            total_price=total_price,
            quantity=item.quantity,
            stock_quantity=variant.stock_quantity,
            is_active=is_active
        ))
        
        if is_active:
            total_cart_price += total_price
            
    return CartResponse(
        id=cart.id,
        expires_at=cart.expires_at,
        items=items,
        total_cart_price=total_cart_price
    )

def set_cart_cookie(response: Response, cart_id: UUID):
    response.set_cookie(
        key="cart_id",
        value=str(cart_id),
        httponly=True,
        secure=True, # Note: Needs HTTPS in production
        samesite="lax",
        max_age=172800 # 48 hours
    )

@router.get("/", response_model=CartResponse)
def get_cart(
    response: Response,
    cart_id: Optional[str] = Depends(get_cart_id),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    if not cart_id:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    cart = crud_cart.get_cart(db, cart_id)
    if not cart:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    return _build_cart_response(db, cart, lang)

@router.post("/items", response_model=CartResponse)
@limiter.limit("20/minute")
def add_item_to_cart(
    request: Request,
    item_in: CartItemCreate,
    response: Response,
    cart_id: Optional[str] = Depends(get_cart_id),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    cart = None
    if cart_id:
        cart = crud_cart.get_cart(db, cart_id)
        
    if not cart:
        cart = crud_cart.create_cart(db)
        set_cart_cookie(response, cart.id)
        
    updated_cart = crud_cart.add_item_to_cart(db, cart.id, item_in.product_variant_id, item_in.quantity)
    return _build_cart_response(db, updated_cart, lang)

@router.put("/items/{item_id}", response_model=CartResponse)
@limiter.limit("20/minute")
def update_item_quantity(
    request: Request,
    item_id: UUID,
    item_in: CartItemUpdate,
    response: Response,
    cart_id: Optional[str] = Depends(get_cart_id),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    if not cart_id:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    updated_cart = crud_cart.update_item_quantity(db, cart_id, item_id, item_in.quantity)
    return _build_cart_response(db, updated_cart, lang)

@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_item(
    item_id: UUID,
    response: Response,
    cart_id: Optional[str] = Depends(get_cart_id),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    if not cart_id:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    updated_cart = crud_cart.remove_item_from_cart(db, cart_id, item_id)
    return _build_cart_response(db, updated_cart, lang)

@router.delete("/", response_model=CartResponse)
def clear_cart(
    response: Response,
    cart_id: Optional[str] = Depends(get_cart_id),
    db: Session = Depends(get_db),
    lang: LanguageEnum = Depends(get_language)
):
    if not cart_id:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    updated_cart = crud_cart.clear_cart(db, cart_id)
    return _build_cart_response(db, updated_cart, lang)
