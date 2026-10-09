from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, HTTPException, status

from app.config import get_settings
from app.database import get_mongo_db, get_postgres_session
from app.repositories.base import (
    CartRepository,
    OrderRepository,
    ProductRepository,
    UserRepository,
)
from app.repositories.factory import (
    create_cart_repository,
    create_order_repository,
    create_product_repository,
    create_user_repository,
)
from app.schemas.user import UserResponse
from app.services.auth import decode_access_token, oauth2_scheme
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.user_service import UserService


async def get_db_context() -> AsyncGenerator[Any, None]:
    settings = get_settings()
    if settings.DB_BACKEND == "postgres":
        async for session in get_postgres_session():
            yield session
    elif settings.DB_BACKEND == "mongo":
        yield get_mongo_db()
    else:
        raise ValueError(f"Unknown DB_BACKEND '{settings.DB_BACKEND}'")


def get_user_repository(
    db: Any = Depends(get_db_context),
) -> UserRepository:
    return create_user_repository(db)


def get_product_repository(
    db: Any = Depends(get_db_context),
) -> ProductRepository:
    return create_product_repository(db)


def get_cart_repository(
    db: Any = Depends(get_db_context),
) -> CartRepository:
    return create_cart_repository(db)


def get_order_repository(
    db: Any = Depends(get_db_context),
) -> OrderRepository:
    return create_order_repository(db)


def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(user_repo)


def get_product_service(
    product_repo: ProductRepository = Depends(get_product_repository),
) -> ProductService:
    return ProductService(product_repo)


def get_cart_service(
    cart_repo: CartRepository = Depends(get_cart_repository),
) -> CartService:
    return CartService(cart_repo)


def get_order_service(
    order_repo: OrderRepository = Depends(get_order_repository),
) -> OrderService:
    return OrderService(order_repo)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    payload = decode_access_token(token)
    if not payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    user = await user_service.get_profile(payload.sub)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return user


async def get_current_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required",
        )
    return current_user
