import uuid
from sqlalchemy import Column, String, Boolean, Integer, Numeric, Text, ForeignKey, Enum, DateTime, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class LanguageEnum(str, enum.Enum):
    ar = "ar"
    en = "en"

class GrindTypeEnum(str, enum.Enum):
    WHOLE_BEAN = "WHOLE_BEAN"
    TURKISH = "TURKISH"
    ESPRESSO = "ESPRESSO"
    FILTER = "FILTER"
    FRENCH_PRESS = "FRENCH_PRESS"
    MOKA_POT = "MOKA_POT"
    AEROPRESS = "AEROPRESS"

class Category(Base):
    __tablename__ = "categories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    is_active = Column(Boolean, default=True, index=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    translations = relationship("CategoryTranslation", back_populates="category", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        Index("ix_categories_is_active_sort_order", "is_active", "sort_order"),
    )

class CategoryTranslation(Base):
    __tablename__ = "category_translations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(Enum(LanguageEnum), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    category = relationship("Category", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("category_id", "language", name="uq_category_translation_lang"),
    )

class Product(Base):
    __tablename__ = "products"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    category = relationship("Category", back_populates="products")
    translations = relationship("ProductTranslation", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_products_category_id_is_active", "category_id", "is_active"),
        Index("ix_products_created_at_desc", created_at.desc()),
    )

class ProductTranslation(Base):
    __tablename__ = "product_translations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(Enum(LanguageEnum), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    product = relationship("Product", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("product_id", "language", name="uq_product_translation_lang"),
    )

class ProductVariant(Base):
    __tablename__ = "product_variants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    weight_grams = Column(Integer, nullable=False)
    grind_type = Column(Enum(GrindTypeEnum), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    product = relationship("Product", back_populates="variants")

    __table_args__ = (
        UniqueConstraint("product_id", "weight_grams", "grind_type", name="uq_product_variant"),
        Index("ix_product_variants_product_id_is_active", "product_id", "is_active"),
        CheckConstraint("weight_grams > 0", name="chk_weight_grams_positive"),
        CheckConstraint("price >= 0", name="chk_price_non_negative"),
        CheckConstraint("stock_quantity >= 0", name="chk_stock_quantity_non_negative"),
    )
