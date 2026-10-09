from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EmptyCartError, InsufficientStockError
from app.models.postgres import (
    CartItemModel,
    CartModel,
    OrderItemModel,
    OrderModel,
    ProductModel,
    utc_now,
)
from app.repositories.base import OrderRepository
from app.schemas.order import OrderItemResponse, OrderResponse


class PostgresOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_order_atomic(self, user_id: str) -> OrderResponse:
        """
        Executes an atomic checkout inside a PostgreSQL transaction:
        - Locks product rows with FOR UPDATE (sorted by ID to prevent deadlocks)
        - Verifies sufficient inventory
        - Decrements stock
        - Creates order and order_items
        - Clears user cart
        """
        async with self.session.begin():
            # 1. Fetch user's cart
            cart_stmt = select(CartModel).where(CartModel.user_id == user_id)
            cart_res = await self.session.execute(cart_stmt)
            cart = cart_res.scalar_one_or_none()
            if not cart:
                raise EmptyCartError()

            # 2. Fetch cart items
            items_stmt = select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            items_res = await self.session.execute(items_stmt)
            cart_items = items_res.scalars().all()
            if not cart_items:
                raise EmptyCartError()

            # 3. Lock product rows in deterministic order to prevent deadlocks
            product_ids = sorted({item.product_id for item in cart_items})
            lock_stmt = (
                select(ProductModel).where(ProductModel.id.in_(product_ids)).with_for_update()
            )
            lock_res = await self.session.execute(lock_stmt)
            locked_products = {p.id: p for p in lock_res.scalars().all()}

            # 4. Check stock and compute totals
            total_amount = 0.0
            order_items_to_create: list[dict] = []

            for item in cart_items:
                product = locked_products.get(item.product_id)
                if not product or product.stock < item.quantity:
                    available = product.stock if product else 0
                    p_name = product.name if product else item.product_id
                    raise InsufficientStockError(
                        product_id=item.product_id,
                        product_name=p_name,
                        available=available,
                        requested=item.quantity,
                    )

                # Decrement stock
                product.stock -= item.quantity
                subtotal = round(product.price * item.quantity, 2)
                total_amount += subtotal

                order_items_to_create.append(
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "quantity": item.quantity,
                        "subtotal": subtotal,
                    }
                )

            # 5. Create Order
            order = OrderModel(
                user_id=user_id,
                total_amount=round(total_amount, 2),
                status="completed",
                created_at=utc_now(),
            )
            self.session.add(order)
            await self.session.flush()

            # 6. Create OrderItems
            for item_dict in order_items_to_create:
                order_item = OrderItemModel(
                    order_id=order.id,
                    product_id=item_dict["product_id"],
                    name=item_dict["name"],
                    price=item_dict["price"],
                    quantity=item_dict["quantity"],
                    subtotal=item_dict["subtotal"],
                )
                self.session.add(order_item)

            # 7. Clear cart items
            del_stmt = delete(CartItemModel).where(CartItemModel.cart_id == cart.id)
            await self.session.execute(del_stmt)
            cart.updated_at = utc_now()

        # Reload order with items after commit
        order_res = await self.get_by_id(order.id, user_id)
        assert order_res is not None
        return order_res

    async def get_by_id(self, order_id: str, user_id: str | None = None) -> OrderResponse | None:
        stmt = select(OrderModel).where(OrderModel.id == order_id)
        if user_id:
            stmt = stmt.where(OrderModel.user_id == user_id)
        result = await self.session.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            return None

        # Fetch items
        items_stmt = select(OrderItemModel).where(OrderItemModel.order_id == order.id)
        items_res = await self.session.execute(items_stmt)
        items = items_res.scalars().all()

        return OrderResponse(
            id=order.id,
            user_id=order.user_id,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            items=[
                OrderItemResponse(
                    product_id=item.product_id,
                    name=item.name,
                    price=item.price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                )
                for item in items
            ],
        )

    async def list_by_user_id(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[OrderResponse], int]:
        count_stmt = select(func.count(OrderModel.id)).where(OrderModel.user_id == user_id)
        total = (await self.session.execute(count_stmt)).scalar_one() or 0

        stmt = (
            select(OrderModel)
            .where(OrderModel.user_id == user_id)
            .order_by(OrderModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        orders = (await self.session.execute(stmt)).scalars().all()

        order_responses = []
        for o in orders:
            order_resp = await self.get_by_id(o.id, user_id)
            if order_resp:
                order_responses.append(order_resp)

        return order_responses, total

    async def count(self) -> int:
        stmt = select(func.count(OrderModel.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
