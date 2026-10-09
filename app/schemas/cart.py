from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartItemBase(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, description="Quantity must be at least 1")


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=0, description="Quantity to set; 0 removes the item")


class CartItemResponse(BaseModel):
    product_id: str
    name: str
    price: float
    quantity: int
    subtotal: float

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    id: str
    user_id: str
    items: list[CartItemResponse] = []
    total_amount: float = 0.0
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
