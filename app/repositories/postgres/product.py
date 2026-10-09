from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EntityNotFoundError
from app.models.postgres import CategoryModel, ProductModel
from app.repositories.base import ProductRepository
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)


class PostgresProductRepository(ProductRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, product_id: str) -> ProductResponse | None:
        stmt = (
            select(ProductModel, CategoryModel.name.label("category_name"))
            .outerjoin(CategoryModel, ProductModel.category_id == CategoryModel.id)
            .where(ProductModel.id == product_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        prod, cat_name = row
        return ProductResponse(
            id=prod.id,
            name=prod.name,
            description=prod.description,
            price=prod.price,
            stock=prod.stock,
            category_id=prod.category_id,
            category_name=cat_name,
            created_at=prod.created_at,
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
        filters = []
        if category_id:
            filters.append(ProductModel.category_id == category_id)
        if min_price is not None:
            filters.append(ProductModel.price >= min_price)
        if max_price is not None:
            filters.append(ProductModel.price <= max_price)
        if search:
            # Case-insensitive search on name or description
            pattern = f"%{search}%"
            filters.append(
                or_(
                    ProductModel.name.ilike(pattern),
                    ProductModel.description.ilike(pattern),
                )
            )

        # Count total matching
        count_stmt = select(func.count(ProductModel.id))
        if filters:
            count_stmt = count_stmt.where(*filters)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one() or 0

        # Query page
        stmt = select(ProductModel, CategoryModel.name.label("category_name")).outerjoin(
            CategoryModel, ProductModel.category_id == CategoryModel.id
        )
        if filters:
            stmt = stmt.where(*filters)

        stmt = stmt.order_by(ProductModel.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        rows = result.all()

        products = [
            ProductResponse(
                id=prod.id,
                name=prod.name,
                description=prod.description,
                price=prod.price,
                stock=prod.stock,
                category_id=prod.category_id,
                category_name=cat_name,
                created_at=prod.created_at,
            )
            for prod, cat_name in rows
        ]
        return products, total

    async def create(
        self, product_data: ProductCreate, product_id: str | None = None
    ) -> ProductResponse:
        # Verify category exists
        cat_stmt = select(CategoryModel).where(CategoryModel.id == product_data.category_id)
        cat_result = await self.session.execute(cat_stmt)
        cat = cat_result.scalar_one_or_none()
        if not cat:
            raise EntityNotFoundError("Category", product_data.category_id)

        product = ProductModel(
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            stock=product_data.stock,
            category_id=product_data.category_id,
        )
        if product_id:
            product.id = product_id

        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)

        return ProductResponse(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            stock=product.stock,
            category_id=product.category_id,
            category_name=cat.name,
            created_at=product.created_at,
        )

    async def update(self, product_id: str, product_data: ProductUpdate) -> ProductResponse | None:
        stmt = select(ProductModel).where(ProductModel.id == product_id)
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            return None

        update_dict = product_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(product, key, value)

        await self.session.commit()
        return await self.get_by_id(product_id)

    async def get_categories(self) -> list[CategoryResponse]:
        stmt = select(CategoryModel).order_by(CategoryModel.name.asc())
        result = await self.session.execute(stmt)
        categories = result.scalars().all()
        return [CategoryResponse.model_validate(c) for c in categories]

    async def create_category(
        self, category_data: CategoryCreate, category_id: str | None = None
    ) -> CategoryResponse:
        cat = CategoryModel(name=category_data.name, slug=category_data.slug)
        if category_id:
            cat.id = category_id
        self.session.add(cat)
        await self.session.commit()
        await self.session.refresh(cat)
        return CategoryResponse.model_validate(cat)

    async def count(self) -> int:
        stmt = select(func.count(ProductModel.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
