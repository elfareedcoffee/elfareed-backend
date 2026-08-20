import uuid
from sqlalchemy import Column, String, Integer, Numeric, Text, ForeignKey, Enum, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class PaymentMethodEnum(str, enum.Enum):
    COD = "COD"
    ONLINE = "ONLINE"

class PaymentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"

class OrderStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String, unique=True, nullable=False, index=True)
    tracking_token = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False, index=True)
    customer_email = Column(String, nullable=True)
    governorate = Column(String, nullable=False)
    city = Column(String, nullable=False)
    delivery_address = Column(Text, nullable=False)
    delivery_notes = Column(Text, nullable=True)
    
    subtotal = Column(Numeric(10, 2), nullable=False)
    delivery_fee = Column(Numeric(10, 2), nullable=False)
    discount = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False)
    
    payment_method = Column(Enum(PaymentMethodEnum), nullable=False)
    payment_status = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.PENDING, index=True)
    order_status = Column(Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PENDING, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_orders_order_status_created_at_desc", "order_status", created_at.desc()),
        Index("ix_orders_payment_status_created_at_desc", "payment_status", created_at.desc()),
        Index("ix_orders_customer_phone_created_at_desc", "customer_phone", created_at.desc()),
        Index("ix_orders_created_at_desc", created_at.desc()),
        CheckConstraint("subtotal >= 0", name="chk_order_subtotal_non_negative"),
        CheckConstraint("delivery_fee >= 0", name="chk_order_delivery_fee_non_negative"),
        CheckConstraint("discount >= 0", name="chk_order_discount_non_negative"),
        CheckConstraint("total >= 0", name="chk_order_total_non_negative"),
    )

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    original_product_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    product_name_ar = Column(String, nullable=False)
    product_name_en = Column(String, nullable=False)
    weight_grams = Column(Integer, nullable=False)
    grind_type = Column(String, nullable=False)
    
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_item_unit_price_non_negative"),
        CheckConstraint("total_price >= 0", name="chk_order_item_total_price_non_negative"),
    )
