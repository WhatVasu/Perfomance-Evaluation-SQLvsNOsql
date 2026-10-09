from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str
    slug: str


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    description: str = ""
    price: float = Field(gt=0, description="Price must be strictly positive")
    stock: int = Field(ge=0, description="Stock must be non-negative")
    category_id: str


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    category_id: str | None = None


class ProductResponse(ProductBase):
    id: str
    category_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
