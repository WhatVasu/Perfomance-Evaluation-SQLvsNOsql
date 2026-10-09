from app.routers.auth import router as auth_router
from app.routers.cart import router as cart_router
from app.routers.orders import router as orders_router
from app.routers.products import router as products_router
from app.routers.users import router as users_router
from app.routers.views import router as views_router

__all__ = [
    "auth_router",
    "users_router",
    "products_router",
    "cart_router",
    "orders_router",
    "views_router",
]
