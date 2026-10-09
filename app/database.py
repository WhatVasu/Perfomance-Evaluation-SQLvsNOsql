import logging
from collections.abc import AsyncGenerator

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# PostgreSQL async engine & sessionmaker
postgres_engine: AsyncEngine | None = None
postgres_session_maker: async_sessionmaker[AsyncSession] | None = None

# MongoDB client & database
mongo_client: AsyncIOMotorClient | None = None
mongo_database: AsyncIOMotorDatabase | None = None


def get_postgres_engine() -> AsyncEngine:
    global postgres_engine, postgres_session_maker
    if postgres_engine is None:
        postgres_engine = create_async_engine(
            settings.postgres_async_url,
            pool_size=settings.POSTGRES_POOL_SIZE,
            max_overflow=settings.POSTGRES_MAX_OVERFLOW,
            pool_pre_ping=True,
            echo=False,
        )
        postgres_session_maker = async_sessionmaker(
            bind=postgres_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return postgres_engine


def get_postgres_session_maker() -> async_sessionmaker[AsyncSession]:
    if postgres_session_maker is None:
        get_postgres_engine()
    assert postgres_session_maker is not None
    return postgres_session_maker


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    maker = get_postgres_session_maker()
    async with maker() as session:
        yield session


def get_mongo_client() -> AsyncIOMotorClient:
    global mongo_client, mongo_database
    if mongo_client is None:
        mongo_client = AsyncIOMotorClient(
            settings.mongo_url,
            maxPoolSize=settings.MONGO_POOL_SIZE,
            minPoolSize=min(10, settings.MONGO_POOL_SIZE),
            serverSelectionTimeoutMS=5000,
        )
        mongo_database = mongo_client[settings.MONGO_DB]
    return mongo_client


def get_mongo_db() -> AsyncIOMotorDatabase:
    if mongo_database is None:
        get_mongo_client()
    assert mongo_database is not None
    return mongo_database


async def init_postgres_tables(engine: AsyncEngine | None = None) -> None:
    """Create all PostgreSQL tables and indexes."""
    from app.models.postgres import Base

    target_engine = engine or get_postgres_engine()
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables and indexes ensured.")


async def init_mongo_indexes(db: AsyncIOMotorDatabase | None = None) -> None:
    """Create equivalent indexes on MongoDB collections."""
    target_db = db or get_mongo_db()

    # 1. Users: email unique
    await target_db.users.create_index(
        [("email", pymongo.ASCENDING)], unique=True, name="idx_users_email_unique"
    )

    # 2. Products: category_id, price, text index on name
    await target_db.products.create_index(
        [("category_id", pymongo.ASCENDING)], name="idx_products_category_id"
    )
    await target_db.products.create_index([("price", pymongo.ASCENDING)], name="idx_products_price")
    await target_db.products.create_index(
        [("name", pymongo.TEXT), ("description", pymongo.TEXT)], name="idx_products_text_name_desc"
    )

    # 3. Carts: user_id unique
    await target_db.carts.create_index(
        [("user_id", pymongo.ASCENDING)], unique=True, name="idx_carts_user_id_unique"
    )

    # 4. Orders: compound index on (user_id, created_at DESC)
    await target_db.orders.create_index(
        [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        name="idx_orders_user_created",
    )
    logger.info("MongoDB equivalent indexes ensured.")


async def close_connections() -> None:
    global postgres_engine, mongo_client
    if postgres_engine:
        await postgres_engine.dispose()
        postgres_engine = None
    if mongo_client:
        mongo_client.close()
        mongo_client = None
