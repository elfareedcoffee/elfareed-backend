import pytest
from app.main import app
from app.api.deps import verify_csrf_token
from app.core.config import settings
from cryptography.fernet import Fernet

def mock_verify_csrf():
    pass

@pytest.fixture(autouse=True)
def mock_settings():
    original_key = settings.SESSION_ENCRYPTION_KEY
    settings.SESSION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield
    settings.SESSION_ENCRYPTION_KEY = original_key

@pytest.fixture(autouse=True)
def default_dependency_overrides():
    # Globally mock CSRF validation to allow standard endpoint tests to pass
    # without needing to weave cookies and headers in every single test.
    # The CSRF mechanism itself is tested exclusively in test_admin_auth_csrf.py.
    app.dependency_overrides[verify_csrf_token] = mock_verify_csrf
    yield
    app.dependency_overrides.clear()
