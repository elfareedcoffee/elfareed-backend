import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid

from app.main import app
from app.db.models.admin import AdminUser, AdminRole
from app.db.models.product import Product, ProductTranslation

client = TestClient(app)

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

def test_get_single_product_success(mock_admin_auth):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    mock_prod = Product(id=prod_id, category_id=cat_id, is_active=True)
    mock_prod.translations = [
        ProductTranslation(id=uuid.uuid4(), product_id=prod_id, language="ar", name="Test AR", description="Desc AR")
    ]
    mock_prod.variants = []
    
    with patch("app.crud.crud_product.get_product_by_id", return_value=mock_prod):
        response = client.get(
            f"/api/v1/admin/products/{prod_id}",
            headers={"Authorization": "Bearer test_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(prod_id)
        assert len(data["translations"]) == 1

def test_get_nonexistent_product(mock_admin_auth):
    with patch("app.crud.crud_product.get_product_by_id", return_value=None):
        response = client.get(
            f"/api/v1/admin/products/{uuid.uuid4()}",
            headers={"Authorization": "Bearer test_token"}
        )
        assert response.status_code == 404

def test_get_unauthorized():
    response = client.get(f"/api/v1/admin/products/{uuid.uuid4()}")
    assert response.status_code == 401

def test_update_product_translations_success(mock_admin_auth):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    
    mock_prod = Product(id=prod_id, category_id=cat_id, is_active=True)
    mock_prod.translations = [
        ProductTranslation(id=uuid.uuid4(), product_id=prod_id, language="ar", name="Old AR", description="Old Desc")
    ]
    mock_prod.variants = []
    
    payload = {
        "translations": [
            {"language": "ar", "name": "New AR", "description": "New Desc AR"},
            {"language": "en", "name": "New EN", "description": "New Desc EN"}
        ]
    }
    
    with patch("app.crud.crud_product.get_product_by_id", return_value=mock_prod), \
         patch("app.crud.crud_product.update_product_translations", return_value=mock_prod) as mock_update:
        
        response = client.put(
            f"/api/v1/admin/products/{prod_id}/translations",
            headers={"Authorization": "Bearer test_token"},
            json=payload
        )
        assert response.status_code == 200
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        assert len(kwargs["obj_in"].translations) == 2

def test_update_duplicate_language(mock_admin_auth):
    prod_id = uuid.uuid4()
    payload = {
        "translations": [
            {"language": "ar", "name": "Name1", "description": "Desc1"},
            {"language": "ar", "name": "Name2", "description": "Desc2"}
        ]
    }
    
    response = client.put(
        f"/api/v1/admin/products/{prod_id}/translations",
        headers={"Authorization": "Bearer test_token"},
        json=payload
    )
    assert response.status_code == 422
    assert "Duplicate languages" in response.text

def test_update_invalid_language(mock_admin_auth):
    prod_id = uuid.uuid4()
    payload = {
        "translations": [
            {"language": "fr", "name": "Name", "description": "Desc"}
        ]
    }
    response = client.put(
        f"/api/v1/admin/products/{prod_id}/translations",
        headers={"Authorization": "Bearer test_token"},
        json=payload
    )
    assert response.status_code == 422

def test_update_invalid_name_length(mock_admin_auth):
    prod_id = uuid.uuid4()
    payload = {
        "translations": [
            {"language": "ar", "name": "", "description": "Desc"}
        ]
    }
    response = client.put(
        f"/api/v1/admin/products/{prod_id}/translations",
        headers={"Authorization": "Bearer test_token"},
        json=payload
    )
    assert response.status_code == 422

def test_update_nonexistent_product(mock_admin_auth):
    payload = {
        "translations": [
            {"language": "ar", "name": "Name", "description": "Desc"}
        ]
    }
    with patch("app.crud.crud_product.get_product_by_id", return_value=None):
        response = client.put(
            f"/api/v1/admin/products/{uuid.uuid4()}/translations",
            headers={"Authorization": "Bearer test_token"},
            json=payload
        )
        assert response.status_code == 404
