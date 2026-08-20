"""Add performance, composite, and foreign key indexes

Revision ID: c1f58bca51fc
Revises: 88c41eb496d1
Create Date: 2026-08-20 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f58bca51fc'
down_revision: Union[str, Sequence[str], None] = '88c41eb496d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with performance indexes."""
    # 1. Categories
    op.create_index('ix_categories_is_active', 'categories', ['is_active'], unique=False)
    op.create_index('ix_categories_is_active_sort_order', 'categories', ['is_active', 'sort_order'], unique=False)

    # 2. Category Translations
    op.create_index('ix_category_translations_category_id', 'category_translations', ['category_id'], unique=False)

    # 3. Products
    op.create_index('ix_products_category_id', 'products', ['category_id'], unique=False)
    op.create_index('ix_products_is_active', 'products', ['is_active'], unique=False)
    op.create_index('ix_products_category_id_is_active', 'products', ['category_id', 'is_active'], unique=False)
    op.create_index('ix_products_created_at_desc', 'products', [sa.text('created_at DESC')], unique=False)

    # 4. Product Translations
    op.create_index('ix_product_translations_product_id', 'product_translations', ['product_id'], unique=False)

    # 5. Product Variants
    op.create_index('ix_product_variants_product_id', 'product_variants', ['product_id'], unique=False)
    op.create_index('ix_product_variants_product_id_is_active', 'product_variants', ['product_id', 'is_active'], unique=False)

    # 6. Orders
    op.create_index('ix_orders_order_status_created_at_desc', 'orders', ['order_status', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_orders_payment_status_created_at_desc', 'orders', ['payment_status', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_orders_customer_phone_created_at_desc', 'orders', ['customer_phone', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_orders_created_at_desc', 'orders', [sa.text('created_at DESC')], unique=False)

    # 7. Order Items
    op.create_index('ix_order_items_product_variant_id', 'order_items', ['product_variant_id'], unique=False)

    # 8. Cart Items
    op.create_index('ix_cart_items_product_variant_id', 'cart_items', ['product_variant_id'], unique=False)

    # 9. Admin Challenges
    op.create_index('ix_admin_auth_challenges_lookup', 'admin_auth_challenges', ['admin_user_id', 'consumed_at', 'expires_at'], unique=False)
    op.create_index('ix_admin_phone_change_challenges_lookup', 'admin_phone_change_challenges', ['admin_user_id', 'consumed_at', 'expires_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_admin_phone_change_challenges_lookup', table_name='admin_phone_change_challenges')
    op.drop_index('ix_admin_auth_challenges_lookup', table_name='admin_auth_challenges')
    op.drop_index('ix_cart_items_product_variant_id', table_name='cart_items')
    op.drop_index('ix_order_items_product_variant_id', table_name='order_items')
    op.drop_index('ix_orders_created_at_desc', table_name='orders')
    op.drop_index('ix_orders_customer_phone_created_at_desc', table_name='orders')
    op.drop_index('ix_orders_payment_status_created_at_desc', table_name='orders')
    op.drop_index('ix_orders_order_status_created_at_desc', table_name='orders')
    op.drop_index('ix_product_variants_product_id_is_active', table_name='product_variants')
    op.drop_index('ix_product_variants_product_id', table_name='product_variants')
    op.drop_index('ix_product_translations_product_id', table_name='product_translations')
    op.drop_index('ix_products_created_at_desc', table_name='products')
    op.drop_index('ix_products_category_id_is_active', table_name='products')
    op.drop_index('ix_products_is_active', table_name='products')
    op.drop_index('ix_products_category_id', table_name='products')
    op.drop_index('ix_category_translations_category_id', table_name='category_translations')
    op.drop_index('ix_categories_is_active_sort_order', table_name='categories')
    op.drop_index('ix_categories_is_active', table_name='categories')
