import pytest
import threading
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from decimal import Decimal
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.db.session import SessionLocal
from app.db.models.product import Product, ProductVariant, Category
from app.db.models.cart import Cart, CartItem
from app.db.models.order import Order, OrderItem

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def setup_test_product(db):
    cat_id = uuid4()
    cat = Category(id=cat_id, is_active=True)
    db.add(cat)
    
    prod_id = uuid4()
    prod = Product(id=prod_id, category_id=cat_id, is_active=True)
    db.add(prod)
    
    var_id = uuid4()
    var = ProductVariant(
        id=var_id,
        product_id=prod_id,
        weight_grams=250,
        grind_type="WHOLE_BEAN",
        price=Decimal("100.00"),
        stock_quantity=1, # EXACTLY 1 IN STOCK
        is_active=True
    )
    db.add(var)
    db.commit()
    return var_id

def cleanup_test_product(db, var_id):
    var = db.query(ProductVariant).filter_by(id=var_id).first()
    if var:
        prod_id = var.product_id
        cat_id = db.query(Product).filter_by(id=prod_id).first().category_id
        db.query(OrderItem).filter_by(product_variant_id=var_id).delete()
        db.query(CartItem).filter_by(product_variant_id=var_id).delete()
        db.query(ProductVariant).filter_by(id=var_id).delete()
        db.query(Product).filter_by(id=prod_id).delete()
        db.query(Category).filter_by(id=cat_id).delete()
        db.commit()

def test_concurrency_final_stock(db_session):
    var_id = setup_test_product(db_session)
    
    # Create 2 Carts for 2 Customers
    cart1 = Cart(id=uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart1_item = CartItem(id=uuid4(), cart_id=cart1.id, product_variant_id=var_id, quantity=1)
    
    cart2 = Cart(id=uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart2_item = CartItem(id=uuid4(), cart_id=cart2.id, product_variant_id=var_id, quantity=1)
    
    db_session.add(cart1)
    db_session.add(cart1_item)
    db_session.add(cart2)
    db_session.add(cart2_item)
    db_session.commit()
    
    responses = []
    
    def checkout(cart_id):
        with TestClient(app) as client:
            client.cookies.set("cart_id", str(cart_id))
            resp = client.post(
                "/api/v1/public/orders/",
                json={
                    "customer_name": "Test",
                    "customer_phone": "+201012345678",
                    "governorate": "Cairo",
                    "city": "Cairo",
                    "delivery_address": "Test",
                    "payment_method": "COD"
                }
            )
            responses.append(resp)
            
    # Fire requests concurrently
    t1 = threading.Thread(target=checkout, args=(cart1.id,))
    t2 = threading.Thread(target=checkout, args=(cart2.id,))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    # Assertions
    status_codes = [r.status_code for r in responses]
    assert 200 in status_codes, "Exactly one should succeed"
    assert 400 in status_codes, "Exactly one should fail"
    
    failed_resp = [r for r in responses if r.status_code == 400][0]
    assert "INSUFFICIENT_STOCK" in failed_resp.text
    
    # DB Checks
    db_session.expire_all()
    variant = db_session.query(ProductVariant).filter_by(id=var_id).first()
    assert variant.stock_quantity == 0, "Final stock must be exactly 0"
    
    # Cleanup
    cleanup_test_product(db_session, var_id)


def test_idempotency_duplicate_checkout(db_session):
    var_id = setup_test_product(db_session)
    
    # Create 1 Cart
    cart1 = Cart(id=uuid4(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    cart1_item = CartItem(id=uuid4(), cart_id=cart1.id, product_variant_id=var_id, quantity=1)
    
    db_session.add(cart1)
    db_session.add(cart1_item)
    db_session.commit()
    
    unique_name = f"Test Duplicate {uuid4()}"
    responses = []
    
    def checkout(cart_id_str):
        with TestClient(app) as client:
            client.cookies.set("cart_id", str(cart_id_str))
            resp = client.post(
                "/api/v1/public/orders/",
                json={
                    "customer_name": unique_name,
                    "customer_phone": "+201012345678",
                    "governorate": "Cairo",
                    "city": "Cairo",
                    "delivery_address": "Test",
                    "payment_method": "COD"
                }
            )
            responses.append(resp)
            
    # Fire 2 identical requests with the SAME cart concurrently
    cart_id_str = str(cart1.id)
    t1 = threading.Thread(target=checkout, args=(cart_id_str,))
    t2 = threading.Thread(target=checkout, args=(cart_id_str,))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 1, "Exactly one order must be created"
    assert status_codes.count(404) == 1 or status_codes.count(400) == 1, "The duplicate request must fail"
    
    db_session.expire_all()
    orders = db_session.query(Order).filter_by(customer_name=unique_name).all()
    assert len(orders) == 1, "Exactly one order exists in the database"
    
    # Cleanup
    cleanup_test_product(db_session, var_id)
    db_session.query(Order).filter_by(customer_name=unique_name).delete()
    db_session.commit()
