from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import UserAlreadyExistsError
from app.models.postgres import UserModel
from app.repositories.base import UserRepository
from app.schemas.user import UserCreate, UserResponse


class PostgresUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> UserResponse | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserResponse.model_validate(user)

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at,
        }

    async def create(
        self,
        user_data: UserCreate,
        hashed_password: str,
        user_id: str | None = None,
        is_admin: bool = False,
    ) -> UserResponse:
        existing = await self.get_by_email(user_data.email)
        if existing:
            raise UserAlreadyExistsError(user_data.email)

        user = UserModel(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_admin=is_admin,
        )
        if user_id:
            user.id = user_id

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return UserResponse.model_validate(user)

    async def count(self) -> int:
        stmt = select(func.count(UserModel.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
