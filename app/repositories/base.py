from abc import ABC, abstractmethod
from typing import Any

from app.schemas.cart import CartResponse
from app.schemas.order import OrderResponse
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.user import UserCreate, UserResponse


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> UserResponse | None:
        """Fetch user by primary identifier."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch user by email, returning raw record including hashed_password for auth."""
        pass

    @abstractmethod
    async def create(
        self,
        user_data: UserCreate,
        hashed_password: str,
        user_id: str | None = None,
        is_admin: bool = False,
    ) -> UserResponse:
        """Create a new user."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Return total number of users."""
        pass


class ProductRepository(ABC):
    @abstractmethod
    async def get_by_id(self, product_id: str) -> ProductResponse | None:
        """Fetch a single product by ID."""
        pass

    @abstractmethod
    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        search: str | None = None,
    ) -> tuple[list[ProductResponse], int]:
        """List products with pagination, optional category, price filter, and text search."""
        pass

    @abstractmethod
    async def create(
        self, product_data: ProductCreate, product_id: str | None = None
    ) -> ProductResponse:
        """Create a new product."""
        pass

    @abstractmethod
    async def update(self, product_id: str, product_data: ProductUpdate) -> ProductResponse | None:
        """Update an existing product."""
        pass

    @abstractmethod
    async def get_categories(self) -> list[CategoryResponse]:
        """Fetch all product categories."""
        pass

    @abstractmethod
    async def create_category(
        self, category_data: CategoryCreate, category_id: str | None = None
    ) -> CategoryResponse:
        """Create a category."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Return total number of products."""
        pass


class CartRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> CartResponse:
        """Get cart for a user. Creates an empty cart if none exists."""
        pass

    @abstractmethod
    async def add_item(self, user_id: str, product_id: str, quantity: int) -> CartResponse:
        """Add item to cart or increment quantity if already present."""
        pass

    @abstractmethod
    async def update_item_quantity(
        self, user_id: str, product_id: str, quantity: int
    ) -> CartResponse:
        """Update item quantity in cart. If quantity <= 0, item is removed."""
        pass

    @abstractmethod
    async def remove_item(self, user_id: str, product_id: str) -> CartResponse:
        """Remove an item from user cart."""
        pass

    @abstractmethod
    async def clear_cart(self, user_id: str) -> None:
        """Empty all items from user cart."""
        pass


class OrderRepository(ABC):
    @abstractmethod
    async def create_order_atomic(self, user_id: str) -> OrderResponse:
        """
        Execute atomic checkout:
        1. Fetch current cart
        2. Validate stock for all cart items
        3. Decrement stock for all items
        4. Create order and order items
        5. Clear cart
        All inside a single database transaction. Rollback on failure.
        """
        pass

    @abstractmethod
    async def get_by_id(self, order_id: str, user_id: str | None = None) -> OrderResponse | None:
        """Get order by ID, optionally scoped to user."""
        pass

    @abstractmethod
    async def list_by_user_id(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[OrderResponse], int]:
        """List orders for a user with pagination."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Return total number of orders."""
        pass
