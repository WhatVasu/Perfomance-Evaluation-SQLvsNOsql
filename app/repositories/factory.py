from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.repositories.base import (
    CartRepository,
    OrderRepository,
    ProductRepository,
    UserRepository,
)
from app.repositories.mongo import (
    MongoCartRepository,
    MongoOrderRepository,
    MongoProductRepository,
    MongoUserRepository,
)
from app.repositories.postgres import (
    PostgresCartRepository,
    PostgresOrderRepository,
    PostgresProductRepository,
    PostgresUserRepository,
)


def create_user_repository(db_context: Any = None, backend: str | None = None) -> UserRepository:
    chosen_backend = backend or get_settings().DB_BACKEND
    if chosen_backend == "postgres":
        assert isinstance(db_context, AsyncSession), "PostgreSQL requires an AsyncSession"
        return PostgresUserRepository(db_context)
    elif chosen_backend == "mongo":
        assert isinstance(db_context, AsyncIOMotorDatabase), "MongoDB requires AsyncIOMotorDatabase"
        return MongoUserRepository(db_context)
    raise ValueError(f"Unsupported database backend: '{chosen_backend}'")


def create_product_repository(
    db_context: Any = None, backend: str | None = None
) -> ProductRepository:
    chosen_backend = backend or get_settings().DB_BACKEND
    if chosen_backend == "postgres":
        assert isinstance(db_context, AsyncSession), "PostgreSQL requires an AsyncSession"
        return PostgresProductRepository(db_context)
    elif chosen_backend == "mongo":
        assert isinstance(db_context, AsyncIOMotorDatabase), "MongoDB requires AsyncIOMotorDatabase"
        return MongoProductRepository(db_context)
    raise ValueError(f"Unsupported database backend: '{chosen_backend}'")


def create_cart_repository(db_context: Any = None, backend: str | None = None) -> CartRepository:
    chosen_backend = backend or get_settings().DB_BACKEND
    if chosen_backend == "postgres":
        assert isinstance(db_context, AsyncSession), "PostgreSQL requires an AsyncSession"
        return PostgresCartRepository(db_context)
    elif chosen_backend == "mongo":
        assert isinstance(db_context, AsyncIOMotorDatabase), "MongoDB requires AsyncIOMotorDatabase"
        return MongoCartRepository(db_context)
    raise ValueError(f"Unsupported database backend: '{chosen_backend}'")


def create_order_repository(db_context: Any = None, backend: str | None = None) -> OrderRepository:
    chosen_backend = backend or get_settings().DB_BACKEND
    if chosen_backend == "postgres":
        assert isinstance(db_context, AsyncSession), "PostgreSQL requires an AsyncSession"
        return PostgresOrderRepository(db_context)
    elif chosen_backend == "mongo":
        assert isinstance(db_context, AsyncIOMotorDatabase), "MongoDB requires AsyncIOMotorDatabase"
        return MongoOrderRepository(db_context)
    raise ValueError(f"Unsupported database backend: '{chosen_backend}'")
