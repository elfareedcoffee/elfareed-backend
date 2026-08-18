from sqlalchemy.orm import Session, joinedload
from app.core.exceptions import APIException
from uuid import UUID
from datetime import datetime, timedelta, timezone
from app.db.models.cart import Cart, CartItem
from app.db.models.product import ProductVariant, Product

def _get_utc_now():
    return datetime.now(timezone.utc)

def get_cart(db: Session, cart_id: str | UUID):
    try:
        cart_uuid = UUID(str(cart_id))
    except ValueError:
        return None
        
    cart = db.query(Cart).options(
        joinedload(Cart.items)
    ).filter(Cart.id == cart_uuid).first()
    
    if not cart:
        return None
        
    # Check expiration
    if cart.expires_at < _get_utc_now():
        return None
        
    return cart

def create_cart(db: Session):
    # Expire in 48 hours
    expires_at = _get_utc_now() + timedelta(hours=48)
    cart = Cart(expires_at=expires_at)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart

def add_item_to_cart(db: Session, cart_id: str | UUID, variant_id: UUID, quantity: int):
    cart = get_cart(db, cart_id)
    if not cart:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        raise APIException(status_code=404, code="VARIANT_NOT_FOUND")
        
    if not variant.is_active:
        raise APIException(status_code=400, code="INACTIVE_VARIANT")
        
    product = db.query(Product).filter(Product.id == variant.product_id).first()
    if not product or not product.is_active:
        raise APIException(status_code=400, code="INACTIVE_PRODUCT")
        
    # Check if item already in cart
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_variant_id == variant_id
    ).first()
    
    new_quantity = quantity
    if existing_item:
        new_quantity += existing_item.quantity
        
    # Validate stock (no deduction yet)
    if new_quantity > variant.stock_quantity:
        raise APIException(status_code=400, code="INSUFFICIENT_STOCK")
        
    if existing_item:
        existing_item.quantity = new_quantity
    else:
        new_item = CartItem(
            cart_id=cart.id,
            product_variant_id=variant_id,
            quantity=quantity
        )
        db.add(new_item)
        
    # Refresh cart expiration
    cart.expires_at = _get_utc_now() + timedelta(hours=48)
    
    db.commit()
    return get_cart(db, cart.id)

def update_item_quantity(db: Session, cart_id: str | UUID, item_id: UUID, quantity: int):
    cart = get_cart(db, cart_id)
    if not cart:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id
    ).first()
    
    if not item:
        raise APIException(status_code=404, code="NOT_FOUND")
        
    variant = db.query(ProductVariant).filter(ProductVariant.id == item.product_variant_id).first()
    if quantity > variant.stock_quantity:
        raise APIException(status_code=400, code="INSUFFICIENT_STOCK")
        
    item.quantity = quantity
    cart.expires_at = _get_utc_now() + timedelta(hours=48)
    
    db.commit()
    return get_cart(db, cart.id)

def remove_item_from_cart(db: Session, cart_id: str | UUID, item_id: UUID):
    cart = get_cart(db, cart_id)
    if not cart:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id
    ).first()
    
    if not item:
        raise APIException(status_code=404, code="NOT_FOUND")
        
    db.delete(item)
    cart.expires_at = _get_utc_now() + timedelta(hours=48)
    db.commit()
    return get_cart(db, cart.id)

def clear_cart(db: Session, cart_id: str | UUID):
    cart = get_cart(db, cart_id)
    if not cart:
        raise APIException(status_code=404, code="CART_NOT_FOUND")
        
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    return get_cart(db, cart.id)
