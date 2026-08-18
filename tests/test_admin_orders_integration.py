import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from decimal import Decimal

from app.main import app
from app.db.session import SessionLocal
from app.db.models.order import Order, OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum
from app.db.models.product import ProductVariant, Product, Category
from app.api.deps import get_current_admin_user

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def setup_mock_admin():
    app.dependency_overrides[get_current_admin_user] = lambda: {"id": uuid.uuid4(), "role": "ADMIN", "is_active": True}

def teardown_mock_admin():
    app.dependency_overrides.clear()

def setup_test_orders(db):
    prefix = f"INT-{uuid.uuid4().hex[:6].upper()}"
    orders = []
    for i in range(15):
        o = Order(
            id=uuid.uuid4(),
            order_number=f"{prefix}-{i}",
            tracking_token=uuid.uuid4(),
            customer_name="Int Test",
            customer_phone=f"+2010{10000000 + i}",
            governorate="Cairo",
            city="Cairo",
            delivery_address="Test",
            payment_method=PaymentMethodEnum.COD,
            payment_status=PaymentStatusEnum.PENDING if i % 2 == 0 else PaymentStatusEnum.PAID,
            order_status=OrderStatusEnum.PENDING if i < 10 else OrderStatusEnum.CONFIRMED,
            subtotal=Decimal('100.00'),
            delivery_fee=Decimal('50.00'),
            total=Decimal('150.00')
        )
        db.add(o)
        orders.append(o)
    db.commit()
    return prefix, orders

def cleanup_test_orders(db, prefix):
    db.query(Order).filter(Order.order_number.like(f"{prefix}%")).delete(synchronize_session=False)
    db.commit()

def test_admin_orders_integration(db_session):
    setup_mock_admin()
    prefix, orders_list = setup_test_orders(db_session)
    
    with TestClient(app) as client:
        # 1. Pagination Default (page=1, size=20) - Should fetch all 15 test orders + whatever is in DB
        resp = client.get("/api/v1/admin/orders/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 20
        assert "total_pages" in data
        assert data["total"] >= 15
        
        # 2. Search by order number
        resp = client.get(f"/api/v1/admin/orders/?search={prefix}-5")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["order_number"] == f"{prefix}-5"
        
        # 3. Search by customer phone
        resp = client.get(f"/api/v1/admin/orders/?search=%2B201010000007")
        data = resp.json()
        assert data["total"] >= 1
        assert any(item["order_number"] == f"{prefix}-7" for item in data["items"])
        
        # 4. Status Filtering
        resp = client.get(f"/api/v1/admin/orders/?search={prefix}&order_status=CONFIRMED")
        data = resp.json()
        assert data["total"] == 5
        
        # 5. Payment Status Filtering
        resp = client.get(f"/api/v1/admin/orders/?search={prefix}&payment_status=PAID")
        data = resp.json()
        assert data["total"] == 7
        
        # 6. Sorting check (descending by created_at)
        resp = client.get(f"/api/v1/admin/orders/?search={prefix}&size=15")
        data = resp.json()
        items = data["items"]
        for i in range(len(items) - 1):
            assert datetime.fromisoformat(items[i]["created_at"]) >= datetime.fromisoformat(items[i+1]["created_at"])
            
        # 7. Valid Status Update
        order_id = str(orders_list[0].id) # PENDING
        resp = client.put(f"/api/v1/admin/orders/{order_id}/status", json={"status": "CONFIRMED"})
        assert resp.status_code == 200
        assert resp.json()["order_status"] == "CONFIRMED"
        
        # 8. Invalid Status Update
        resp = client.put(f"/api/v1/admin/orders/{order_id}/status", json={"status": "DELIVERED"})
        assert resp.status_code == 400
        assert "Invalid status transition" in resp.text
        
    cleanup_test_orders(db_session, prefix)
    teardown_mock_admin()

def test_admin_order_cancellation_integration(db_session):
    setup_mock_admin()
    
    # Create product and variant
    cat = Category(id=uuid.uuid4(), is_active=True)
    db_session.add(cat)
    prod = Product(id=uuid.uuid4(), category_id=cat.id, is_active=True)
    db_session.add(prod)
    var = ProductVariant(id=uuid.uuid4(), product_id=prod.id, stock_quantity=10, weight_grams=250, grind_type="WHOLE_BEAN", price=100)
    db_session.add(var)
    db_session.commit()
    
    prefix, orders_list = setup_test_orders(db_session)
    order = orders_list[0]
    
    # Attach item
    from app.db.models.order import OrderItem
    item = OrderItem(id=uuid.uuid4(), order_id=order.id, product_variant_id=var.id, quantity=3, product_name_ar="Test", product_name_en="Test", weight_grams=250, grind_type="WHOLE_BEAN", unit_price=100, total_price=300)
    db_session.add(item)
    db_session.commit()
    
    with TestClient(app) as client:
        resp = client.post(f"/api/v1/admin/orders/{order.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["order_status"] == "CANCELLED"
        
        db_session.expire_all()
        var_db = db_session.query(ProductVariant).filter_by(id=var.id).first()
        assert var_db.stock_quantity == 13 # Stock restored perfectly!
        
    db_session.query(OrderItem).filter_by(order_id=order.id).delete()
    cleanup_test_orders(db_session, prefix)
    db_session.delete(var)
    db_session.delete(prod)
    db_session.delete(cat)
    db_session.commit()
    teardown_mock_admin()
