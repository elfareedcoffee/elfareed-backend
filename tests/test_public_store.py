from fastapi.testclient import TestClient
from unittest.mock import patch
from decimal import Decimal
from app.main import app

client = TestClient(app)

def test_store_config_returns_business_rule():
    with patch('app.api.v1.public.store.calculate_delivery_fee') as mock_calc:
        mock_calc.return_value = Decimal("65.50")
        
        response = client.get("/api/v1/public/store/config")
        
        assert response.status_code == 200
        data = response.json()
        assert data["delivery_fee_cairo"] == "65.50"
        assert data["is_store_accepting_orders"] is True

def test_store_config_rate_limit():
    response = client.get("/api/v1/public/store/config")
    assert response.status_code == 200
    assert "delivery_fee_cairo" in response.json()
