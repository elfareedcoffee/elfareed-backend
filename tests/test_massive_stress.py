import pytest
import uuid
import concurrent.futures
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.core.limiter import limiter
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.db.models.order import Order, OrderItem, OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum
from app.db.models.product import Product, ProductVariant, Category, ProductTranslation, LanguageEnum
from app.api.deps import get_current_admin_user, get_current_supabase_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_stress_db():
    Base.metadata.create_all(bind=engine)
    limiter.reset()
    yield
    limiter.reset()

def test_high_volume_public_catalog_burst():
    """Burst test: 100 concurrent requests to public catalog."""
    def fetch_catalog():
        custom_client = TestClient(app)
        res = custom_client.get("/api/v1/public/products/")
        return res.status_code, len(res.json()) if res.status_code == 200 else 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_catalog) for _ in range(100)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    status_codes = [r[0] for r in results]
    success_count = status_codes.count(200)
    assert success_count == 100, f"Expected 100/100 requests to succeed, got {success_count}/100"

def test_database_connection_pool_under_concurrency():
    """Stress test: 50 concurrent DB sessions executing queries and verifying clean pool release."""
    def db_worker():
        db = SessionLocal()
        try:
            products = db.query(Product).all()
            return len(products)
        finally:
            db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(db_worker) for _ in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 50

def test_concurrent_order_stock_race_condition():
    """Concurrency test: 20 concurrent threads trying to purchase from a limited stock of 5."""
    db = SessionLocal()
    try:
        # Create category, product, and variant with stock = 5
        cat = Category(id=uuid.uuid4(), is_active=True)
        prod = Product(id=uuid.uuid4(), category_id=cat.id, is_active=True)
        trans = ProductTranslation(id=uuid.uuid4(), product_id=prod.id, language=LanguageEnum.ar, name="قهوة فريد وسط", description="وصف")
        variant = ProductVariant(id=uuid.uuid4(), product_id=prod.id, stock_quantity=5, weight_grams=250, grind_type="WHOLE_BEAN", price=120)
        
        db.add_all([cat, prod, trans, variant])
        db.commit()
        variant_id = variant.id
    finally:
        db.close()

    def attempt_order(buyer_index):
        custom_client = TestClient(app)
        limiter.reset()
        order_payload = {
            "customer_name": f"Buyer {buyer_index}",
            "customer_phone": f"+2010{buyer_index:08d}",
            "governorate": "القاهرة",
            "city": "مدينة نصر",
            "delivery_address": f"Building {buyer_index}",
            "payment_method": "COD",
            "items": [
                {
                    "product_variant_id": str(variant_id),
                    "quantity": 1,
                    "unit_price": 120.0
                }
            ]
        }
        res = custom_client.post("/api/v1/public/orders/", json=order_payload)
        return res.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_order, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Verify results
    success_orders = results.count(200) + results.count(201)
    
    # Check final stock in DB
    db_verify = SessionLocal()
    try:
        v = db_verify.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
        assert v.stock_quantity >= 0, f"Stock went negative: {v.stock_quantity}"
    finally:
        db_verify.close()
