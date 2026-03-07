from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from easy_ecom.api.routers.auth import router as auth_router
from easy_ecom.api.routers.dashboard import router as dashboard_router
from easy_ecom.api.routers.inventory import router as inventory_router
from easy_ecom.api.routers.products import router as products_router
from easy_ecom.api.routers.sales import router as sales_router


def create_app() -> FastAPI:
    app = FastAPI(title="EasyEcom API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(products_router)
    app.include_router(inventory_router)
    app.include_router(sales_router)
    return app


app = create_app()
