# Database Schema Specifications & Fairness Justification

This document details the data models implemented for PostgreSQL 16 and MongoDB 7 in the comparative research benchmark: **"A Performance Evaluation of MongoDB and PostgreSQL Using an Identical E-Commerce Application"**.

---

## 1. Design Philosophy

The objective is to measure the performance and scalability of PostgreSQL and MongoDB using an identical workload. To ensure methodological validity:
1. **PostgreSQL** uses an **idiomatic normalized relational schema (Third Normal Form / 3NF)** with explicit foreign key constraints, table joins, and transactional multi-table updates.
2. **MongoDB** uses an **idiomatic document schema**, leveraging embedded document arrays where atomic containment is natural (order line items inside orders, active cart items inside carts) while maintaining references for independent entities (users, categories).
3. **The Database is the ONLY variable**: Both systems expose identical REST API contracts, guarantee full ACID durability on writes, use identical connection pool configurations, and possess strictly equivalent indexes.

---

## 2. PostgreSQL Schema (Normalized Relational)

### 2.1 Table Definitions

```sql
-- 1. Users Table
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Categories Table
CREATE TABLE categories (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL
);

-- 3. Products Table
CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price FLOAT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    category_id VARCHAR(36) NOT NULL REFERENCES categories(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Shopping Carts Table
CREATE TABLE carts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Cart Items Table
CREATE TABLE cart_items (
    id VARCHAR(36) PRIMARY KEY,
    cart_id VARCHAR(36) NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id VARCHAR(36) NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    price FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cart_item UNIQUE (cart_id, product_id)
);

-- 6. Orders Table
CREATE TABLE orders (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_amount FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Order Items Table
CREATE TABLE order_items (
    id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id VARCHAR(36) NOT NULL REFERENCES products(id),
    name VARCHAR(255) NOT NULL,
    price FLOAT NOT NULL,
    quantity INTEGER NOT NULL,
    subtotal FLOAT NOT NULL
);
```

### 2.2 PostgreSQL Indexes
- `users`: Unique B-Tree index on `email` (`users_email_key`).
- `categories`: Unique B-Tree index on `slug` (`categories_slug_key`).
- `products`:
  - `idx_products_category_id` on `category_id`
  - `idx_products_price` on `price`
  - `idx_products_name` on `name`
- `carts`: Unique B-Tree index on `user_id`.
- `cart_items`: Foreign key indexes on `cart_id`, `product_id`, and unique composite `(cart_id, product_id)`.
- `orders`:
  - `idx_orders_user_created` composite index on `(user_id, created_at DESC)`

---

## 3. MongoDB Schema (Idiomatic Document Model)

### 3.1 Collection Schemas

#### Collection: `users`
```json
{
  "_id": "UUID-string",
  "email": "user@example.com",
  "hashed_password": "$2b$12$...",
  "full_name": "Jane Doe",
  "is_active": true,
  "is_admin": false,
  "created_at": "2026-10-09T12:00:00Z"
}
```

#### Collection: `categories`
```json
{
  "_id": "UUID-string",
  "name": "Electronics",
  "slug": "electronics"
}
```

#### Collection: `products`
```json
{
  "_id": "UUID-string",
  "name": "Wireless Noise-Canceling Headphones",
  "description": "Premium over-ear headphones with active noise cancellation",
  "price": 199.99,
  "stock": 45,
  "category_id": "UUID-string",
  "category_name": "Electronics",
  "created_at": "2026-10-09T12:00:00Z"
}
```

#### Collection: `carts`
```json
{
  "_id": "UUID-string",
  "user_id": "UUID-string",
  "items": [
    {
      "product_id": "UUID-string",
      "name": "Wireless Noise-Canceling Headphones",
      "price": 199.99,
      "quantity": 2,
      "subtotal": 399.98
    }
  ],
  "updated_at": "2026-10-09T12:05:00Z"
}
```

#### Collection: `orders`
```json
{
  "_id": "UUID-string",
  "user_id": "UUID-string",
  "total_amount": 399.98,
  "status": "completed",
  "items": [
    {
      "product_id": "UUID-string",
      "name": "Wireless Noise-Canceling Headphones",
      "price": 199.99,
      "quantity": 2,
      "subtotal": 399.98
    }
  ],
  "created_at": "2026-10-09T12:06:00Z"
}
```

### 3.2 MongoDB Equivalent Indexes
- `users`: Unique index on `{"email": 1}` (`idx_users_email_unique`)
- `products`:
  - Index on `{"category_id": 1}` (`idx_products_category_id`)
  - Index on `{"price": 1}` (`idx_products_price`)
  - Full-text index on `{"name": "text", "description": "text"}` (`idx_products_text_name_desc`)
- `carts`: Unique index on `{"user_id": 1}` (`idx_carts_user_id_unique`)
- `orders`: Compound index on `{"user_id": 1, "created_at": -1}` (`idx_orders_user_created`)

---

## 4. Architectural Fairness & Parity Matrix

To ensure that neither database is artificially favored or disadvantaged, identical constraints and semantics are strictly enforced:

| Dimension | PostgreSQL 16 | MongoDB 7 | Fairness Guarantee |
| :--- | :--- | :--- | :--- |
| **Driver Model** | Async (`SQLAlchemy 2.0` + `psycopg 3`) | Async (`Motor` 3.6 / PyMongo) | Both execute asynchronously on the FastAPI `asyncio` event loop. |
| **Connection Pool** | Fixed size 50 (`pool_size=50`, `max_overflow=0`) | Fixed size 50 (`maxPoolSize=50`, `minPoolSize=10`) | Identical concurrent socket concurrency limit. |
| **Durability Level** | `synchronous_commit = on` (WAL flushed before returning) | Write Concern `w="majority"`, `j=True` (Journal flushed before returning) | Equal strict durability guarantees on disk. |
| **Transaction Semantics** | ACID transaction with `FOR UPDATE` row locks | Multi-Document ACID transaction (`session.start_transaction`) with replica set `rs0` | Complete atomic isolation during checkout; race conditions prevented. |
| **Data Types & IDs** | Standard UUID string (`VARCHAR(36)`) | Standard UUID string (`_id: String`) | Identical ID representation across synthetic records. |
| **Container Limits** | 2.0 CPUs, 2GB RAM | 2.0 CPUs, 2GB RAM | Identical host compute and memory quotas in Docker Compose. |
| **Stock Underflow Guard** | `product.stock < quantity` check under lock | `$inc: {"stock": -qty}` with `stock: {"$gte": qty}` predicate | Zero inventory drift under high concurrent checkouts. |

---

## 5. Schema Justification

1. **Embedding vs. Referencing in MongoDB**:
   - In e-commerce, order line items are immutable historical records that belong exclusively to their parent order. Querying an order virtually always requires reading its items. In MongoDB, embedding line items avoids costly `$lookup` stages and provides single-document read efficiency.
   - Active carts are ephemeral, bounded documents (rarely exceeding 20-50 distinct items), making an embedded array ideal.
   - Products and categories are separate collections referenced by ID because products are independent, mutable, heavily indexed catalog entities.

2. **Normalization in PostgreSQL**:
   - Relational databases enforce declarative referential integrity via foreign keys (`ON DELETE CASCADE`). Normalizing `cart_items` and `order_items` avoids data duplication and adheres to relational standard practice.
   - Indexes on foreign keys and compound sort keys match the MongoDB index topology to equalize query planning overheads.
