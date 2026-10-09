from fastapi import HTTPException, status

from app.exceptions import UserAlreadyExistsError
from app.repositories.base import UserRepository
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.auth import create_access_token, hash_password, verify_password


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, user_data: UserCreate, is_admin: bool = False) -> UserResponse:
        hashed = hash_password(user_data.password)
        try:
            return await self.user_repo.create(
                user_data=user_data,
                hashed_password=hashed,
                is_admin=is_admin,
            )
        except UserAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{user_data.email}' already exists.",
            )

    async def authenticate(self, login_data: UserLogin) -> Token:
        user_record = await self.user_repo.get_by_email(login_data.email)
        if not user_record or not verify_password(
            login_data.password, user_record["hashed_password"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user_record.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user account",
            )

        token = create_access_token(
            subject=user_record["id"],
            claims={"email": user_record["email"], "is_admin": user_record.get("is_admin", False)},
        )
        return Token(access_token=token, token_type="bearer")

    async def get_profile(self, user_id: str) -> UserResponse:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
