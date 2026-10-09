import uuid
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from app.exceptions import EmptyCartError, InsufficientStockError
from app.repositories.base import OrderRepository
from app.schemas.order import OrderItemResponse, OrderResponse


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoOrderRepository(OrderRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.orders_col = db.orders
        self.carts_col = db.carts
        self.products_col = db.products

    async def create_order_atomic(self, user_id: str) -> OrderResponse:
        """
        Executes multi-document ACID checkout transaction:
        1. Reads user cart
        2. Validates inventory and atomically decrements product stock ($inc with $gte guard)
        3. Inserts order with embedded items
        4. Clears user cart
        Rollback occurs automatically if any check fails or exception is raised.
        """
        client = self.db.client
        write_concern = WriteConcern(w="majority", j=True)
        read_concern = ReadConcern(level="local")

        async with await client.start_session() as session:
            async with session.start_transaction(
                write_concern=write_concern, read_concern=read_concern
            ):
                # 1. Fetch user cart
                cart = await self.carts_col.find_one({"user_id": user_id}, session=session)
                if not cart or not cart.get("items"):
                    raise EmptyCartError()

                items = cart["items"]
                # Deterministic sorting by product_id prevents cross-transaction deadlocks
                sorted_items = sorted(items, key=lambda x: x["product_id"])

                order_items = []
                total_amount = 0.0

                # 2. Verify and atomically decrement stock for each item
                for item in sorted_items:
                    pid = item["product_id"]
                    qty = item["quantity"]

                    res = await self.products_col.update_one(
                        {"_id": pid, "stock": {"$gte": qty}},
                        {"$inc": {"stock": -qty}},
                        session=session,
                    )

                    if res.modified_count == 0:
                        prod = await self.products_col.find_one({"_id": pid}, session=session)
                        available = prod.get("stock", 0) if prod else 0
                        name = prod.get("name", pid) if prod else pid
                        raise InsufficientStockError(
                            product_id=pid,
                            product_name=name,
                            available=available,
                            requested=qty,
                        )

                    subtotal = round(item["price"] * qty, 2)
                    total_amount += subtotal
                    order_items.append(
                        {
                            "product_id": pid,
                            "name": item["name"],
                            "price": item["price"],
                            "quantity": qty,
                            "subtotal": subtotal,
                        }
                    )

                # 3. Create order document
                order_id = str(uuid.uuid4())
                now = utc_now()
                order_doc = {
                    "_id": order_id,
                    "user_id": user_id,
                    "total_amount": round(total_amount, 2),
                    "status": "completed",
                    "items": order_items,
                    "created_at": now,
                }
                await self.orders_col.insert_one(order_doc, session=session)

                # 4. Clear cart items
                await self.carts_col.update_one(
                    {"user_id": user_id},
                    {"$set": {"items": [], "updated_at": now}},
                    session=session,
                )

        return OrderResponse(
            id=order_doc["_id"],
            user_id=order_doc["user_id"],
            total_amount=order_doc["total_amount"],
            status=order_doc["status"],
            created_at=order_doc["created_at"],
            items=[
                OrderItemResponse(
                    product_id=it["product_id"],
                    name=it["name"],
                    price=it["price"],
                    quantity=it["quantity"],
                    subtotal=it["subtotal"],
                )
                for it in order_items
            ],
        )

    async def get_by_id(self, order_id: str, user_id: str | None = None) -> OrderResponse | None:
        query: dict = {"_id": order_id}
        if user_id:
            query["user_id"] = user_id
        doc = await self.orders_col.find_one(query)
        if not doc:
            return None

        return OrderResponse(
            id=doc["_id"],
            user_id=doc["user_id"],
            total_amount=doc["total_amount"],
            status=doc.get("status", "completed"),
            created_at=doc["created_at"],
            items=[
                OrderItemResponse(
                    product_id=it["product_id"],
                    name=it["name"],
                    price=it["price"],
                    quantity=it["quantity"],
                    subtotal=it["subtotal"],
                )
                for it in doc.get("items", [])
            ],
        )

    async def list_by_user_id(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[OrderResponse], int]:
        query = {"user_id": user_id}
        total = await self.orders_col.count_documents(query)
        cursor = (
            self.orders_col.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)

        orders = [
            OrderResponse(
                id=doc["_id"],
                user_id=doc["user_id"],
                total_amount=doc["total_amount"],
                status=doc.get("status", "completed"),
                created_at=doc["created_at"],
                items=[
                    OrderItemResponse(
                        product_id=it["product_id"],
                        name=it["name"],
                        price=it["price"],
                        quantity=it["quantity"],
                        subtotal=it["subtotal"],
                    )
                    for it in doc.get("items", [])
                ],
            )
            for doc in docs
        ]
        return orders, total

    async def count(self) -> int:
        return await self.orders_col.count_documents({})
