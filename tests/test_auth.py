import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import uuid

from app.main import app
from app.api.deps import get_current_admin_user, get_super_admin_user
from app.db.models.admin import AdminUser, AdminRole

# Dummy endpoints to test dependencies
@app.get("/api/v1/admin/test-auth", dependencies=[Depends(get_current_admin_user)])
def dummy_auth_route():
    return {"message": "success"}

@app.get("/api/v1/admin/test-super-auth", dependencies=[Depends(get_super_admin_user)])
def dummy_super_auth_route():
    return {"message": "super_success"}

client = TestClient(app)

class MockSupabaseUser:
    def __init__(self, user_id):
        self.id = user_id

class MockSupabaseResponse:
    def __init__(self, user_id):
        self.user = MockSupabaseUser(user_id)

@patch("app.api.deps.supabase.auth.get_user")
@patch("app.api.deps.SessionLocal")
def test_valid_admin(mock_session_local, mock_get_user):
    user_id = str(uuid.uuid4())
    mock_get_user.return_value = MockSupabaseResponse(user_id)
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_admin = AdminUser(auth_user_id=user_id, role=AdminRole.ADMIN, is_active=True)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin
    
    response = client.get("/api/v1/admin/test-auth", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 200
    assert response.json() == {"message": "success"}

@patch("app.api.deps.supabase.auth.get_user")
@patch("app.api.deps.SessionLocal")
def test_inactive_admin(mock_session_local, mock_get_user):
    user_id = str(uuid.uuid4())
    mock_get_user.return_value = MockSupabaseResponse(user_id)
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_admin = AdminUser(auth_user_id=user_id, role=AdminRole.ADMIN, is_active=False)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin
    
    response = client.get("/api/v1/admin/test-auth", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

@patch("app.api.deps.supabase.auth.get_user")
@patch("app.api.deps.SessionLocal")
def test_not_an_admin(mock_session_local, mock_get_user):
    user_id = str(uuid.uuid4())
    mock_get_user.return_value = MockSupabaseResponse(user_id)
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    response = client.get("/api/v1/admin/test-auth", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

@patch("app.api.deps.supabase.auth.get_user")
def test_invalid_token(mock_get_user):
    mock_get_user.side_effect = Exception("Invalid token")
    
    response = client.get("/api/v1/admin/test-auth", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401

@patch("app.api.deps.supabase.auth.get_user")
@patch("app.api.deps.SessionLocal")
def test_super_admin_route_success(mock_session_local, mock_get_user):
    user_id = str(uuid.uuid4())
    mock_get_user.return_value = MockSupabaseResponse(user_id)
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_admin = AdminUser(auth_user_id=user_id, role=AdminRole.SUPER_ADMIN, is_active=True)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin
    
    response = client.get("/api/v1/admin/test-super-auth", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 200

@patch("app.api.deps.supabase.auth.get_user")
@patch("app.api.deps.SessionLocal")
def test_super_admin_route_forbidden_for_normal_admin(mock_session_local, mock_get_user):
    user_id = str(uuid.uuid4())
    mock_get_user.return_value = MockSupabaseResponse(user_id)
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_admin = AdminUser(auth_user_id=user_id, role=AdminRole.ADMIN, is_active=True)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin
    
    response = client.get("/api/v1/admin/test-super-auth", headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_unauthenticated_request():
    response = client.get("/api/v1/admin/test-auth")
    assert response.status_code == 401
