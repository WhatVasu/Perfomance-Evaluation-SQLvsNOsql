from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.dependencies import (
    get_cart_service,
    get_order_service,
    get_product_service,
    get_user_service,
)
from app.schemas.user import UserCreate
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.user_service import UserService

settings = get_settings()
templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(prefix="/ui", tags=["UI Views"])

DEFAULT_DEMO_EMAIL = "demo@benchmark.local"


async def get_or_create_demo_user(user_service: UserService) -> str:
    user_record = await user_service.user_repo.get_by_email(DEFAULT_DEMO_EMAIL)
    if user_record:
        return user_record["id"]
    new_user = await user_service.register(
        UserCreate(
            email=DEFAULT_DEMO_EMAIL,
            full_name="Demo Benchmark User",
            password="demopassword123",
        )
    )
    return new_user.id


@router.get("/products", response_class=HTMLResponse)
async def view_products(
    request: Request,
    search: str | None = None,
    product_service: ProductService = Depends(get_product_service),
):
    res = await product_service.list_products(page=1, page_size=24, search=search)
    return templates.TemplateResponse(
        request,
        "products.html",
        {
            "products": res.items,
            "total": res.total,
            "search": search,
            "db_backend": settings.DB_BACKEND,
            "title": "Products - E-Commerce Benchmark",
        },
    )


@router.get("/cart", response_class=HTMLResponse)
async def view_cart(
    request: Request,
    cart_service: CartService = Depends(get_cart_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    cart = await cart_service.get_cart(demo_user_id)
    return templates.TemplateResponse(
        request,
        "cart.html",
        {
            "cart": cart,
            "db_backend": settings.DB_BACKEND,
            "title": "Shopping Cart",
        },
    )


@router.post("/cart/add")
async def ui_add_cart(
    product_id: str = Form(...),
    quantity: int = Form(1),
    cart_service: CartService = Depends(get_cart_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    await cart_service.add_item(demo_user_id, product_id, quantity)
    return RedirectResponse(url="/ui/cart", status_code=303)


@router.post("/cart/remove")
async def ui_remove_cart(
    product_id: str = Form(...),
    cart_service: CartService = Depends(get_cart_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    await cart_service.remove_item(demo_user_id, product_id)
    return RedirectResponse(url="/ui/cart", status_code=303)


@router.post("/cart/clear")
async def ui_clear_cart(
    cart_service: CartService = Depends(get_cart_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    await cart_service.clear_cart(demo_user_id)
    return RedirectResponse(url="/ui/cart", status_code=303)


@router.post("/orders/checkout")
async def ui_checkout(
    order_service: OrderService = Depends(get_order_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    await order_service.checkout(demo_user_id)
    return RedirectResponse(url="/ui/orders", status_code=303)


@router.get("/orders", response_class=HTMLResponse)
async def view_orders(
    request: Request,
    order_service: OrderService = Depends(get_order_service),
    user_service: UserService = Depends(get_user_service),
):
    demo_user_id = await get_or_create_demo_user(user_service)
    orders_res = await order_service.list_orders(demo_user_id, page=1, page_size=20)
    return templates.TemplateResponse(
        request,
        "orders.html",
        {
            "orders": orders_res.items,
            "db_backend": settings.DB_BACKEND,
            "title": "Order History",
        },
    )
