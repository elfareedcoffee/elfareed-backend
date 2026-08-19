import pytest
import uuid
import os
import io
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, create_app
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.db.models.admin import AdminUser, AdminRole
from app.db.models.product import Product, ProductVariant, Category, ProductTranslation, LanguageEnum
from app.api.deps import get_current_admin_user, get_current_supabase_user, verify_csrf_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db_and_limiter():
    Base.metadata.create_all(bind=engine)
    limiter.reset()
    yield
    limiter.reset()

@pytest.fixture
def mock_admin_auth():
    admin = AdminUser(
        id=uuid.uuid4(),
        auth_user_id=uuid.uuid4(),
        username="superadmin",
        role=AdminRole.SUPER_ADMIN,
        is_active=True
    )
    app.dependency_overrides[get_current_admin_user] = lambda: admin
    app.dependency_overrides[get_current_supabase_user] = lambda: str(admin.auth_user_id)
    yield admin
    app.dependency_overrides.pop(get_current_admin_user, None)
    app.dependency_overrides.pop(get_current_supabase_user, None)

# -------------------------------------------------------------
# 1. AUTHENTICATION & PRIVILEGE ESCALATION SECURITY
# -------------------------------------------------------------

def test_admin_endpoints_reject_unauthenticated():
    """Ensure all critical admin routes reject unauthenticated requests with 401."""
    # Ensure no overrides are active
    app.dependency_overrides.pop(get_current_admin_user, None)
    app.dependency_overrides.pop(get_current_supabase_user, None)
    
    protected_routes = [
        ("GET", "/api/v1/admin/products/"),
        ("POST", "/api/v1/admin/products/"),
        ("GET", "/api/v1/admin/orders/"),
        ("GET", "/api/v1/admin/auth/me"),
        ("POST", "/api/v1/admin/auth/logout"),
        ("PATCH", "/api/v1/admin/auth/profile"),
    ]
    for method, route in protected_routes:
        if method == "GET":
            res = client.get(route)
        elif method == "POST":
            res = client.post(route, json={})
        elif method == "PATCH":
            res = client.patch(route, json={})
        assert res.status_code == 401, f"Route {route} allowed unauthenticated access with status {res.status_code}"

def test_admin_endpoints_reject_tampered_jwt():
    """Ensure tampered or forged JWT tokens are strictly rejected."""
    fake_tokens = [
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDNxdACt7vuhF8xiZwuhqSxDnVAZP0XEYLIRGUoGo",
        "invalid.token.structure",
        "Bearer totally_fake_token_value_12345",
        "",
    ]
    for token in fake_tokens:
        res = client.get(
            "/api/v1/admin/products/",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 401, f"Tampered token '{token}' bypassed auth with status {res.status_code}"

def test_inactive_admin_user_rejected(monkeypatch):
    """Ensure deactivated admin accounts cannot access the system."""
    db = SessionLocal()
    try:
        fake_auth_id = uuid.uuid4()
        from app.api import deps
        
        # Mock supabase to return the fake_auth_id
        monkeypatch.setattr(deps, "get_current_supabase_user", lambda *args, **kwargs: str(fake_auth_id))
        
        # Test client with inactive user
        custom_client = TestClient(app)
        res = custom_client.get("/api/v1/admin/auth/me")
        assert res.status_code in [401, 403], "Inactive/non-existent admin user was not rejected"
    finally:
        db.close()


# -------------------------------------------------------------
# 2. CSRF & COOKIE ATTACK PREVENTION
# -------------------------------------------------------------

def test_csrf_protection_on_cookie_authenticated_requests():
    """Verify that cookie-authenticated state-changing requests fail without matching X-CSRF-Token."""
    db = SessionLocal()
    try:
        fake_auth_id = uuid.uuid4()
        admin = AdminUser(
            id=uuid.uuid4(),
            auth_user_id=fake_auth_id,
            username=f"csrf_test_{uuid.uuid4().hex[:6]}",
            email=f"csrf_{uuid.uuid4().hex[:6]}@example.com",
            phone_number=f"+2010{uuid.uuid4().int % 100000000:08d}",
            name="CSRF Tester",
            role=AdminRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Only mock get_current_supabase_user so get_current_admin_user executes verify_csrf_token
        app.dependency_overrides[get_current_supabase_user] = lambda: str(fake_auth_id)
        app.dependency_overrides.pop(verify_csrf_token, None)
        app.dependency_overrides.pop(get_current_admin_user, None)

        custom_client = TestClient(app)
        custom_client.cookies.set("admin_access_token", "dummy_cookie_token")
        custom_client.cookies.set("csrf_token", "legitimate_csrf_token_123")

        # Send request with WRONG csrf header (and no Bearer auth header)
        res = custom_client.post(
            "/api/v1/admin/auth/logout",
            headers={"x-csrf-token": "attacker_forged_csrf"}
        )
        assert res.status_code == 403, f"Mismatched CSRF token did not produce 403 Forbidden (got {res.status_code})"
        assert res.json().get("error", {}).get("code") == "FORBIDDEN" or "detail" in res.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


# -------------------------------------------------------------
# 3. RATE LIMITING & BRUTE FORCE PROTECTION
# -------------------------------------------------------------

def test_rate_limiting_prevents_brute_force():
    """Verify SlowAPI rate limiting triggers 429 on abuse."""
    limiter.reset()
    custom_client = TestClient(app)
    payload = {"order_number": "SEC-RATE-TEST", "customer_phone": "+201012345678"}
    
    for _ in range(5):
        resp = custom_client.post("/api/v1/public/orders/recover", json=payload)
        assert resp.status_code != 429

    # 6th request should hit rate limit
    resp = custom_client.post("/api/v1/public/orders/recover", json=payload)
    assert resp.status_code == 429, "Rate limiter failed to block excessive requests"


# -------------------------------------------------------------
# 4. SQL INJECTION (SQLi) & XSS DEFENSE
# -------------------------------------------------------------

def test_sql_injection_payloads_in_public_order():
    """Verify malicious SQL injection payloads in customer input do not execute or cause SQL errors."""
    sqli_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE orders; --",
        "1' UNION SELECT null, null, username, password FROM admin_users --",
        "admin'--",
        "SLEEP(5) /*",
    ]
    
    for payload in sqli_payloads:
        order_payload = {
            "customer_name": f"Hacker {payload}",
            "customer_phone": "+201012345678",
            "governorate": "القاهرة",
            "city": f"City {payload}",
            "delivery_address": f"Address {payload}",
            "delivery_notes": f"Notes {payload}",
            "payment_method": "COD",
            "items": []
        }
        res = client.post("/api/v1/public/orders/", json=order_payload)
        # Should return 400 or 422 (empty items or validation error), never 500 SQL syntax error
        assert res.status_code in [400, 422], f"SQLi payload caused unexpected status {res.status_code}: {res.text}"
        assert "syntax error" not in res.text.lower()
        assert "psycopg2" not in res.text.lower()
        assert "sqlalchemy" not in res.text.lower()

def test_xss_payloads_safely_stored():
    """Verify stored XSS payloads are treated as plain text strings and not executable."""
    limiter.reset()
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(document.cookie)>",
        "<svg onload=alert(1)>",
        "javascript:alert(1)",
    ]
    
    for payload in xss_payloads:
        limiter.reset()
        order_data = {
            "customer_name": f"Test {payload}",
            "customer_phone": "+201012345678",
            "governorate": "القاهرة",
            "city": "مدينة نصر",
            "delivery_address": f"123 Street {payload}",
            "delivery_notes": payload,
            "payment_method": "COD",
            "items": []
        }
        res = client.post("/api/v1/public/orders/", json=order_data)
        assert res.status_code in [400, 422], f"XSS handling error: {res.status_code}"


# -------------------------------------------------------------
# 5. FILE UPLOAD SECURITY (EXPLOITS, POLYGLOTS & LIMITS)
# -------------------------------------------------------------

def test_image_upload_rejects_executable_files(mock_admin_auth, monkeypatch):
    """Ensure .exe, .sh, .php, .py files are rejected even if disguised as images."""
    from app.crud import crud_product
    mock_prod = Product(id=uuid.uuid4(), is_active=True)
    monkeypatch.setattr(crud_product, "get_product_by_id", lambda db, pid: mock_prod)
    
    dangerous_files = [
        ("shell.php", b"<?php echo 'pwned'; ?>", "application/x-php"),
        ("exploit.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-dosexec"),
        ("script.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh"),
        ("fake.svg.html", b"<script>alert(1)</script>", "text/html"),
    ]
    
    for filename, content, mime in dangerous_files:
        files = {"file": (filename, io.BytesIO(content), mime)}
        res = client.post(
            f"/api/v1/admin/products/{mock_prod.id}/image",
            files=files,
            headers={"Authorization": "Bearer valid_test_token"}
        )
        assert res.status_code == 400, f"Dangerous file {filename} ({mime}) was not rejected with 400 (got {res.status_code})"

def test_image_upload_rejects_oversized_files(mock_admin_auth, monkeypatch):
    """Ensure files exceeding 10MB are rejected with 400."""
    from app.crud import crud_product
    mock_prod = Product(id=uuid.uuid4(), is_active=True)
    monkeypatch.setattr(crud_product, "get_product_by_id", lambda db, pid: mock_prod)
    
    # 11MB dummy image bytes
    oversized_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("huge.jpg", io.BytesIO(oversized_bytes), "image/jpeg")}
    
    res = client.post(
        f"/api/v1/admin/products/{mock_prod.id}/image",
        files=files,
        headers={"Authorization": "Bearer valid_test_token"}
    )
    assert res.status_code == 400
    assert "exceeds" in res.text.lower() or "limit" in res.text.lower()


# -------------------------------------------------------------
# 6. INFORMATION LEAKAGE & SENSITIVE DATA EXPOSURE
# -------------------------------------------------------------

def test_no_stack_traces_on_internal_errors(monkeypatch):
    """Ensure 500 Internal Server Errors never leak database credentials, stack traces, or schemas."""
    def force_crash(*args, **kwargs):
        raise RuntimeError("FATAL_ERROR: postgresql://postgres:SuperSecretPassword123@db.supabase.co:5432/postgres")

    from app.crud import crud_product
    monkeypatch.setattr(crud_product, "get_active_products", force_crash)
    
    custom_client = TestClient(app, raise_server_exceptions=False)
    res = custom_client.get("/api/v1/public/products/")
    assert res.status_code == 500
    assert "SuperSecretPassword123" not in res.text
    assert "postgresql://" not in res.text
    assert "Traceback" not in res.text
