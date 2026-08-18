import sys
import uuid
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db.models.product import Category, CategoryTranslation, Product, ProductTranslation, ProductVariant, LanguageEnum, GrindTypeEnum

def seed_products():
    print("🌱 Seeding products from design...")
    db = SessionLocal()
    
    try:
        # Check if products already exist
        if db.query(Product).count() > 0:
            print("⚠️ Products already exist in the database. Clearing them...")
            db.query(Product).delete()
            db.query(Category).delete()
            db.commit()

        # Create Category "قهوة"
        cat = Category(id=uuid.uuid4(), is_active=True, sort_order=1)
        db.add(cat)
        
        cat_ar = CategoryTranslation(category_id=cat.id, language=LanguageEnum.ar, name="القهوة المختصة", description="تشكيلة من أفضل أنواع البن المحمص")
        cat_en = CategoryTranslation(category_id=cat.id, language=LanguageEnum.en, name="Specialty Coffee", description="Premium roasted coffee selection")
        db.add_all([cat_ar, cat_en])

        # Define products
        items = [
            {
                "name_ar": "غامق",
                "desc_ar": "التحميص الغامق. مرارة نبيلة وطعم كاكاو داكن - الفنجان اللي يفوق النايم.",
                "price_250": "140.00"
            },
            {
                "name_ar": "فاتح",
                "desc_ar": "تحميص فاتح يحافظ على أصل الحبة: حموضة مشرقة ونهاية نظيفة. للي بيحب يتذوق التفاصيل.",
                "price_250": "150.00"
            },
            {
                "name_ar": "وسط",
                "desc_ar": "التحميص المتوازن. حلاوة كراميل هادية وجسم مليان، يناسب الكنكة والفلتر على السواء.",
                "price_250": "135.00"
            },
            {
                "name_ar": "محوج",
                "desc_ar": "خلطة البيت، بن مطحون مع الهيل الأخضر ولمسة قرنفل - القهوة اللي ريحتها توصل قبلها.",
                "price_250": "145.00"
            }
        ]

        for item in items:
            p = Product(id=uuid.uuid4(), category_id=cat.id, is_active=True)
            db.add(p)
            
            t_ar = ProductTranslation(product_id=p.id, language=LanguageEnum.ar, name=item["name_ar"], description=item["desc_ar"])
            t_en = ProductTranslation(product_id=p.id, language=LanguageEnum.en, name=item["name_ar"], description="English description")
            db.add_all([t_ar, t_en])
            
            # Add variants: 250g, 500g, 1000g
            base_price = Decimal(item["price_250"])
            
            v250 = ProductVariant(product_id=p.id, weight_grams=250, grind_type=GrindTypeEnum.ESPRESSO, price=base_price, stock_quantity=100)
            v500 = ProductVariant(product_id=p.id, weight_grams=500, grind_type=GrindTypeEnum.ESPRESSO, price=base_price * 2 - Decimal("5.00"), stock_quantity=100)
            v1000 = ProductVariant(product_id=p.id, weight_grams=1000, grind_type=GrindTypeEnum.ESPRESSO, price=base_price * 4 - Decimal("15.00"), stock_quantity=100)
            
            db.add_all([v250, v500, v1000])

        db.commit()
        print("✅ Products seeded successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding products: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_products()
