import math

from fastapi import HTTPException, status

from app.exceptions import ConcurrencyConflictError, EmptyCartError, InsufficientStockError
from app.repositories.base import OrderRepository
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderResponse


class OrderService:
    def __init__(self, order_repo: OrderRepository):
        self.order_repo = order_repo

    async def checkout(self, user_id: str) -> OrderResponse:
        try:
            return await self.order_repo.create_order_atomic(user_id)
        except EmptyCartError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except InsufficientStockError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "INSUFFICIENT_STOCK",
                    "message": str(e),
                    "product_id": e.product_id,
                    "available": e.available,
                    "requested": e.requested,
                },
            )
        except ConcurrencyConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    async def get_order(self, order_id: str, user_id: str | None = None) -> OrderResponse:
        order = await self.order_repo.get_by_id(order_id, user_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order '{order_id}' not found.",
            )
        return order

    async def list_orders(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[OrderResponse]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        items, total = await self.order_repo.list_by_user_id(
            user_id, page=page, page_size=page_size
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedResponse[OrderResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
