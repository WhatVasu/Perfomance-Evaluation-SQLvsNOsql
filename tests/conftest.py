import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import get_settings
from app.database import (
    get_mongo_client,
    get_mongo_db,
    get_postgres_engine,
    init_mongo_indexes,
    init_postgres_tables,
)
from app.main import app

settings = get_settings()


async def is_postgres_ready() -> bool:
    try:
        engine = get_postgres_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def is_mongo_ready() -> bool:
    try:
        client = get_mongo_client()
        await client.admin.command("ping")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def event_loop():
    """Create session event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", params=["postgres", "mongo"])
async def backend(request, monkeypatch) -> AsyncGenerator[str, None]:
    backend_choice = request.param
    monkeypatch.setattr(settings, "DB_BACKEND", backend_choice)

    if backend_choice == "postgres":
        ready = await is_postgres_ready()
        if not ready:
            pytest.skip("PostgreSQL is not reachable on localhost:5432")
        await init_postgres_tables()
        # Truncate tables for clean test slate
        engine = get_postgres_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE order_items, orders, cart_items, carts, products, categories, users CASCADE;"
                )
            )

    elif backend_choice == "mongo":
        ready = await is_mongo_ready()
        if not ready:
            pytest.skip("MongoDB is not reachable on localhost:27017")
        db = get_mongo_db()
        await db.order_items.delete_many({})
        await db.orders.delete_many({})
        await db.cart_items.delete_many({})
        await db.carts.delete_many({})
        await db.products.delete_many({})
        await db.categories.delete_many({})
        await db.users.delete_many({})
        await init_mongo_indexes(db)

    yield backend_choice


@pytest_asyncio.fixture(scope="function")
async def client(backend) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def admin_auth(client: AsyncClient) -> dict[str, str]:
    # Register admin user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@benchmark.test",
            "full_name": "Admin User",
            "password": "AdminPassword123!",
        },
    )
    assert reg_resp.status_code == 201

    # Grant admin privileges directly in DB
    if settings.DB_BACKEND == "postgres":
        engine = get_postgres_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE users SET is_admin = true WHERE email = 'admin@benchmark.test'")
            )
    else:
        db = get_mongo_db()
        await db.users.update_one({"email": "admin@benchmark.test"}, {"$set": {"is_admin": True}})

    # Login to obtain JWT
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@benchmark.test", "password": "AdminPassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def user_auth(client: AsyncClient) -> dict[str, str]:
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@benchmark.test",
            "full_name": "Standard User",
            "password": "UserPassword123!",
        },
    )
    assert reg_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@benchmark.test", "password": "UserPassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
