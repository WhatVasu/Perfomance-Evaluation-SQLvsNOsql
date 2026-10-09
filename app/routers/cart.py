from fastapi import APIRouter, Depends, status

from app.dependencies import get_cart_service, get_current_user
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartResponse
from app.schemas.user import UserResponse
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Shopping Cart"])


@router.get("", response_model=CartResponse)
async def get_cart(
    current_user: UserResponse = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.get_cart(current_user.id)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_200_OK)
async def add_cart_item(
    item_data: CartItemCreate,
    current_user: UserResponse = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.add_item(
        user_id=current_user.id,
        product_id=item_data.product_id,
        quantity=item_data.quantity,
    )


@router.put("/items/{product_id}", response_model=CartResponse)
async def update_cart_item(
    product_id: str,
    item_data: CartItemUpdate,
    current_user: UserResponse = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.update_quantity(
        user_id=current_user.id,
        product_id=product_id,
        quantity=item_data.quantity,
    )


@router.delete("/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: str,
    current_user: UserResponse = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> CartResponse:
    return await cart_service.remove_item(
        user_id=current_user.id,
        product_id=product_id,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    current_user: UserResponse = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> None:
    await cart_service.clear_cart(current_user.id)
