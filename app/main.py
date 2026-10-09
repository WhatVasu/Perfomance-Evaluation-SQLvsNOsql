import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.database import (
    close_connections,
    init_mongo_indexes,
    init_postgres_tables,
)
from app.routers import (
    auth_router,
    cart_router,
    orders_router,
    products_router,
    users_router,
    views_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up application with DB_BACKEND='%s'", settings.DB_BACKEND)
    try:
        if settings.DB_BACKEND == "postgres":
            await init_postgres_tables()
        elif settings.DB_BACKEND == "mongo":
            await init_mongo_indexes()
    except Exception as e:
        logger.warning("Could not initialize database on startup (will retry on connection): %s", e)

    yield

    logger.info("Shutting down application, closing database connections...")
    await close_connections()


app = FastAPI(
    title=settings.APP_NAME,
    description="Identical E-Commerce API for benchmarking PostgreSQL and MongoDB backends",
    version="0.1.0",
    lifespan=lifespan,
)

# API Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(products_router, prefix=settings.API_V1_PREFIX)
app.include_router(cart_router, prefix=settings.API_V1_PREFIX)
app.include_router(orders_router, prefix=settings.API_V1_PREFIX)

# UI Router
app.include_router(views_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "backend": settings.DB_BACKEND,
        "app_name": settings.APP_NAME,
    }


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/ui/products")
