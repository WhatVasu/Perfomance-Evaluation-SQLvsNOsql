from fastapi import APIRouter, Depends, Request, status

from app.dependencies import get_user_service
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await user_service.register(user_data)


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> Token:
    """
    Accepts both standard JSON {email, password} and form-urlencoded
    (OAuth2PasswordRequestForm username/password) for Swagger UI support.
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        login_data = UserLogin(email=body.get("email"), password=body.get("password"))
    else:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
        login_data = UserLogin(email=str(email), password=str(password))

    return await user_service.authenticate(login_data)
