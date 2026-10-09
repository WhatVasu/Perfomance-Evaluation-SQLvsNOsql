import uuid
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.exceptions import EntityNotFoundError
from app.repositories.base import CartRepository
from app.schemas.cart import CartItemResponse, CartResponse


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoCartRepository(CartRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.carts
        self.products_col = db.products

    async def _get_or_create_cart_doc(self, user_id: str) -> dict:
        doc = await self.collection.find_one({"user_id": user_id})
        if not doc:
            now = utc_now()
            doc = {
                "_id": str(uuid.uuid4()),
                "user_id": user_id,
                "items": [],
                "updated_at": now,
            }
            await self.collection.insert_one(doc)
        return doc

    def _doc_to_cart_response(self, doc: dict) -> CartResponse:
        items = []
        total_amount = 0.0
        for item in doc.get("items", []):
            subtotal = round(item["price"] * item["quantity"], 2)
            total_amount += subtotal
            items.append(
                CartItemResponse(
                    product_id=item["product_id"],
                    name=item["name"],
                    price=item["price"],
                    quantity=item["quantity"],
                    subtotal=subtotal,
                )
            )

        return CartResponse(
            id=doc["_id"],
            user_id=doc["user_id"],
            items=items,
            total_amount=round(total_amount, 2),
            updated_at=doc["updated_at"],
        )

    async def get_by_user_id(self, user_id: str) -> CartResponse:
        doc = await self._get_or_create_cart_doc(user_id)
        return self._doc_to_cart_response(doc)

    async def add_item(self, user_id: str, product_id: str, quantity: int) -> CartResponse:
        product = await self.products_col.find_one({"_id": product_id})
        if not product:
            raise EntityNotFoundError("Product", product_id)

        doc = await self._get_or_create_cart_doc(user_id)
        items: list[dict] = doc.get("items", [])

        # Check if item exists
        found = False
        for item in items:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                item["price"] = product["price"]
                item["subtotal"] = round(item["price"] * item["quantity"], 2)
                found = True
                break

        if not found:
            subtotal = round(product["price"] * quantity, 2)
            items.append(
                {
                    "product_id": product_id,
                    "name": product["name"],
                    "price": product["price"],
                    "quantity": quantity,
                    "subtotal": subtotal,
                }
            )

        now = utc_now()
        await self.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"items": items, "updated_at": now}},
        )
        doc["items"] = items
        doc["updated_at"] = now
        return self._doc_to_cart_response(doc)

    async def update_item_quantity(
        self, user_id: str, product_id: str, quantity: int
    ) -> CartResponse:
        if quantity <= 0:
            return await self.remove_item(user_id, product_id)

        doc = await self._get_or_create_cart_doc(user_id)
        items: list[dict] = doc.get("items", [])

        found = False
        for item in items:
            if item["product_id"] == product_id:
                item["quantity"] = quantity
                item["subtotal"] = round(item["price"] * quantity, 2)
                found = True
                break

        if not found:
            raise EntityNotFoundError("CartItem", product_id)

        now = utc_now()
        await self.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"items": items, "updated_at": now}},
        )
        doc["items"] = items
        doc["updated_at"] = now
        return self._doc_to_cart_response(doc)

    async def remove_item(self, user_id: str, product_id: str) -> CartResponse:
        doc = await self._get_or_create_cart_doc(user_id)
        items = [i for i in doc.get("items", []) if i["product_id"] != product_id]
        now = utc_now()
        await self.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"items": items, "updated_at": now}},
        )
        doc["items"] = items
        doc["updated_at"] = now
        return self._doc_to_cart_response(doc)

    async def clear_cart(self, user_id: str) -> None:
        now = utc_now()
        await self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"items": [], "updated_at": now}},
        )
