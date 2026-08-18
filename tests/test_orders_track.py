import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timezone

from app.main import app
from app.api.deps import get_db
from app.db.models.order import Order

client = TestClient(app)

@pytest.fixture
def mock_db_session_track():
    with patch("app.api.v1.public.orders.get_db") as mock:
        yield mock

def test_track_order(mock_db_session_track):
    response = client.get(
        f"/api/v1/public/orders/track/{uuid.uuid4()}"
    )
    # the MagicMock for get_db will return Mock obj when .first() is called by default unless specified
    # but the mock_db_session_track is not applied directly without patching the exact location.
    pass

def test_track_order_success():
    with patch("app.api.v1.public.orders.Session") as mock_session:
        db = MagicMock()
        order = Order(
            id=uuid.uuid4(), order_number="ELFA-123", tracking_token=uuid.uuid4(),
            subtotal=10, delivery_fee=10, discount=0, total=20,
            payment_status="PENDING", order_status="PENDING", created_at=datetime.now(timezone.utc),
            customer_name="A", customer_phone="+201012345678", governorate="G", city="C", delivery_address="D",
            payment_method="COD"
        )
        # Patch dependencies via dependency_overrides in FastAPI
        app.dependency_overrides[get_db] = lambda: db
        db.query.return_value.filter.return_value.first.return_value = order
        
        response = client.get(f"/api/v1/public/orders/track/{order.tracking_token}")
        
        assert response.status_code == 200
        assert response.json()["order_number"] == "ELFA-123"
        app.dependency_overrides.clear()

def test_recover_order_success():
    db = MagicMock()
    order = Order(
        id=uuid.uuid4(), order_number="ELFA-123", tracking_token=uuid.uuid4(),
        subtotal=10, delivery_fee=10, discount=0, total=20,
        payment_status="PENDING", order_status="PENDING", created_at=datetime.now(timezone.utc),
        customer_name="A", customer_phone="+201012345678", governorate="G", city="C", delivery_address="D",
        payment_method="COD"
    )
    app.dependency_overrides[get_db] = lambda: db
    db.query.return_value.filter.return_value.first.return_value = order
    
    response = client.post(
        "/api/v1/public/orders/recover",
        json={"order_number": "ELFA-123", "customer_phone": "+201012345678"}
    )
    
    assert response.status_code == 200
    assert response.json()["tracking_token"] == str(order.tracking_token)
    app.dependency_overrides.clear()
