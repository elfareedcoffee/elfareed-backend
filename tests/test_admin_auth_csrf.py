import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_admin_user, get_db, verify_csrf_token
from unittest.mock import patch, MagicMock
from app.db.models.admin import AdminUser
import uuid

# Create a test router
test_router = APIRouter()

@test_router.get("/test/admin/get")
def test_get(admin: AdminUser = Depends(get_current_admin_user)):
    return {"message": "Success"}

@test_router.post("/test/admin/post")
def test_post(admin: AdminUser = Depends(get_current_admin_user)):
    return {"message": "Success"}

app.include_router(test_router)

client = TestClient(app)

@pytest.fixture
def mock_admin_deps(monkeypatch):
    # Mock supabase auth check
    mock_supabase = MagicMock()
    mock_supabase.auth.get_user.return_value = MagicMock(user=MagicMock(id="b43e8bb2-5369-42b7-a859-459f2ef020e9"))
    monkeypatch.setattr("app.api.deps.supabase", mock_supabase)

    # Mock DB user
    mock_admin = AdminUser(id=uuid.uuid4(), auth_user_id="b43e8bb2-5369-42b7-a859-459f2ef020e9", is_active=True)
    
    # We need to mock the db.query
    mock_db = MagicMock()
    mock_query = mock_db.query.return_value.filter.return_value
    mock_query.first.return_value = mock_admin
    
    # Monkeypatch get_db to return our mock
    def override_get_db():
        yield mock_db
        
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(verify_csrf_token, None)
    
    yield
    app.dependency_overrides = {}

def test_csrf_get_request_ignores_csrf(mock_admin_deps):
    # GET request doesn't need CSRF token
    response = client.get("/test/admin/get", cookies={"admin_access_token": "valid_token"})
    assert response.status_code == 200

def test_csrf_post_request_missing_cookie(mock_admin_deps):
    response = client.post("/test/admin/post", cookies={"admin_access_token": "valid_token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_csrf_post_request_missing_header(mock_admin_deps):
    response = client.post(
        "/test/admin/post", 
        cookies={"admin_access_token": "valid_token", "csrf_token": "test-csrf-value"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_csrf_post_request_mismatch(mock_admin_deps):
    response = client.post(
        "/test/admin/post", 
        cookies={"admin_access_token": "valid_token", "csrf_token": "test-csrf-value"},
        headers={"X-CSRF-Token": "different-value"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_csrf_post_request_success(mock_admin_deps):
    response = client.post(
        "/test/admin/post", 
        cookies={"admin_access_token": "valid_token", "csrf_token": "correct-csrf-value"},
        headers={"X-CSRF-Token": "correct-csrf-value"}
    )
    assert response.status_code == 200
