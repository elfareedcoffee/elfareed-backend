import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid
import io

from app.main import app
from app.db.models.admin import AdminUser, AdminRole
from app.db.models.product import Product

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

@pytest.fixture
def mock_crud_product_admin():
    with patch("app.api.v1.admin.products.crud_product") as mock:
        yield mock

@pytest.fixture
def mock_storage():
    with patch("app.api.v1.admin.products.storage") as mock:
        yield mock

@pytest.fixture
def mock_db():
    with patch("app.api.v1.admin.products.get_db") as mock:
        yield mock

def test_upload_image_success_jpeg(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url=None)
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/image.jpg"
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.jpg", io.BytesIO(b"fake_image_data"), "image/jpeg")}
    )
    
    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/image.jpg"
    mock_storage.upload_product_image.assert_called_once()
    mock_storage.delete_product_image.assert_not_called()

def test_upload_image_replacement_flow_success(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url="https://example.com/old.jpg")
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake_image_data"), "image/png")}
    )
    
    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/new.png"
    mock_storage.upload_product_image.assert_called_once()
    mock_storage.delete_product_image.assert_called_once_with("https://example.com/old.jpg")

def test_upload_image_invalid_mime(mock_admin_auth, mock_crud_product_admin):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.return_value = Product(id=prod_id, category_id=cat_id)
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.pdf", io.BytesIO(b"pdf data"), "application/pdf")}
    )
    
    assert response.status_code == 400

def test_upload_image_too_large(mock_admin_auth, mock_crud_product_admin):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.return_value = Product(id=prod_id, category_id=cat_id)
    
    large_data = b"0" * ((2 * 1024 * 1024) + 1)
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("large.jpg", io.BytesIO(large_data), "image/jpeg")}
    )
    
    assert response.status_code == 400

def test_delete_image_success(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url="https://example.com/old.jpg")
    mock_crud_product_admin.get_product_by_id.return_value = p
    
    response = client.delete(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"}
    )
    
    assert response.status_code == 200
    mock_storage.delete_product_image.assert_called_once_with("https://example.com/old.jpg")

def test_storage_upload_failure_leaves_old_intact(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url="https://example.com/old.jpg")
    mock_crud_product_admin.get_product_by_id.return_value = p
    
    mock_storage.upload_product_image.side_effect = Exception("Storage down")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    )
    
    assert response.status_code == 500
    mock_storage.delete_product_image.assert_not_called()

def test_database_update_failure_cleans_up_new_image(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url="https://example.com/old.jpg")
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    # Simulate DB commit failure
    with patch("app.api.v1.admin.products.Depends") as mock_depends:
        pass
        
    mock_admin_auth.commit.side_effect = Exception("DB Down")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    
    assert response.status_code == 500
    mock_storage.delete_product_image.assert_called_once_with("https://example.com/new.png")
    assert mock_storage.delete_product_image.call_count == 1

def test_old_image_deletion_failure_does_not_rollback(mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=cat_id, is_active=True, image_url="https://example.com/old.jpg")
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    mock_storage.delete_product_image.side_effect = Exception("Delete failed")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    
    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/new.png"
    mock_storage.delete_product_image.assert_called_once_with("https://example.com/old.jpg")

@patch("starlette.datastructures.UploadFile.close")
def test_upload_cleanup_success(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=uuid.uuid4(), is_active=True, image_url=None)
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 200
    assert mock_close.call_count >= 1

@patch("starlette.datastructures.UploadFile.close")
def test_upload_cleanup_on_exception(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=uuid.uuid4(), is_active=True, image_url=None)
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.side_effect = Exception("Upload failed")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1

@patch("starlette.datastructures.UploadFile.close")
def test_database_update_failure_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=uuid.uuid4(), is_active=True, image_url=None)
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    mock_admin_auth.commit.side_effect = Exception("DB Down")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1

@patch("starlette.datastructures.UploadFile.close")
def test_unexpected_exception_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.side_effect = Exception("Unexpected error")
    
    custom_client = TestClient(app, raise_server_exceptions=False)
    response = custom_client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1

def test_unauthorized_image_upload():
    prod_id = uuid.uuid4()
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 401

def test_unauthorized_image_deletion():
    prod_id = uuid.uuid4()
    response = client.delete(
        f"/api/v1/admin/products/{prod_id}/image"
    )
    assert response.status_code == 401
