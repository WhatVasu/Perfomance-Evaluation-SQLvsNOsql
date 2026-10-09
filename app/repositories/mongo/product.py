import uuid
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.exceptions import EntityNotFoundError
from app.repositories.base import ProductRepository
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class MongoProductRepository(ProductRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.products
        self.categories_col = db.categories

    async def get_by_id(self, product_id: str) -> ProductResponse | None:
        doc = await self.collection.find_one({"_id": product_id})
        if not doc:
            return None
        return ProductResponse(
            id=doc["_id"],
            name=doc["name"],
            description=doc.get("description", ""),
            price=doc["price"],
            stock=doc["stock"],
            category_id=doc["category_id"],
            category_name=doc.get("category_name"),
            created_at=doc["created_at"],
        )

    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        search: str | None = None,
    ) -> tuple[list[ProductResponse], int]:
        query: dict[str, Any] = {}

        if category_id:
            query["category_id"] = category_id

        if min_price is not None or max_price is not None:
            price_query: dict[str, Any] = {}
            if min_price is not None:
                price_query["$gte"] = min_price
            if max_price is not None:
                price_query["$lte"] = max_price
            query["price"] = price_query

        if search:
            # Use text search if text index exists, or regex fallback
            query["$text"] = {"$search": search}

        try:
            total = await self.collection.count_documents(query)
            cursor = (
                self.collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * page_size)
                .limit(page_size)
            )
            docs = await cursor.to_list(length=page_size)
        except Exception:
            # Fallback to regex if text index is not yet built
            if search and "$text" in query:
                del query["$text"]
                query["name"] = {"$regex": search, "$options": "i"}
                total = await self.collection.count_documents(query)
                cursor = (
                    self.collection.find(query)
                    .sort("created_at", -1)
                    .skip((page - 1) * page_size)
                    .limit(page_size)
                )
                docs = await cursor.to_list(length=page_size)
            else:
                raise

        products = [
            ProductResponse(
                id=doc["_id"],
                name=doc["name"],
                description=doc.get("description", ""),
                price=doc["price"],
                stock=doc["stock"],
                category_id=doc["category_id"],
                category_name=doc.get("category_name"),
                created_at=doc["created_at"],
            )
            for doc in docs
        ]
        return products, total

    async def create(
        self, product_data: ProductCreate, product_id: str | None = None
    ) -> ProductResponse:
        # Verify category exists
        cat = await self.categories_col.find_one({"_id": product_data.category_id})
        if not cat:
            raise EntityNotFoundError("Category", product_data.category_id)

        pid = product_id or str(uuid.uuid4())
        now = utc_now()
        doc = {
            "_id": pid,
            "name": product_data.name,
            "description": product_data.description,
            "price": product_data.price,
            "stock": product_data.stock,
            "category_id": product_data.category_id,
            "category_name": cat["name"],
            "created_at": now,
        }
        await self.collection.insert_one(doc)
        return ProductResponse(
            id=pid,
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            stock=product_data.stock,
            category_id=product_data.category_id,
            category_name=cat["name"],
            created_at=now,
        )

    async def update(self, product_id: str, product_data: ProductUpdate) -> ProductResponse | None:
        update_fields = product_data.model_dump(exclude_unset=True)
        if not update_fields:
            return await self.get_by_id(product_id)

        if "category_id" in update_fields:
            cat = await self.categories_col.find_one({"_id": update_fields["category_id"]})
            if cat:
                update_fields["category_name"] = cat["name"]

        res = await self.collection.update_one({"_id": product_id}, {"$set": update_fields})
        if res.matched_count == 0:
            return None
        return await self.get_by_id(product_id)

    async def get_categories(self) -> list[CategoryResponse]:
        cursor = self.categories_col.find({}).sort("name", 1)
        docs = await cursor.to_list(length=1000)
        return [CategoryResponse(id=doc["_id"], name=doc["name"], slug=doc["slug"]) for doc in docs]

    async def create_category(
        self, category_data: CategoryCreate, category_id: str | None = None
    ) -> CategoryResponse:
        cid = category_id or str(uuid.uuid4())
        doc = {"_id": cid, "name": category_data.name, "slug": category_data.slug}
        await self.categories_col.insert_one(doc)
        return CategoryResponse(id=cid, name=category_data.name, slug=category_data.slug)

    async def count(self) -> int:
        return await self.collection.count_documents({})
