import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.main import app
from app.db.models.order import Order, OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum
from app.schemas.order import OrderStatusUpdateRequest

client = TestClient(app)

@pytest.fixture
def mock_admin_user():
    return {"id": uuid.uuid4(), "role": "ADMIN", "is_active": True}

@pytest.fixture
def mock_super_admin_user():
    return {"id": uuid.uuid4(), "role": "SUPER_ADMIN", "is_active": True}

@pytest.fixture
def mock_get_current_admin():
    from app.api.deps import get_current_admin_user
    # We will override this per-test via app.dependency_overrides
    pass

@pytest.fixture
def mock_crud_admin_order():
    with patch("app.api.v1.admin.orders.crud_admin_order") as mock:
        yield mock

def test_unauthorized_access():
    # Attempting to access admin route without being authenticated
    response = client.get("/api/v1/admin/orders/")
    # Depends(get_current_admin_user) would normally throw 401
    # We haven't mocked it here, so it should hit the real dependency and fail
    assert response.status_code == 401

def test_admin_access_list_orders(mock_crud_admin_order, mock_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    mock_crud_admin_order.get_orders_paginated.return_value = {
        "items": [], "total": 0, "page": 1, "size": 20, "total_pages": 0
    }
    
    response = client.get("/api/v1/admin/orders/")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    app.dependency_overrides.clear()

def test_super_admin_access_list_orders(mock_crud_admin_order, mock_super_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_super_admin_user
    mock_crud_admin_order.get_orders_paginated.return_value = {
        "items": [], "total": 0, "page": 1, "size": 20, "total_pages": 0
    }
    
    response = client.get("/api/v1/admin/orders/")
    assert response.status_code == 200
    app.dependency_overrides.clear()
    
def test_order_filtering_and_pagination(mock_crud_admin_order, mock_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    mock_crud_admin_order.get_orders_paginated.return_value = {
        "items": [], "total": 100, "page": 2, "size": 10, "total_pages": 10
    }
    
    response = client.get("/api/v1/admin/orders/?page=2&size=10&search=123&order_status=PENDING")
    assert response.status_code == 200
    assert response.json()["total"] == 100
    mock_crud_admin_order.get_orders_paginated.assert_called_once()
    kwargs = mock_crud_admin_order.get_orders_paginated.call_args.kwargs
    assert kwargs["page"] == 2
    assert kwargs["size"] == 10
    assert kwargs["search"] == "123"
    assert kwargs["order_status"] == OrderStatusEnum.PENDING
    app.dependency_overrides.clear()

def test_get_order_details(mock_crud_admin_order, mock_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    order_id = uuid.uuid4()
    
    mock_order = Order(
        id=order_id, order_number="123", tracking_token=uuid.uuid4(),
        subtotal=10, delivery_fee=10, discount=0, total=20, customer_name="Test",
        customer_phone="+201012345678", governorate="G", city="C", delivery_address="A",
        payment_method="COD", payment_status="PENDING", order_status="PENDING",
        created_at=datetime.now(timezone.utc)
    )
    mock_crud_admin_order.get_order_by_id.return_value = mock_order
    
    response = client.get(f"/api/v1/admin/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(order_id)
    app.dependency_overrides.clear()

def test_valid_status_transition(mock_crud_admin_order, mock_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    order_id = uuid.uuid4()
    
    mock_order = Order(
        id=order_id, order_number="123", tracking_token=uuid.uuid4(),
        subtotal=10, delivery_fee=10, discount=0, total=20, customer_name="Test",
        customer_phone="+201012345678", governorate="G", city="C", delivery_address="A",
        payment_method="COD", payment_status="PENDING", order_status="CONFIRMED",
        created_at=datetime.now(timezone.utc)
    )
    mock_crud_admin_order.update_order_status.return_value = mock_order
    
    response = client.put(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "CONFIRMED"}
    )
    assert response.status_code == 200
    assert response.json()["order_status"] == "CONFIRMED"
    app.dependency_overrides.clear()

# Test the actual CRUD state machine
from app.crud.crud_admin_order import update_order_status
from fastapi import HTTPException

def test_crud_invalid_status_transition():
    db = MagicMock()
    order_id = uuid.uuid4()
    mock_order = Order(id=order_id, order_status=OrderStatusEnum.PENDING)
    db.query.return_value.filter.return_value.first.return_value = mock_order
    
    with pytest.raises(HTTPException) as exc:
        update_order_status(db, str(order_id), OrderStatusEnum.DELIVERED)
    assert exc.value.status_code == 400
    assert "Invalid status transition" in exc.value.detail

def test_crud_valid_status_transition():
    db = MagicMock()
    order_id = uuid.uuid4()
    mock_order = Order(id=order_id, order_status=OrderStatusEnum.READY_FOR_DELIVERY)
    db.query.return_value.filter.return_value.first.return_value = mock_order
    
    result = update_order_status(db, str(order_id), OrderStatusEnum.OUT_FOR_DELIVERY)
    assert result.order_status == OrderStatusEnum.OUT_FOR_DELIVERY
    db.commit.assert_called_once()

def test_unauthorized_order_cancellation():
    response = client.post(
        f"/api/v1/admin/orders/{uuid.uuid4()}/cancel"
    )
    assert response.status_code == 401

def test_admin_get_nonexistent_order(mock_admin_user, mock_crud_admin_order):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    mock_crud_admin_order.get_order_by_id.return_value = None
    response = client.get(f"/api/v1/admin/orders/{uuid.uuid4()}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404
    app.dependency_overrides.clear()

def test_admin_order_invalid_uuid(mock_admin_user):
    from app.api.deps import get_current_admin_user
    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    response = client.get("/api/v1/admin/orders/invalid-uuid", headers={"Authorization": "Bearer token"})
    assert response.status_code == 422
    app.dependency_overrides.clear()
