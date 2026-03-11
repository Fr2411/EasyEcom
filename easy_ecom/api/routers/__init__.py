from fastapi import APIRouter

from easy_ecom.api.routers.auth import router as auth_router
from easy_ecom.api.routers.admin import router as admin_router
from easy_ecom.api.routers.customers import router as customers_router
from easy_ecom.api.routers.finance import router as finance_router
from easy_ecom.api.routers.dashboard import router as dashboard_router
from easy_ecom.api.routers.health import router as health_router
from easy_ecom.api.routers.inventory import router as inventory_router
from easy_ecom.api.routers.products import router as products_router
from easy_ecom.api.routers.products_stock import router as products_stock_router
from easy_ecom.api.routers.sales import router as sales_router
from easy_ecom.api.routers.returns import router as returns_router
from easy_ecom.api.routers.session import router as session_router
from easy_ecom.api.routers.settings import router as settings_router
from easy_ecom.api.routers.purchases import router as purchases_router
from easy_ecom.api.routers.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(session_router)
api_router.include_router(admin_router)

# Canonical protected business API surface.
api_router.include_router(dashboard_router)
api_router.include_router(products_router)
api_router.include_router(products_stock_router)
api_router.include_router(inventory_router)
api_router.include_router(sales_router)
api_router.include_router(customers_router)
api_router.include_router(finance_router)
api_router.include_router(returns_router)
api_router.include_router(purchases_router)
api_router.include_router(reports_router)

api_router.include_router(settings_router)
