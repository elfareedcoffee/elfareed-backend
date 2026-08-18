import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
import uuid
from datetime import datetime, timedelta, timezone

from app.main import app
from app.db.models.cart import Cart, CartItem
from app.db.models.product import Product, ProductVariant, ProductTranslation, LanguageEnum, GrindTypeEnum

client = TestClient(app)

@pytest.fixture
def mock_crud_cart():
    with patch("app.api.v1.storefront.cart.crud_cart") as mock:
        yield mock

@pytest.fixture
def mock_db_session():
    with patch("app.api.v1.storefront.cart.get_db") as mock:
        yield mock

# Mock helper for building cart response internally inside the router
@pytest.fixture
def mock_db_queries():
    # Since _build_cart_response queries Product and ProductVariant directly, we must mock them.
    # Alternatively, we can patch _build_cart_response for simplicity or mock the DB session.
    with patch("app.api.v1.storefront.cart.Session.query") as mock_query:
        yield mock_query

# 1. Guest cart creation
# 3. Add item
# 17. Cookie behavior
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_create_cart_on_add_item(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    mock_crud_cart.get_cart.return_value = None
    mock_cart = Cart(id=cart_id, expires_at=datetime.now(timezone.utc) + timedelta(hours=48))
    mock_crud_cart.create_cart.return_value = mock_cart
    mock_crud_cart.add_item_to_cart.return_value = mock_cart
    
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    
    response = client.post(
        "/api/v1/public/cart/items",
        json={"product_variant_id": str(uuid.uuid4()), "quantity": 1}
    )
    
    assert response.status_code == 200
    mock_crud_cart.create_cart.assert_called_once()
    
    # Check Cookie behavior
    assert "cart_id" in response.cookies
    cookie = response.headers.get("set-cookie")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie

# 2. Cart retrieval
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_cart_retrieval(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    mock_cart = Cart(id=cart_id)
    mock_crud_cart.get_cart.return_value = mock_cart
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    
    client.cookies.set("cart_id", str(cart_id))
    response = client.get("/api/v1/public/cart/")
    
    assert response.status_code == 200
    mock_crud_cart.get_cart.assert_called_with(ANY, str(cart_id))

# 4. Update quantity
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_update_quantity(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    item_id = uuid.uuid4()
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    client.cookies.set("cart_id", str(cart_id))
    response = client.put(
        f"/api/v1/public/cart/items/{item_id}",
        json={"quantity": 5}
    )
    assert response.status_code == 200
    mock_crud_cart.update_item_quantity.assert_called_once()

# 5. Remove item
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_remove_item(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    item_id = uuid.uuid4()
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    client.cookies.set("cart_id", str(cart_id))
    response = client.delete(f"/api/v1/public/cart/items/{item_id}")
    assert response.status_code == 200
    mock_crud_cart.remove_item_from_cart.assert_called_once()

# 6. Clear cart
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_clear_cart(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    client.cookies.set("cart_id", str(cart_id))
    response = client.delete("/api/v1/public/cart/")
    assert response.status_code == 200
    mock_crud_cart.clear_cart.assert_called_once()

# 10. Zero/negative quantity
def test_negative_quantity_validation():
    response = client.post(
        "/api/v1/public/cart/items",
        json={"product_variant_id": str(uuid.uuid4()), "quantity": 0} # Invalid
    )
    assert response.status_code == 422 # Pydantic gt=0 constraint

# 16. X-Cart-ID fallback
@patch("app.api.v1.storefront.cart._build_cart_response")
def test_x_cart_id_fallback(mock_build, mock_crud_cart):
    cart_id = uuid.uuid4()
    mock_cart = Cart(id=cart_id)
    mock_crud_cart.get_cart.return_value = mock_cart
    mock_build.return_value = {"id": str(cart_id), "expires_at": datetime.now(timezone.utc).isoformat(), "items": []}
    
    # No cookies sent, only Header
    client.cookies.clear()
    response = client.get(
        "/api/v1/public/cart/",
        headers={"X-Cart-ID": str(cart_id)}
    )
    
    assert response.status_code == 200
    mock_crud_cart.get_cart.assert_called_with(ANY, str(cart_id))

# Test CRUD Logic specifically for Business Rules
from app.crud.crud_cart import add_item_to_cart, get_cart
from app.core.exceptions import APIException

# 7. Invalid variant, 8. Inactive product, 9. Inactive variant, 11. Insufficient stock
def test_crud_add_item_business_rules():
    db = MagicMock()
    cart_id = uuid.uuid4()
    variant_id = uuid.uuid4()
    
    # Mock cart exists
    db.query.return_value.options.return_value.filter.return_value.first.return_value = Cart(id=cart_id, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    
    # 7. Invalid Variant (Not found)
    db.query.return_value.filter.return_value.first.side_effect = [None] # Variant query returns None
    with pytest.raises(APIException) as exc:
        add_item_to_cart(db, cart_id, variant_id, 1)
    assert exc.value.status_code == 404
    
    # 9. Inactive Variant
    variant = ProductVariant(id=variant_id, is_active=False, stock_quantity=10, product_id=uuid.uuid4())
    db.query.return_value.filter.return_value.first.side_effect = [variant] 
    with pytest.raises(APIException) as exc:
        add_item_to_cart(db, cart_id, variant_id, 1)
    assert exc.value.status_code == 400
    assert exc.value.code == "INACTIVE_VARIANT"
    
    # 8. Inactive Product
    variant.is_active = True
    product = Product(is_active=False)
    db.query.return_value.filter.return_value.first.side_effect = [variant, product]
    with pytest.raises(APIException) as exc:
        add_item_to_cart(db, cart_id, variant_id, 1)
    assert exc.value.status_code == 400
    
    # 11. Insufficient stock
    product.is_active = True
    db.query.return_value.filter.return_value.first.side_effect = [variant, product, None] # existing item is None
    with pytest.raises(APIException) as exc:
        add_item_to_cart(db, cart_id, variant_id, 15) # Exceeds 10
    assert exc.value.status_code == 400
    assert exc.value.code == "INSUFFICIENT_STOCK"

# 12. Cart expiration
def test_crud_get_cart_expiration():
    db = MagicMock()
    cart_id = uuid.uuid4()
    # Mock cart with past expiration
    past_date = datetime.now(timezone.utc) - timedelta(hours=1)
    cart = Cart(id=cart_id, expires_at=past_date)
    
    db.query.return_value.options.return_value.filter.return_value.first.return_value = cart
    
    result = get_cart(db, cart_id)
    assert result is None # Returns None if expired

# 14. Arabic default localization, 15. English localization via Accept-Language
from app.api.v1.storefront.cart import _build_cart_response

def test_build_cart_localization():
    db = MagicMock()
    cart = Cart(id=uuid.uuid4(), expires_at=datetime.now(timezone.utc))
    item = CartItem(id=uuid.uuid4(), product_variant_id=uuid.uuid4(), quantity=2)
    cart.items = [item]
    
    from decimal import Decimal
    variant = ProductVariant(id=item.product_variant_id, price=Decimal('100.00'), weight_grams=250, grind_type=GrindTypeEnum.ESPRESSO, stock_quantity=10, is_active=True, product_id=uuid.uuid4())
    product = Product(id=variant.product_id, is_active=True)
    product.translations = [
        ProductTranslation(language=LanguageEnum.ar, name="قهوة", description=""),
        ProductTranslation(language=LanguageEnum.en, name="Coffee", description="")
    ]
    
    db.query.return_value.filter.return_value.first.side_effect = [variant, product, variant, product]
    
    # Test English
    resp_en = _build_cart_response(db, cart, LanguageEnum.en)
    assert resp_en.items[0].product_name == "Coffee"
    assert resp_en.total_cart_price == 200.00
    
    # Test Arabic
    db.query.return_value.filter.return_value.first.side_effect = [variant, product]
    resp_ar = _build_cart_response(db, cart, LanguageEnum.ar)
    assert resp_ar.items[0].product_name == "قهوة"
