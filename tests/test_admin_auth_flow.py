import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timedelta, timezone

from app.main import app
from app.db.models.admin import AdminUser, AdminRole, AdminAuthChallenge
from app.crud.crud_admin_auth import create_challenge, hash_otp, encrypt_session_data, get_fernet

client = TestClient(app)

class MockSupabaseSession:
    def __init__(self, access_token="mock_access", refresh_token="mock_refresh", expires_in=3600):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in

class MockSupabaseAuthResponse:
    def __init__(self, user_id=str(uuid.uuid4())):
        self.user = MagicMock(id=user_id)
        self.session = MockSupabaseSession()

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
        is_active=True
    )

def test_login_success_initiates_otp(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.sign_in_with_password") as mock_signin, \
         patch("app.api.v1.admin.auth.sms_service.send_otp") as mock_send_otp:
         
        mock_signin.return_value = MockSupabaseAuthResponse()
        
        response = client.post("/api/v1/admin/auth/login", json={
            "username": "testadmin",
            "password": "valid_password"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["requires_verification"] is True
        assert "verification_id" in data
        
        mock_send_otp.assert_called_once()
    app.dependency_overrides.clear()

def test_login_invalid_username():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/api/v1/admin/auth/login", json={
        "username": "nonexistent",
        "password": "any_password"
    })
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    app.dependency_overrides.clear()

def test_login_inactive_admin(mock_admin_user):
    mock_admin_user.is_active = False
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.post("/api/v1/admin/auth/login", json={
        "username": "testadmin",
        "password": "any_password"
    })
    
    assert response.status_code == 401
    app.dependency_overrides.clear()

def test_login_invalid_password(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.sign_in_with_password") as mock_signin:
        mock_signin.side_effect = Exception("AuthApiError: Invalid login credentials")
        
        response = client.post("/api/v1/admin/auth/login", json={
            "username": "testadmin",
            "password": "wrong_password"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
    app.dependency_overrides.clear()

def test_sms_failure_aborts_login(mock_admin_user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.sign_in_with_password") as mock_signin, \
         patch("app.api.v1.admin.auth.sms_service.send_otp") as mock_send_otp:
         
        mock_signin.return_value = MockSupabaseAuthResponse()
        
        from app.services.sms import SMSProviderException
        mock_send_otp.side_effect = SMSProviderException("SMS Failed")
        
        response = client.post("/api/v1/admin/auth/login", json={
            "username": "testadmin",
            "password": "valid_password"
        })
        
        assert response.status_code == 500
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called()
    app.dependency_overrides.clear()

from app.api.deps import get_db

def test_verify_success():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    challenge_id = uuid.uuid4()
    code = "123456"
    hashed = hash_otp(code)
    session_data = {"access_token": "acc", "refresh_token": "ref"}
    encrypted = encrypt_session_data(session_data)
    
    challenge = AdminAuthChallenge(
        id=challenge_id,
        code_hash=hashed,
        encrypted_session=encrypted,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        attempts=0,
        max_attempts=3
    )
    
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = challenge
    
    response = client.post("/api/v1/admin/auth/verify", json={
        "verification_id": str(challenge_id),
        "code": code
    })
    
    assert response.status_code == 200
    assert "admin_access_token=acc" in response.headers["set-cookie"]
    assert "admin_refresh_token=ref" in response.headers["set-cookie"]
    assert "csrf_token=" in response.headers["set-cookie"]
    assert challenge.consumed_at is not None
    assert challenge.encrypted_session is None

def test_verify_expired():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    challenge_id = uuid.uuid4()
    challenge = AdminAuthChallenge(
        id=challenge_id,
        code_hash="...",
        encrypted_session="encrypted",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        attempts=0,
        max_attempts=3
    )
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = challenge
    
    response = client.post("/api/v1/admin/auth/verify", json={
        "verification_id": str(challenge_id),
        "code": "123456"
    })
    
    assert response.status_code == 400
    assert challenge.encrypted_session is None
    app.dependency_overrides.clear()

def test_verify_max_attempts():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    challenge_id = uuid.uuid4()
    challenge = AdminAuthChallenge(
        id=challenge_id,
        code_hash="...",
        encrypted_session="encrypted",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        attempts=3,
        max_attempts=3
    )
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = challenge
    
    response = client.post("/api/v1/admin/auth/verify", json={
        "verification_id": str(challenge_id),
        "code": "123456"
    })
    
    assert response.status_code == 400
    assert challenge.encrypted_session is None
    app.dependency_overrides.clear()

def test_verify_wrong_code():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    challenge_id = uuid.uuid4()
    hashed = hash_otp("123456")
    challenge = AdminAuthChallenge(
        id=challenge_id,
        code_hash=hashed,
        encrypted_session="encrypted",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        attempts=0,
        max_attempts=3
    )
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = challenge
    
    response = client.post("/api/v1/admin/auth/verify", json={
        "verification_id": str(challenge_id),
        "code": "000000"
    })
    
    assert response.status_code == 400
    assert challenge.attempts == 1
    assert challenge.encrypted_session == "encrypted"
    app.dependency_overrides.clear()

def test_verify_concurrent_lock():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    from sqlalchemy.exc import OperationalError
    mock_db.query.return_value.filter.return_value.with_for_update.return_value.first.side_effect = OperationalError("Lock", "params", "orig")
    
    response = client.post("/api/v1/admin/auth/verify", json={
        "verification_id": str(uuid.uuid4()),
        "code": "123456"
    })
    
    assert response.status_code == 400
    app.dependency_overrides.clear()

def test_refresh_success(mock_admin_user):
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.refresh_session") as mock_refresh:
        # Pass the exact auth_user_id to the mock
        specific_auth_user_id = str(mock_admin_user.auth_user_id)
        mock_refresh.return_value = MockSupabaseAuthResponse(user_id=specific_auth_user_id)
        
        def filter_side_effect(*args):
            mock_query = MagicMock()
            # Ensure the query filters by auth_user_id, not id
            # SQLAlchemy parameterized expressions won't contain the literal UUID string, 
            # so we just check the column name.
            if "auth_user_id" in str(args[0]):
                mock_query.first.return_value = mock_admin_user
            else:
                mock_query.first.return_value = None
            return mock_query
            
        mock_db.query.return_value.filter.side_effect = filter_side_effect
        
        response = client.post("/api/v1/admin/auth/refresh", cookies={
            "admin_refresh_token": "valid_refresh_token"
        })
        
        assert response.status_code == 200
        assert "admin_access_token=mock_access" in response.headers["set-cookie"]
        assert "admin_refresh_token=mock_refresh" in response.headers["set-cookie"]
        assert "csrf_token=" in response.headers["set-cookie"]

def test_refresh_invalid_or_revoked_token():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.refresh_session") as mock_refresh:
        mock_refresh.side_effect = Exception("AuthSessionMissingError: Invalid Refresh Token: Refresh Token Not Found")
        
        response = client.post("/api/v1/admin/auth/refresh", cookies={
            "admin_refresh_token": "invalid_or_revoked_token"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_refresh_malformed_request():
    response = client.post("/api/v1/admin/auth/refresh")
    
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_refresh_supabase_unavailable():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.refresh_session") as mock_refresh:
        mock_refresh.side_effect = Exception("ConnectionError")
        
        response = client.post("/api/v1/admin/auth/refresh", cookies={
            "admin_refresh_token": "any_token"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_refresh_inactive_admin(mock_admin_user):
    mock_admin_user.is_active = False
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.refresh_session") as mock_refresh:
        mock_refresh.return_value = MockSupabaseAuthResponse()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user
        
        response = client.post("/api/v1/admin/auth/refresh", cookies={
            "admin_refresh_token": "any_token"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

def test_refresh_unknown_admin():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.v1.admin.auth.supabase.auth.refresh_session") as mock_refresh:
        mock_refresh.return_value = MockSupabaseAuthResponse()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post("/api/v1/admin/auth/refresh", cookies={
            "admin_refresh_token": "any_token"
        })
        
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
