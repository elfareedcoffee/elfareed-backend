import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid

from app.main import app
from app.db.models.product import Category, CategoryTranslation, LanguageEnum, Product, ProductTranslation, ProductVariant, GrindTypeEnum

client = TestClient(app)

@pytest.fixture
def mock_crud_category_public():
    with patch("app.api.v1.storefront.categories.crud_category") as mock:
        yield mock

@pytest.fixture
def mock_crud_product_public():
    with patch("app.api.v1.storefront.products.crud_product") as mock:
        yield mock

def test_public_categories_default_arabic(mock_crud_category_public):
    cat_id = uuid.uuid4()
    cat = Category(id=cat_id, is_active=True, sort_order=0)
    cat.translations = [
        CategoryTranslation(id=uuid.uuid4(), language=LanguageEnum.ar, name="قهوة", description=""),
        CategoryTranslation(id=uuid.uuid4(), language=LanguageEnum.en, name="Coffee", description="")
    ]
    mock_crud_category_public.get_active_categories.return_value = [cat]
    
    response = client.get("/api/v1/public/categories/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "قهوة" # Defaults to Arabic

def test_public_categories_accept_language_en(mock_crud_category_public):
    cat_id = uuid.uuid4()
    cat = Category(id=cat_id, is_active=True, sort_order=0)
    cat.translations = [
        CategoryTranslation(id=uuid.uuid4(), language=LanguageEnum.ar, name="قهوة", description=""),
        CategoryTranslation(id=uuid.uuid4(), language=LanguageEnum.en, name="Coffee", description="")
    ]
    mock_crud_category_public.get_active_categories.return_value = [cat]
    
    response = client.get("/api/v1/public/categories/", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "Coffee" # Respects Accept-Language

def test_public_categories_fallback_ar(mock_crud_category_public):
    cat_id = uuid.uuid4()
    cat = Category(id=cat_id, is_active=True, sort_order=0)
    # Only Arabic translation available
    cat.translations = [
        CategoryTranslation(id=uuid.uuid4(), language=LanguageEnum.ar, name="قهوة", description="")
    ]
    mock_crud_category_public.get_active_categories.return_value = [cat]
    
    response = client.get("/api/v1/public/categories/", headers={"Accept-Language": "en"})
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "قهوة" # Falls back to Arabic

def test_public_products_active_only(mock_crud_product_public):
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    
    prod = Product(id=prod_id, category_id=cat_id, is_active=True)
    prod.translations = [
        ProductTranslation(id=uuid.uuid4(), language=LanguageEnum.ar, name="قهوة برازيلي", description="وصف")
    ]
    # One active variant, one inactive variant
    v1 = ProductVariant(id=uuid.uuid4(), weight_grams=250, grind_type=GrindTypeEnum.ESPRESSO, price=200, stock_quantity=10, is_active=True)
    v2 = ProductVariant(id=uuid.uuid4(), weight_grams=500, grind_type=GrindTypeEnum.TURKISH, price=400, stock_quantity=5, is_active=False)
    prod.variants = [v1, v2]
    
    mock_crud_product_public.get_active_products.return_value = [prod]
    
    response = client.get("/api/v1/public/products/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "قهوة برازيلي"
    assert len(data[0]["variants"]) == 1 # Inactive variant is filtered out
    assert data[0]["variants"][0]["weight_grams"] == 250
