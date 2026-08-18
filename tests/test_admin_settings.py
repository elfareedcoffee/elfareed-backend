import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timedelta, timezone

from app.main import app
from app.db.models.admin import AdminUser, AdminRole, AdminPhoneChangeChallenge
from app.crud.crud_admin_auth import hash_otp

client = TestClient(app)

@pytest.fixture
def mock_admin_user():
    return AdminUser(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        username="testadmin",
        email="testadmin@example.com",
        phone_number="+1234567890",
        name="Test Admin",
        role=AdminRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

def test_get_me_success(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    
    from app.api.deps import get_db, get_current_supabase_user, verify_csrf_token
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_supabase_user] = lambda: str(mock_admin_user.auth_user_id)
    app.dependency_overrides[verify_csrf_token] = lambda: None
    
    response = client.get("/api/v1/admin/auth/me")
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testadmin"
    assert data["email"] == "testadmin@example.com"
    assert data["phone_number"] == "+1234567890"
    assert data["is_active"] is True
    
    app.dependency_overrides.clear()

def test_update_profile_success(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    
    from app.api.deps import get_db, get_current_supabase_user, verify_csrf_token
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_supabase_user] = lambda: str(mock_admin_user.auth_user_id)
    app.dependency_overrides[verify_csrf_token] = lambda: None
    
    response = client.patch("/api/v1/admin/auth/profile", json={"name": "New Name"})
    
    assert response.status_code == 200
    assert mock_admin_user.name == "New Name"
    mock_db.commit.assert_called_once()
    
    app.dependency_overrides.clear()

def test_request_phone_change_success(mock_admin_user):
    mock_db = MagicMock()
    # First query is for existing phone number, return None
    # Second query is inside get_current_admin_user, return mock_admin_user
    def side_effect(*args, **kwargs):
        mock_query = MagicMock()
        if "phone_number" in str(args):
             mock_query.filter.return_value.first.return_value = None
        else:
             mock_query.filter.return_value.first.return_value = mock_admin_user
        return mock_query
        
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_admin_user, None]
    
    from app.api.deps import get_db, get_current_supabase_user, verify_csrf_token
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_supabase_user] = lambda: str(mock_admin_user.auth_user_id)
    app.dependency_overrides[verify_csrf_token] = lambda: None
    
    with patch("app.api.v1.admin.auth.sms_service.send_otp") as mock_send_otp:
        response = client.post("/api/v1/admin/auth/security/phone/request", json={
            "new_phone_number": "+201000000000"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["requires_verification"] is True
        assert "verification_id" in data
        mock_send_otp.assert_called_once()
        
    app.dependency_overrides.clear()

def test_verify_phone_change_success(mock_admin_user):
    mock_db = MagicMock()
    from app.api.deps import get_db, get_current_supabase_user, verify_csrf_token
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_supabase_user] = lambda: str(mock_admin_user.auth_user_id)
    app.dependency_overrides[verify_csrf_token] = lambda: None
    
    # Needs a mock for get_current_admin_user
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user

    challenge_id = uuid.uuid4()
    code = "123456"
    hashed = hash_otp(code)
    
    challenge = AdminPhoneChangeChallenge(
        id=challenge_id,
        admin_user_id=mock_admin_user.id,
        new_phone_number="+201000000000",
        code_hash=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        attempts=0,
        max_attempts=3
    )
    
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = challenge
    
    response = client.post("/api/v1/admin/auth/security/phone/verify", json={
        "verification_id": str(challenge_id),
        "code": code
    })
    
    assert response.status_code == 200
    assert challenge.consumed_at is not None
    assert mock_admin_user.phone_number == "+201000000000"
    
    app.dependency_overrides.clear()

def test_change_password_success(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    
    from app.api.deps import get_db, get_current_supabase_user, verify_csrf_token
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_supabase_user] = lambda: str(mock_admin_user.auth_user_id)
    app.dependency_overrides[verify_csrf_token] = lambda: None
    
    class MockSupabaseAuthResponse:
        def __init__(self):
            self.user = MagicMock()
    
    with patch("app.api.v1.admin.auth.supabase.auth.sign_in_with_password") as mock_signin, \
         patch("app.api.v1.admin.auth.supabase_admin.auth.admin.update_user_by_id") as mock_update:
         
        mock_signin.return_value = MockSupabaseAuthResponse()
        mock_update.return_value = MockSupabaseAuthResponse()
        
        response = client.post("/api/v1/admin/auth/security/password", json={
            "current_password": "old_password",
            "new_password": "new_password"
        })
        
        assert response.status_code == 200
        mock_signin.assert_called_once_with({"email": mock_admin_user.email, "password": "old_password"})
        mock_update.assert_called_once_with(str(mock_admin_user.auth_user_id), {"password": "new_password"})
        
    app.dependency_overrides.clear()
