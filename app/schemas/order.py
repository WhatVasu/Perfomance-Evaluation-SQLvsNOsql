from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderItemResponse(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    subtotal: float

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: str
    user_id: str
    total_amount: float
    status: str = "completed"
    items: list[OrderItemResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckoutRequest(BaseModel):
    # Optional payment or shipping metadata if needed
    notes: str | None = None
