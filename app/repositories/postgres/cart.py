from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.models.postgres import CartItemModel, CartModel, ProductModel, utc_now
from app.repositories.base import CartRepository
from app.schemas.cart import CartItemResponse, CartResponse


class PostgresCartRepository(CartRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_or_create_cart(self, user_id: str) -> CartModel:
        stmt = select(CartModel).where(CartModel.user_id == user_id)
        result = await self.session.execute(stmt)
        cart = result.scalar_one_or_none()
        if not cart:
            cart = CartModel(user_id=user_id)
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)
        return cart

    async def get_by_user_id(self, user_id: str) -> CartResponse:
        cart = await self._get_or_create_cart(user_id)

        # Fetch cart items joined with products
        stmt = (
            select(CartItemModel, ProductModel)
            .join(ProductModel, CartItemModel.product_id == ProductModel.id)
            .where(CartItemModel.cart_id == cart.id)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        items: list[CartItemResponse] = []
        total_amount = 0.0
        for item, prod in rows:
            subtotal = round(prod.price * item.quantity, 2)
            total_amount += subtotal
            items.append(
                CartItemResponse(
                    product_id=prod.id,
                    name=prod.name,
                    price=prod.price,
                    quantity=item.quantity,
                    subtotal=subtotal,
                )
            )

        return CartResponse(
            id=cart.id,
            user_id=cart.user_id,
            items=items,
            total_amount=round(total_amount, 2),
            updated_at=cart.updated_at,
        )

    async def add_item(self, user_id: str, product_id: str, quantity: int) -> CartResponse:
        cart = await self._get_or_create_cart(user_id)

        # Check product existence
        p_stmt = select(ProductModel).where(ProductModel.id == product_id)
        p_res = await self.session.execute(p_stmt)
        product = p_res.scalar_one_or_none()
        if not product:
            raise EntityNotFoundError("Product", product_id)

        # Check existing item
        stmt = select(CartItemModel).where(
            CartItemModel.cart_id == cart.id, CartItemModel.product_id == product_id
        )
        res = await self.session.execute(stmt)
        cart_item = res.scalar_one_or_none()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.price = product.price
        else:
            cart_item = CartItemModel(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
                price=product.price,
            )
            self.session.add(cart_item)

        cart.updated_at = utc_now()
        await self.session.commit()
        return await self.get_by_user_id(user_id)

    async def update_item_quantity(
        self, user_id: str, product_id: str, quantity: int
    ) -> CartResponse:
        cart = await self._get_or_create_cart(user_id)

        if quantity <= 0:
            return await self.remove_item(user_id, product_id)

        stmt = select(CartItemModel).where(
            CartItemModel.cart_id == cart.id, CartItemModel.product_id == product_id
        )
        res = await self.session.execute(stmt)
        cart_item = res.scalar_one_or_none()

        if not cart_item:
            raise EntityNotFoundError("CartItem", product_id)

        cart_item.quantity = quantity
        cart.updated_at = utc_now()
        await self.session.commit()
        return await self.get_by_user_id(user_id)

    async def remove_item(self, user_id: str, product_id: str) -> CartResponse:
        cart = await self._get_or_create_cart(user_id)
        del_stmt = delete(CartItemModel).where(
            CartItemModel.cart_id == cart.id, CartItemModel.product_id == product_id
        )
        await self.session.execute(del_stmt)
        cart.updated_at = utc_now()
        await self.session.commit()
        return await self.get_by_user_id(user_id)

    async def clear_cart(self, user_id: str) -> None:
        cart = await self._get_or_create_cart(user_id)
        del_stmt = delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
        await self.session.execute(del_stmt)
        cart.updated_at = utc_now()
        await self.session.commit()
