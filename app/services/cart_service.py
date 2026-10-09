from fastapi import HTTPException, status

from app.exceptions import EntityNotFoundError
from app.repositories.base import CartRepository
from app.schemas.cart import CartResponse


class CartService:
    def __init__(self, cart_repo: CartRepository):
        self.cart_repo = cart_repo

    async def get_cart(self, user_id: str) -> CartResponse:
        return await self.cart_repo.get_by_user_id(user_id)

    async def add_item(self, user_id: str, product_id: str, quantity: int) -> CartResponse:
        try:
            return await self.cart_repo.add_item(user_id, product_id, quantity)
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    async def update_quantity(self, user_id: str, product_id: str, quantity: int) -> CartResponse:
        try:
            return await self.cart_repo.update_item_quantity(user_id, product_id, quantity)
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    async def remove_item(self, user_id: str, product_id: str) -> CartResponse:
        return await self.cart_repo.remove_item(user_id, product_id)

    async def clear_cart(self, user_id: str) -> None:
        await self.cart_repo.clear_cart(user_id)
