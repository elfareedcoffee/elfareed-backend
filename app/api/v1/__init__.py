from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.storefront.categories import router as public_categories_router
from app.api.v1.storefront.products import router as public_products_router
from app.api.v1.storefront.cart import router as public_cart_router
from app.api.v1.storefront.orders import router as public_orders_router
from app.api.v1.storefront.store import router as public_store_router
from app.api.v1.admin.categories import router as admin_categories_router
from app.api.v1.admin.products import router as admin_products_router
from app.api.v1.admin.variants import router as admin_variants_router
from app.api.v1.admin.orders import router as admin_orders_router
from app.api.v1.admin.dashboard import router as admin_dashboard_router
from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.cron import router as cron_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(public_categories_router, prefix="/public/categories", tags=["Public Categories"])
api_router.include_router(public_products_router, prefix="/public/products", tags=["Public Products"])
api_router.include_router(public_cart_router, prefix="/public/cart", tags=["Public Cart"])
api_router.include_router(public_orders_router, prefix="/public/orders", tags=["Public Orders"])
api_router.include_router(public_store_router, prefix="/public/store", tags=["Public Store"])

api_router.include_router(admin_auth_router, prefix="/admin/auth", tags=["Admin Auth"])
api_router.include_router(admin_categories_router, prefix="/admin/categories", tags=["Admin Categories"])
api_router.include_router(admin_products_router, prefix="/admin/products", tags=["Admin Products"])
api_router.include_router(admin_variants_router, prefix="/admin/variants", tags=["Admin Variants"])
api_router.include_router(admin_orders_router, prefix="/admin/orders", tags=["Admin Orders"])
api_router.include_router(admin_dashboard_router, prefix="/admin/dashboard", tags=["Admin Dashboard"])
api_router.include_router(cron_router, prefix="/cron", tags=["Cron Tasks"])
