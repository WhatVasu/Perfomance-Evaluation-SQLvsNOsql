from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Mongo vs Postgres E-Commerce Benchmark"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "super-secret-benchmark-key-change-in-production-12345678"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Backend Selection
    DB_BACKEND: Literal["postgres", "mongo"] = "postgres"

    # PostgreSQL Configuration
    POSTGRES_USER: str = "benchmark"
    POSTGRES_PASSWORD: str = "benchmark_secret"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ecommerce_benchmark"
    POSTGRES_POOL_SIZE: int = 50
    POSTGRES_MAX_OVERFLOW: int = 0  # Fixed pool size for strict fairness

    # MongoDB Configuration
    MONGO_USER: str = "benchmark"
    MONGO_PASSWORD: str = "benchmark_secret"
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB: str = "ecommerce_benchmark"
    MONGO_REPLICA_SET: str = "rs0"
    MONGO_POOL_SIZE: int = 50  # Equal pool size to Postgres

    # Transaction / Durability Fair Configuration
    MONGO_WRITE_CONCERN: str = "majority"
    MONGO_JOURNAL: bool = True
    POSTGRES_SYNCHRONOUS_COMMIT: str = "on"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def postgres_async_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_sync_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def mongo_url(self) -> str:
        # If user/password provided and auth enabled:
        auth = ""
        if self.MONGO_USER and self.MONGO_PASSWORD:
            auth = f"{self.MONGO_USER}:{self.MONGO_PASSWORD}@"
        params = []
        if self.MONGO_REPLICA_SET:
            params.append(f"replicaSet={self.MONGO_REPLICA_SET}")
            params.append("directConnection=true")
        query = f"?{'&'.join(params)}" if params else ""
        return f"mongodb://{auth}{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB}{query}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
