import uuid
import string
import random
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.exceptions import APIException

from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatusEnum, PaymentStatusEnum
from app.db.models.product import ProductVariant, Product, LanguageEnum
from app.core.localization import get_localized_translation
from app.core.business_rules import calculate_delivery_fee
from app.schemas.order import OrderCreate

def _generate_order_number(db: Session) -> str:
    # Generates e.g. ELFA-A39K2
    while True:
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        order_num = f"ELFA-{suffix}"
        # Check collision
        if not db.query(Order).filter(Order.order_number == order_num).first():
            return order_num

def _get_utc_now():
    return datetime.now(timezone.utc)

def create_order_from_cart(db: Session, cart_id: str, order_in: OrderCreate) -> Order:
    try:
        cart_uuid = uuid.UUID(str(cart_id))
    except ValueError:
        raise APIException(status_code=400, code="CART_NOT_FOUND")
        
    try:
        # 1. Lock the Cart
        # This provides Idempotency: concurrent requests will block here, the first will delete it, the second will find it None
        cart = db.query(Cart).filter(Cart.id == cart_uuid).with_for_update().first()
        
        if not cart:
            raise APIException(status_code=404, code="EMPTY_CART")
            
        if cart.expires_at < _get_utc_now():
            raise APIException(status_code=400, code="CART_EXPIRED")
            
        if not cart.items:
            raise APIException(status_code=400, code="EMPTY_CART")
            
        # 2. Extract and Sort Variant IDs to prevent deadlocks
        variant_ids = [item.product_variant_id for item in cart.items]
        variant_ids.sort() # Deterministic lock order
        
        # 3. Lock ProductVariants
        locked_variants = db.query(ProductVariant).filter(
            ProductVariant.id.in_(variant_ids)
        ).order_by(ProductVariant.id).with_for_update().all()
        
        variant_map = {v.id: v for v in locked_variants}
        
        subtotal = Decimal('0.00')
        order_items_to_create = []
        
        # 4. Validate and build order items
        for cart_item in cart.items:
            variant = variant_map.get(cart_item.product_variant_id)
            if not variant:
                raise APIException(status_code=404, code="VARIANT_NOT_FOUND")
                
            if not variant.is_active:
                raise APIException(status_code=400, code="INACTIVE_VARIANT")
                
            # Fetch Product (no need to lock product row, just check active status)
            product = db.query(Product).filter(Product.id == variant.product_id).first()
            if not product or not product.is_active:
                raise APIException(status_code=400, code="INACTIVE_PRODUCT")
                
            # Check Stock
            if cart_item.quantity > variant.stock_quantity:
                raise APIException(status_code=400, code="INSUFFICIENT_STOCK")
                
            # Deduct Stock
            variant.stock_quantity -= cart_item.quantity
            
            # Snapshots
            name_ar = get_localized_translation(product.translations, LanguageEnum.ar)
            name_en = get_localized_translation(product.translations, LanguageEnum.en)
            
            unit_price = variant.price
            total_price = unit_price * cart_item.quantity
            subtotal += total_price
            
            order_item = OrderItem(
                product_variant_id=variant.id,
                original_product_id=product.id,
                product_name_ar=name_ar.name if name_ar else "Unknown",
                product_name_en=name_en.name if name_en else "Unknown",
                weight_grams=variant.weight_grams,
                grind_type=variant.grind_type.value,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            order_items_to_create.append(order_item)
            
        # 5. Financial Rules
        delivery_fee = calculate_delivery_fee()
        discount = Decimal('0.00')
        total = subtotal + delivery_fee - discount
        
        # 6. Create Order
        order = Order(
            order_number=_generate_order_number(db),
            customer_name=order_in.customer_name,
            customer_phone=order_in.customer_phone,
            customer_email=order_in.customer_email,
            governorate=order_in.governorate,
            city=order_in.city,
            delivery_address=order_in.delivery_address,
            delivery_notes=order_in.delivery_notes,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=discount,
            total=total,
            payment_method=order_in.payment_method
        )
        db.add(order)
        db.flush() # flush to get order.id for items
        
        for oi in order_items_to_create:
            oi.order_id = order.id
            db.add(oi)
            
        # 7. Delete Cart (Idempotency)
        db.delete(cart)
        
        # 8. Commit
        db.commit()
        db.refresh(order)
        return order

    except APIException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise APIException(status_code=500, code="INTERNAL_SERVER_ERROR") from e


def create_order_direct(db: Session, order_in: OrderCreate) -> Order:
    if not order_in.items:
        raise APIException(status_code=400, code="EMPTY_CART", message="السلة فارغة")
        
    try:
        # 1. Extract and Sort Variant IDs to prevent deadlocks
        variant_ids = [item.product_variant_id for item in order_in.items]
        variant_ids.sort() # Deterministic lock order
        
        # 2. Lock ProductVariants
        locked_variants = db.query(ProductVariant).filter(
            ProductVariant.id.in_(variant_ids)
        ).order_by(ProductVariant.id).with_for_update().all()
        
        variant_map = {v.id: v for v in locked_variants}
        
        subtotal = Decimal('0.00')
        order_items_to_create = []
        
        # 3. Validate and build order items
        for input_item in order_in.items:
            variant = variant_map.get(input_item.product_variant_id)
            if not variant:
                raise APIException(status_code=404, code="VARIANT_NOT_FOUND", message="أحد المنتجات المطلوبة غير متوفر")
                
            if not variant.is_active:
                raise APIException(status_code=400, code="INACTIVE_VARIANT", message="أحد المنتجات غير متاح حالياً")
                
            product = db.query(Product).filter(Product.id == variant.product_id).first()
            if not product or not product.is_active:
                raise APIException(status_code=400, code="INACTIVE_PRODUCT", message="أحد المنتجات غير متاح")
                
            # Check Stock
            if input_item.quantity > variant.stock_quantity:
                raise APIException(status_code=400, code="INSUFFICIENT_STOCK", message="الكمية المطلوبة غير متوفرة في المخزن")
                
            # Deduct Stock
            variant.stock_quantity -= input_item.quantity
            
            # Snapshots
            name_ar = get_localized_translation(product.translations, LanguageEnum.ar)
            name_en = get_localized_translation(product.translations, LanguageEnum.en)
            
            unit_price = variant.price
            total_price = unit_price * input_item.quantity
            subtotal += total_price
            
            order_item = OrderItem(
                product_variant_id=variant.id,
                original_product_id=product.id,
                product_name_ar=name_ar.name if name_ar else (product.name or "قهوة فريد"),
                product_name_en=name_en.name if name_en else "Fareed Coffee",
                weight_grams=variant.weight_grams,
                grind_type=variant.grind_type.value if hasattr(variant.grind_type, 'value') else str(variant.grind_type),
                quantity=input_item.quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            order_items_to_create.append(order_item)
            
        # 4. Financial Rules
        delivery_fee = calculate_delivery_fee()
        discount = Decimal('0.00')
        total = subtotal + delivery_fee - discount
        
        # 5. Create Order
        order = Order(
            order_number=_generate_order_number(db),
            customer_name=order_in.customer_name,
            customer_phone=order_in.customer_phone,
            customer_email=order_in.customer_email,
            governorate=order_in.governorate,
            city=order_in.city,
            delivery_address=order_in.delivery_address,
            delivery_notes=order_in.delivery_notes,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=discount,
            total=total,
            payment_method=order_in.payment_method
        )
        db.add(order)
        db.flush()
        
        for oi in order_items_to_create:
            oi.order_id = order.id
            db.add(oi)
            
        db.commit()
        db.refresh(order)
        return order

    except APIException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise APIException(status_code=500, code="INTERNAL_SERVER_ERROR") from e


def cancel_order(db: Session, order_id: str | uuid.UUID) -> Order:
    try:
        # 1. Lock the Order
        order = db.query(Order).filter(Order.id == uuid.UUID(str(order_id))).with_for_update().first()
        if not order:
            raise APIException(status_code=404, code="ORDER_NOT_FOUND")
            
        # 2. Validate Status
        if order.order_status in [OrderStatusEnum.OUT_FOR_DELIVERY, OrderStatusEnum.DELIVERED]:
            raise APIException(status_code=400, code="HTTP_ERROR", message="Cannot cancel an order that is out for delivery or delivered")
            
        if order.order_status == OrderStatusEnum.CANCELLED:
            raise APIException(status_code=400, code="HTTP_ERROR", message="Order is already cancelled")
            
        # 3. Deterministic Locking for Variants
        variant_ids = [item.product_variant_id for item in order.items if item.product_variant_id]
        if variant_ids:
            variant_ids.sort()
            locked_variants = db.query(ProductVariant).filter(
                ProductVariant.id.in_(variant_ids)
            ).order_by(ProductVariant.id).with_for_update().all()
            
            variant_map = {v.id: v for v in locked_variants}
            
            # 4. Restore Stock exactly once
            for item in order.items:
                if item.product_variant_id and item.product_variant_id in variant_map:
                    variant_map[item.product_variant_id].stock_quantity += item.quantity
                    
        # 5. Update Status
        order.order_status = OrderStatusEnum.CANCELLED
        
        # 6. Commit
        db.commit()
        db.refresh(order)
        return order
        
    except APIException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise APIException(status_code=500, code="INTERNAL_SERVER_ERROR") from e
