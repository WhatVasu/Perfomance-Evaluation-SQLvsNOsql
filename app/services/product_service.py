import math

from fastapi import HTTPException, status

from app.exceptions import EntityNotFoundError
from app.repositories.base import ProductRepository
from app.schemas.common import PaginatedResponse
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo

    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[ProductResponse]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        items, total = await self.product_repo.list_products(
            page=page,
            page_size=page_size,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            search=search,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedResponse[ProductResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_product(self, product_id: str) -> ProductResponse:
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{product_id}' not found.",
            )
        return product

    async def create_product(self, product_data: ProductCreate) -> ProductResponse:
        try:
            return await self.product_repo.create(product_data)
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    async def update_product(self, product_id: str, product_data: ProductUpdate) -> ProductResponse:
        product = await self.product_repo.update(product_id, product_data)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{product_id}' not found.",
            )
        return product

    async def get_categories(self) -> list[CategoryResponse]:
        return await self.product_repo.get_categories()

    async def create_category(self, category_data: CategoryCreate) -> CategoryResponse:
        return await self.product_repo.create_category(category_data)
