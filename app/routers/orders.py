from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_user, get_order_service
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderResponse
from app.schemas.user import UserResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def checkout(
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """
    Executes atomic checkout:
    Creates order from current cart, verifies stock, decrements inventory,
    and clears cart all inside a single database transaction.
    """
    return await order_service.checkout(current_user.id)


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def list_orders(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> PaginatedResponse[OrderResponse]:
    return await order_service.list_orders(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: UserResponse = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return await order_service.get_order(order_id, user_id=current_user.id)
