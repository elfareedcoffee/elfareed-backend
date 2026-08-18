import pytest
from fastapi.testclient import TestClient
from app.main import app

# Because we are testing rate limits, we should be careful not to break other tests
# We will use a unique remote address for this client for rate limiting tests
client = TestClient(app)

def test_cors_headers_disallowed():
    # ALLOWED_ORIGINS is empty by default in tests
    response = client.options("/api/v1/public/products/", headers={"Origin": "https://attacker.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in response.headers

def test_cors_headers_allowed():
    from app.core.config import settings
    from app.main import create_app
    
    settings.ALLOWED_ORIGINS = ["https://approved.com"]
    test_app = create_app()
    test_client = TestClient(test_app)
    
    response = test_client.options("/api/v1/public/products/", headers={"Origin": "https://approved.com", "Access-Control-Request-Method": "GET"})
    assert response.headers.get("access-control-allow-origin") == "https://approved.com"
    
    # Clean up
    settings.ALLOWED_ORIGINS = []

def test_security_headers_default():
    response = client.get("/api/v1/public/products/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" not in response.headers

def test_security_headers_hsts_enabled():
    from app.core.config import settings
    settings.ENABLE_HSTS = True
    
    response = client.get("/api/v1/public/products/")
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    
    # Clean up
    settings.ENABLE_HSTS = False

def test_rate_limiting():
    custom_client = TestClient(app)
    payload = {"order_number": "ORD-RATE-LIMIT", "customer_phone": "+201012345678"}
    
    from app.core.limiter import limiter
    limiter.reset() # clear limits to isolate this test
    
    for i in range(5):
        resp = custom_client.post("/api/v1/public/orders/recover", json=payload)
        assert resp.status_code != 429

    resp = custom_client.post("/api/v1/public/orders/recover", json=payload)
    assert resp.status_code == 429

def test_no_secret_leakage_on_500(monkeypatch):
    # We want to force a 500 error to ensure stack traces and DB errors aren't leaked
    def mock_db_crash(*args, **kwargs):
        raise Exception("SECRET_DATABASE_PASSWORD_OR_TRACE")
    
    import app.crud.crud_product
    monkeypatch.setattr(app.crud.crud_product, "get_active_products", mock_db_crash)
    
    custom_client = TestClient(app, raise_server_exceptions=False)
    response = custom_client.get("/api/v1/public/products/")
    assert response.status_code == 500
    assert "SECRET_DATABASE_PASSWORD_OR_TRACE" not in response.text
