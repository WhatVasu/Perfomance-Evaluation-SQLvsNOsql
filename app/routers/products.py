from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_admin, get_product_service
from app.schemas.common import PaginatedResponse
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.user import UserResponse
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    category_id: str | None = Query(default=None, description="Filter by category ID"),
    min_price: float | None = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: float | None = Query(default=None, ge=0, description="Maximum price filter"),
    search: str | None = Query(
        default=None, description="Text search on product name or description"
    ),
    product_service: ProductService = Depends(get_product_service),
) -> PaginatedResponse[ProductResponse]:
    return await product_service.list_products(
        page=page,
        page_size=page_size,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )


@router.get("/categories", response_model=list[CategoryResponse])
async def get_categories(
    product_service: ProductService = Depends(get_product_service),
) -> list[CategoryResponse]:
    return await product_service.get_categories()


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    product_service: ProductService = Depends(get_product_service),
    _admin: UserResponse = Depends(get_current_admin),
) -> CategoryResponse:
    return await product_service.create_category(category_data)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    return await product_service.get_product(product_id)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    product_service: ProductService = Depends(get_product_service),
    _admin: UserResponse = Depends(get_current_admin),
) -> ProductResponse:
    return await product_service.create_product(product_data)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_data: ProductUpdate,
    product_service: ProductService = Depends(get_product_service),
    _admin: UserResponse = Depends(get_current_admin),
) -> ProductResponse:
    return await product_service.update_product(product_id, product_data)
