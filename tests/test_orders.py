import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.main import app
from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem, OrderStatusEnum, PaymentMethodEnum
from app.db.models.product import ProductVariant, Product, ProductTranslation, LanguageEnum, GrindTypeEnum

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    with patch("app.api.v1.storefront.orders.get_db") as mock:
        yield mock

@pytest.fixture
def mock_crud_order():
    with patch("app.api.v1.storefront.orders.crud_order") as mock:
        yield mock

# 1. Phone validation
def test_checkout_invalid_phone():
    client.cookies.set("cart_id", str(uuid.uuid4()))
    response = client.post(
        "/api/v1/public/orders/",
        json={
            "customer_name": "Test",
            "customer_phone": "01012345678", # Missing +20
            "governorate": "Cairo",
            "city": "Cairo",
            "delivery_address": "Test",
            "payment_method": "COD"
        }
    )
    assert response.status_code == 422
    assert "Invalid Egyptian phone number" in response.text

def test_checkout_valid_phone(mock_crud_order):
    mock_order = Order(
        id=uuid.uuid4(),
        order_number="ELFA-TEST",
        tracking_token=uuid.uuid4(),
        subtotal=10, delivery_fee=50, discount=0, total=60,
        payment_status="PENDING", order_status="PENDING",
        created_at=datetime.now(timezone.utc),
        customer_name="Test", customer_phone="+201012345678",
        governorate="Cairo", city="Cairo", delivery_address="Test",
        payment_method="COD"
    )
    mock_crud_order.create_order_from_cart.return_value = mock_order
    
    client.cookies.set("cart_id", str(uuid.uuid4()))
    response = client.post(
        "/api/v1/public/orders/",
        json={
            "customer_name": "Test",
            "customer_phone": "+201012345678",
            "governorate": "Cairo",
            "city": "Cairo",
            "delivery_address": "Test",
            "payment_method": "COD"
        }
    )
    
    assert response.status_code == 200
    # Duplicate checkout protection via cookie deletion
    cookie = response.headers.get("set-cookie", "")
    assert "cart_id" in cookie
    assert "Max-Age=0" in cookie or "max-age=0" in cookie.lower()

# Test the CRUD explicitly
from app.crud.crud_order import create_order_from_cart, cancel_order
from app.core.exceptions import APIException

def test_crud_create_order_empty_cart():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1), items=[])
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cart
    
    with pytest.raises(APIException) as exc:
        create_order_from_cart(db, str(cart.id), MagicMock())
    assert exc.value.status_code == 400
    assert exc.value.code == "EMPTY_CART"
    db.rollback.assert_called()

def test_crud_create_order_expired_cart():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cart
    
    with pytest.raises(APIException) as exc:
        create_order_from_cart(db, str(cart.id), MagicMock())
    assert exc.value.status_code == 400
    assert exc.value.code == "CART_EXPIRED"

def test_crud_create_order_inactive_variant():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart.items = [CartItem(product_variant_id=uuid.uuid4(), quantity=1)]
    
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cart
    
    variant = ProductVariant(id=cart.items[0].product_variant_id, is_active=False)
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [variant]
    
    with pytest.raises(APIException) as exc:
        create_order_from_cart(db, str(cart.id), MagicMock())
    assert exc.value.status_code == 400
    assert exc.value.code in ["INACTIVE_VARIANT", "INACTIVE_PRODUCT"]

def test_crud_create_order_insufficient_stock():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart.items = [CartItem(product_variant_id=uuid.uuid4(), quantity=5)]
    
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cart
    
    variant = ProductVariant(id=cart.items[0].product_variant_id, is_active=True, stock_quantity=1, product_id=uuid.uuid4())
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [variant]
    
    # Mock product active check
    product = Product(is_active=True)
    db.query.return_value.filter.return_value.first.side_effect = [product] # For the product check
    
    with pytest.raises(APIException) as exc:
        create_order_from_cart(db, str(cart.id), MagicMock())
    assert exc.value.status_code == 400
    assert exc.value.code == "INSUFFICIENT_STOCK"

def test_crud_create_order_success():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart.items = [CartItem(product_variant_id=uuid.uuid4(), quantity=2)]
    
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cart
    
    variant = ProductVariant(id=cart.items[0].product_variant_id, price=Decimal('100.00'), weight_grams=250, grind_type=GrindTypeEnum.ESPRESSO, is_active=True, stock_quantity=10, product_id=uuid.uuid4())
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [variant]
    
    product = Product(is_active=True, translations=[
        ProductTranslation(language=LanguageEnum.ar, name="قهوة"),
        ProductTranslation(language=LanguageEnum.en, name="Coffee")
    ])
    
    # We have to mock the `first` for product, and `first` for generate_order_number collision check.
    # 1st call to first(): product
    # 2nd call to first(): collision check returns None
    db.query.return_value.filter.return_value.first.side_effect = [product, None]
    
    order_in = MagicMock()
    order_in.payment_method = PaymentMethodEnum.COD
    
    order = create_order_from_cart(db, str(cart.id), order_in)
    
    assert variant.stock_quantity == 8 # Deducted
    assert order.subtotal == Decimal('200.00')
    assert order.delivery_fee == Decimal('50.00')
    assert order.total == Decimal('250.00')
    db.delete.assert_called_with(cart)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    
def test_crud_cancel_order_already_cancelled():
    db = MagicMock()
    order = Order(id=uuid.uuid4(), order_status=OrderStatusEnum.CANCELLED)
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = order
    
    with pytest.raises(APIException) as exc:
        cancel_order(db, str(order.id))
    assert exc.value.status_code == 400
    assert exc.value.message == "Order is already cancelled"

def test_crud_cancel_order_success():
    db = MagicMock()
    order = Order(id=uuid.uuid4(), order_status=OrderStatusEnum.PENDING)
    item = OrderItem(product_variant_id=uuid.uuid4(), quantity=3)
    order.items = [item]
    
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = order
    
    variant = ProductVariant(id=item.product_variant_id, stock_quantity=5)
    db.query.return_value.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [variant]
    
    cancel_order(db, str(order.id))
    
    assert variant.stock_quantity == 8 # Restored
    assert order.order_status == OrderStatusEnum.CANCELLED
    db.commit.assert_called_once()
