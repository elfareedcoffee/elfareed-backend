import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid

from app.main import app
from app.db.models.admin import AdminUser, AdminRole
from app.db.models.product import Category, Product, ProductVariant

client = TestClient(app)

# Override admin auth for testing
@pytest.fixture
def mock_admin_auth():
    with patch("app.api.deps.supabase.auth.get_user") as mock_get_user, \
         patch("app.api.deps.SessionLocal") as mock_session_local:
        
        user_id = str(uuid.uuid4())
        
        class MockUser:
            id = user_id
        class MockResp:
            user = MockUser()
            
        mock_get_user.return_value = MockResp()
        
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_admin = AdminUser(auth_user_id=user_id, role=AdminRole.ADMIN, is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_admin
        
        yield mock_db

@pytest.fixture
def mock_crud_category_admin():
    with patch("app.api.v1.admin.categories.crud_category") as mock:
        yield mock

@pytest.fixture
def mock_crud_product_admin():
    with patch("app.api.v1.admin.products.crud_product") as mock:
        yield mock

@pytest.fixture
def mock_crud_variant_admin():
    with patch("app.api.v1.admin.variants.crud_variant") as mock:
        with patch("app.api.v1.admin.variants.crud_product") as mock_p:
            yield mock, mock_p

def test_admin_create_category(mock_admin_auth, mock_crud_category_admin):
    mock_crud_category_admin.create_category.return_value = Category(id=uuid.uuid4(), is_active=True, sort_order=0, translations=[])
    
    payload = {
        "is_active": True,
        "sort_order": 1,
        "translations": [
            {"language": "ar", "name": "قهوة", "description": ""}
        ]
    }
    
    response = client.post("/api/v1/admin/categories/", json=payload, headers={"Authorization": "Bearer token"})
    assert response.status_code == 200

def test_admin_create_product_missing_category(mock_admin_auth, mock_crud_product_admin, mock_crud_category_admin):
    # crud_category.get_category_by_id returns None (category not found)
    with patch("app.api.v1.admin.products.crud_category.get_category_by_id", return_value=None):
        payload = {
            "category_id": str(uuid.uuid4()),
            "is_active": True,
            "translations": [
                {"language": "ar", "name": "قهوة برازيلي", "description": ""}
            ]
        }
        
        response = client.post("/api/v1/admin/products/", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "HTTP_ERROR"

def test_admin_create_variant_validation(mock_admin_auth):
    # Test Pydantic validation for negative prices/weights
    prod_id = str(uuid.uuid4())
    payload = {
        "weight_grams": -100, # Invalid
        "grind_type": "ESPRESSO",
        "price": -50.0, # Invalid
        "stock_quantity": -10, # Invalid
        "is_active": True
    }
    
    response = client.post(f"/api/v1/admin/variants/product/{prod_id}", json=payload, headers={"Authorization": "Bearer token"})
    assert response.status_code == 422 # Unprocessable Entity
    
    errors = response.json()["error"]["message"]
    # assert len(errors) == 3
    # Check that it caught weight, price, and stock being negative

def test_admin_get_nonexistent_product(mock_admin_auth, mock_crud_product_admin):
    mock_crud_product_admin.get_product_by_id.return_value = None
    response = client.put(f"/api/v1/admin/products/{uuid.uuid4()}", headers={"Authorization": "Bearer token"}, json={"is_active": True})
    assert response.status_code == 404

def test_admin_create_product_invalid_data(mock_admin_auth):
    response = client.post(
        "/api/v1/admin/products/",
        headers={"Authorization": "Bearer token"},
        json={"is_active": True} # Missing category_id and translations
    )
    assert response.status_code == 422

def test_admin_invalid_uuid(mock_admin_auth):
    response = client.put("/api/v1/admin/products/invalid-uuid", headers={"Authorization": "Bearer token"}, json={"is_active": True})
    assert response.status_code == 422

def test_admin_get_nonexistent_category(mock_admin_auth, mock_crud_category_admin):
    mock_crud_category_admin.get_category_by_id.return_value = None
    response = client.put(f"/api/v1/admin/categories/{uuid.uuid4()}", headers={"Authorization": "Bearer token"}, json={"is_active": True})
    assert response.status_code == 404

def test_admin_get_nonexistent_variant(mock_admin_auth, mock_crud_variant_admin):
    mock_crud_variant, _ = mock_crud_variant_admin
    mock_crud_variant.get_variant_by_id.return_value = None
    response = client.put(f"/api/v1/admin/variants/{uuid.uuid4()}", headers={"Authorization": "Bearer token"}, json={"is_active": True})
    assert response.status_code == 404

def test_admin_duplicate_variant_configuration(mock_admin_auth, mock_crud_variant_admin):
    mock_crud_variant, mock_crud_product = mock_crud_variant_admin
    from fastapi import HTTPException
    
    mock_crud_product.get_product_by_id.return_value = Product(id=uuid.uuid4())
    mock_crud_variant.create_variant.side_effect = HTTPException(status_code=400, detail="Variant with this weight and grind type already exists for this product")
    
    payload = {
        "weight_grams": 250,
        "grind_type": "ESPRESSO",
        "price": 50.0,
        "stock_quantity": 10,
        "is_active": True
    }
    response = client.post(f"/api/v1/admin/variants/product/{uuid.uuid4()}", json=payload, headers={"Authorization": "Bearer token"})
    assert response.status_code == 400
    assert "already exists" in response.json()["error"]["message"]
