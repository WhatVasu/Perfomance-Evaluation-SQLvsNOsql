import uuid
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.exceptions import UserAlreadyExistsError
from app.repositories.base import UserRepository
from app.schemas.user import UserCreate, UserResponse


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoUserRepository(UserRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users

    async def get_by_id(self, user_id: str) -> UserResponse | None:
        doc = await self.collection.find_one({"_id": user_id})
        if not doc:
            return None
        return UserResponse(
            id=doc["_id"],
            email=doc["email"],
            full_name=doc["full_name"],
            is_active=doc.get("is_active", True),
            is_admin=doc.get("is_admin", False),
            created_at=doc["created_at"],
        )

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"email": email})
        if not doc:
            return None
        return {
            "id": doc["_id"],
            "email": doc["email"],
            "hashed_password": doc["hashed_password"],
            "full_name": doc["full_name"],
            "is_active": doc.get("is_active", True),
            "is_admin": doc.get("is_admin", False),
            "created_at": doc["created_at"],
        }

    async def create(
        self,
        user_data: UserCreate,
        hashed_password: str,
        user_id: str | None = None,
        is_admin: bool = False,
    ) -> UserResponse:
        uid = user_id or str(uuid.uuid4())
        now = utc_now()
        doc = {
            "_id": uid,
            "email": user_data.email,
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "is_active": True,
            "is_admin": is_admin,
            "created_at": now,
        }
        try:
            await self.collection.insert_one(doc)
        except DuplicateKeyError:
            raise UserAlreadyExistsError(user_data.email)

        return UserResponse(
            id=uid,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=True,
            is_admin=is_admin,
            created_at=now,
        )

    async def count(self) -> int:
        return await self.collection.count_documents({})
