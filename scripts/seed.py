import argparse
import json
import logging
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pymongo
from faker import Faker
from psycopg.rows import dict_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")

SCALE_PRESETS = {
    "test": {"users": 100, "products": 50, "orders": 200},
    "small": {"users": 10_000, "products": 5_000, "orders": 50_000},
    "medium": {"users": 100_000, "products": 50_000, "orders": 500_000},
    "large": {"users": 1_000_000, "products": 200_000, "orders": 5_000_000},
}

DEFAULT_CATEGORIES = [
    {"name": "Electronics", "slug": "electronics"},
    {"name": "Computers & Accessories", "slug": "computers"},
    {"name": "Home & Kitchen", "slug": "home-kitchen"},
    {"name": "Clothing & Apparel", "slug": "apparel"},
    {"name": "Footwear", "slug": "footwear"},
    {"name": "Books & Audible", "slug": "books"},
    {"name": "Sports & Outdoors", "slug": "sports-outdoors"},
    {"name": "Beauty & Personal Care", "slug": "beauty"},
    {"name": "Toys & Games", "slug": "toys-games"},
    {"name": "Automotive", "slug": "automotive"},
]

# Standard bcrypt hash for "Password123!" to avoid hashing computation overhead in bulk generation
DETERMINISTIC_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"


def generate_dataset(
    scale_name: str,
    num_users: int,
    num_products: int,
    num_orders: int,
    seed: int,
    data_dir: Path,
) -> None:
    logger.info(
        "Generating synthetic dataset: scale='%s' (users=%d, products=%d, orders=%d, seed=%d)",
        scale_name,
        num_users,
        num_products,
        num_orders,
        seed,
    )
    rng = random.Random(seed)
    fake = Faker()
    Faker.seed(seed)

    data_dir.mkdir(parents=True, exist_ok=True)
    categories_file = data_dir / "categories.json"
    users_file = data_dir / "users.jsonl"
    products_file = data_dir / "products.jsonl"
    orders_file = data_dir / "orders.jsonl"

    # 1. Categories
    categories = []
    for i, cat in enumerate(DEFAULT_CATEGORIES):
        cid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cat_{i}_{seed}"))
        categories.append({"id": cid, "name": cat["name"], "slug": cat["slug"]})

    with open(categories_file, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2)
    logger.info("Generated %d categories -> %s", len(categories), categories_file)

    # 2. Users
    user_ids: list[str] = []
    base_time = datetime.now(UTC) - timedelta(days=90)

    with open(users_file, "w", encoding="utf-8") as f:
        # Pre-seed one admin user
        admin_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"admin_{seed}"))
        admin_record = {
            "id": admin_id,
            "email": "admin@benchmark.local",
            "hashed_password": DETERMINISTIC_HASH,
            "full_name": "Benchmark Administrator",
            "is_active": True,
            "is_admin": True,
            "created_at": base_time.isoformat(),
        }
        f.write(json.dumps(admin_record) + "\n")
        user_ids.append(admin_id)

        for i in range(num_users):
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"user_{i}_{seed}"))
            user_ids.append(uid)
            created_at = base_time + timedelta(seconds=rng.randint(0, 86400 * 90))
            record = {
                "id": uid,
                "email": f"user_{i}@benchmark.local",
                "hashed_password": DETERMINISTIC_HASH,
                "full_name": fake.name(),
                "is_active": True,
                "is_admin": False,
                "created_at": created_at.isoformat(),
            }
            f.write(json.dumps(record) + "\n")
    logger.info("Generated %d users -> %s", len(user_ids), users_file)

    # 3. Products
    products_list: list[dict] = []
    with open(products_file, "w", encoding="utf-8") as f:
        for i in range(num_products):
            pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"prod_{i}_{seed}"))
            cat = categories[i % len(categories)]
            price = round(rng.uniform(4.99, 899.99), 2)
            stock = rng.randint(20, 2000)
            created_at = base_time + timedelta(seconds=rng.randint(0, 86400 * 90))
            prod_record = {
                "id": pid,
                "name": f"{cat['name']} Item #{i + 1} - {fake.word().capitalize()}",
                "description": fake.sentence(nb_words=10),
                "price": price,
                "stock": stock,
                "category_id": cat["id"],
                "category_name": cat["name"],
                "created_at": created_at.isoformat(),
            }
            products_list.append(prod_record)
            f.write(json.dumps(prod_record) + "\n")
    logger.info("Generated %d products -> %s", len(products_list), products_file)

    # 4. Orders
    with open(orders_file, "w", encoding="utf-8") as f:
        for i in range(num_orders):
            oid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"order_{i}_{seed}"))
            uid = rng.choice(user_ids)
            num_items = rng.randint(1, 4)
            order_products = rng.sample(products_list, num_items)
            created_at = base_time + timedelta(seconds=rng.randint(0, 86400 * 90))

            items = []
            total_amount = 0.0
            for p in order_products:
                qty = rng.randint(1, 3)
                subtotal = round(p["price"] * qty, 2)
                total_amount += subtotal
                items.append(
                    {
                        "product_id": p["id"],
                        "name": p["name"],
                        "price": p["price"],
                        "quantity": qty,
                        "subtotal": subtotal,
                    }
                )

            order_record = {
                "id": oid,
                "user_id": uid,
                "total_amount": round(total_amount, 2),
                "status": "completed",
                "created_at": created_at.isoformat(),
                "items": items,
            }
            f.write(json.dumps(order_record) + "\n")
    logger.info("Generated %d orders -> %s", num_orders, orders_file)


def load_postgres(
    data_dir: Path,
    host: str,
    port: int,
    user: str,
    password: str,
    dbname: str,
    batch_size: int = 5000,
):
    logger.info("Connecting to PostgreSQL at %s:%d/%s...", host, port, dbname)
    conn_str = f"host={host} port={port} user={user} password={password} dbname={dbname}"
    with psycopg.connect(conn_str, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # 1. Truncate tables
            logger.info("Truncating PostgreSQL tables...")
            cur.execute(
                "TRUNCATE TABLE order_items, orders, cart_items, carts, products, categories, users CASCADE;"
            )
            conn.commit()

            # 2. Categories
            with open(data_dir / "categories.json", encoding="utf-8") as f:
                categories = json.load(f)
            for cat in categories:
                cur.execute(
                    "INSERT INTO categories (id, name, slug) VALUES (%s, %s, %s)",
                    (cat["id"], cat["name"], cat["slug"]),
                )
            conn.commit()
            logger.info("Loaded %d categories into PostgreSQL", len(categories))

            # 3. Users & Carts
            logger.info("Loading users and carts into PostgreSQL...")
            user_batch = []
            cart_batch = []
            with open(data_dir / "users.jsonl", encoding="utf-8") as f:
                for line in f:
                    u = json.loads(line)
                    user_batch.append(
                        (
                            u["id"],
                            u["email"],
                            u["hashed_password"],
                            u["full_name"],
                            u["is_active"],
                            u["is_admin"],
                            u["created_at"],
                        )
                    )
                    # Also create an initial empty cart for each user
                    cart_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cart_{u['id']}"))
                    cart_batch.append((cart_id, u["id"], u["created_at"], u["created_at"]))

                    if len(user_batch) >= batch_size:
                        cur.executemany(
                            "INSERT INTO users (id, email, hashed_password, full_name, is_active, is_admin, created_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            user_batch,
                        )
                        cur.executemany(
                            "INSERT INTO carts (id, user_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                            cart_batch,
                        )
                        conn.commit()
                        user_batch.clear()
                        cart_batch.clear()

            if user_batch:
                cur.executemany(
                    "INSERT INTO users (id, email, hashed_password, full_name, is_active, is_admin, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    user_batch,
                )
                cur.executemany(
                    "INSERT INTO carts (id, user_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    cart_batch,
                )
                conn.commit()

            # 4. Products
            logger.info("Loading products into PostgreSQL...")
            prod_batch = []
            with open(data_dir / "products.jsonl", encoding="utf-8") as f:
                for line in f:
                    p = json.loads(line)
                    prod_batch.append(
                        (
                            p["id"],
                            p["name"],
                            p["description"],
                            p["price"],
                            p["stock"],
                            p["category_id"],
                            p["created_at"],
                        )
                    )
                    if len(prod_batch) >= batch_size:
                        cur.executemany(
                            "INSERT INTO products (id, name, description, price, stock, category_id, created_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            prod_batch,
                        )
                        conn.commit()
                        prod_batch.clear()
            if prod_batch:
                cur.executemany(
                    "INSERT INTO products (id, name, description, price, stock, category_id, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    prod_batch,
                )
                conn.commit()

            # 5. Orders & Order Items
            logger.info("Loading orders and order_items into PostgreSQL...")
            order_batch = []
            item_batch = []
            with open(data_dir / "orders.jsonl", encoding="utf-8") as f:
                for line in f:
                    o = json.loads(line)
                    order_batch.append(
                        (o["id"], o["user_id"], o["total_amount"], o["status"], o["created_at"])
                    )
                    for it in o["items"]:
                        item_id = str(uuid.uuid4())
                        item_batch.append(
                            (
                                item_id,
                                o["id"],
                                it["product_id"],
                                it["name"],
                                it["price"],
                                it["quantity"],
                                it["subtotal"],
                            )
                        )

                    if len(order_batch) >= batch_size:
                        cur.executemany(
                            "INSERT INTO orders (id, user_id, total_amount, status, created_at) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            order_batch,
                        )
                        cur.executemany(
                            "INSERT INTO order_items (id, order_id, product_id, name, price, quantity, subtotal) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            item_batch,
                        )
                        conn.commit()
                        order_batch.clear()
                        item_batch.clear()

            if order_batch:
                cur.executemany(
                    "INSERT INTO orders (id, user_id, total_amount, status, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    order_batch,
                )
                cur.executemany(
                    "INSERT INTO order_items (id, order_id, product_id, name, price, quantity, subtotal) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    item_batch,
                )
                conn.commit()

    logger.info("Successfully populated PostgreSQL with synthetic benchmark dataset.")


def load_mongo(
    data_dir: Path,
    host: str,
    port: int,
    dbname: str,
    replica_set: str = "rs0",
    batch_size: int = 5000,
):
    logger.info("Connecting to MongoDB at %s:%d/%s...", host, port, dbname)
    uri = f"mongodb://{host}:{port}/?directConnection=true"
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client[dbname]

    # Clean existing collections
    logger.info("Clearing MongoDB collections...")
    for coll_name in ["users", "categories", "products", "carts", "orders"]:
        db[coll_name].delete_many({})

    # 1. Categories
    with open(data_dir / "categories.json", encoding="utf-8") as f:
        categories = json.load(f)
    cat_docs = [{"_id": c["id"], "name": c["name"], "slug": c["slug"]} for c in categories]
    if cat_docs:
        db.categories.insert_many(cat_docs, ordered=False)
    logger.info("Loaded %d categories into MongoDB", len(cat_docs))

    # 2. Users & Carts
    logger.info("Loading users and carts into MongoDB...")
    user_batch = []
    cart_batch = []
    with open(data_dir / "users.jsonl", encoding="utf-8") as f:
        for line in f:
            u = json.loads(line)
            user_batch.append(
                {
                    "_id": u["id"],
                    "email": u["email"],
                    "hashed_password": u["hashed_password"],
                    "full_name": u["full_name"],
                    "is_active": u["is_active"],
                    "is_admin": u["is_admin"],
                    "created_at": datetime.fromisoformat(u["created_at"]),
                }
            )
            cart_batch.append(
                {
                    "_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cart_{u['id']}")),
                    "user_id": u["id"],
                    "items": [],
                    "updated_at": datetime.fromisoformat(u["created_at"]),
                }
            )

            if len(user_batch) >= batch_size:
                db.users.insert_many(user_batch, ordered=False)
                db.carts.insert_many(cart_batch, ordered=False)
                user_batch.clear()
                cart_batch.clear()

    if user_batch:
        db.users.insert_many(user_batch, ordered=False)
        db.carts.insert_many(cart_batch, ordered=False)

    # 3. Products
    logger.info("Loading products into MongoDB...")
    prod_batch = []
    with open(data_dir / "products.jsonl", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            prod_batch.append(
                {
                    "_id": p["id"],
                    "name": p["name"],
                    "description": p["description"],
                    "price": p["price"],
                    "stock": p["stock"],
                    "category_id": p["category_id"],
                    "category_name": p["category_name"],
                    "created_at": datetime.fromisoformat(p["created_at"]),
                }
            )
            if len(prod_batch) >= batch_size:
                db.products.insert_many(prod_batch, ordered=False)
                prod_batch.clear()
    if prod_batch:
        db.products.insert_many(prod_batch, ordered=False)

    # 4. Orders (with embedded items)
    logger.info("Loading orders into MongoDB...")
    order_batch = []
    with open(data_dir / "orders.jsonl", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            order_batch.append(
                {
                    "_id": o["id"],
                    "user_id": o["user_id"],
                    "total_amount": o["total_amount"],
                    "status": o["status"],
                    "items": o["items"],
                    "created_at": datetime.fromisoformat(o["created_at"]),
                }
            )
            if len(order_batch) >= batch_size:
                db.orders.insert_many(order_batch, ordered=False)
                order_batch.clear()
    if order_batch:
        db.orders.insert_many(order_batch, ordered=False)

    # Ensure equivalent indexes
    logger.info("Building MongoDB equivalent indexes...")
    db.users.create_index(
        [("email", pymongo.ASCENDING)], unique=True, name="idx_users_email_unique"
    )
    db.products.create_index([("category_id", pymongo.ASCENDING)], name="idx_products_category_id")
    db.products.create_index([("price", pymongo.ASCENDING)], name="idx_products_price")
    db.products.create_index(
        [("name", pymongo.TEXT), ("description", pymongo.TEXT)], name="idx_products_text_name_desc"
    )
    db.carts.create_index(
        [("user_id", pymongo.ASCENDING)], unique=True, name="idx_carts_user_id_unique"
    )
    db.orders.create_index(
        [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        name="idx_orders_user_created",
    )

    logger.info("Successfully populated MongoDB with synthetic benchmark dataset.")


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic E-Commerce Dataset Generator & Bulk Loader"
    )
    parser.add_argument("--scale", choices=["test", "small", "medium", "large"], default="small")
    parser.add_argument("--users", type=int, default=None)
    parser.add_argument("--products", type=int, default=None)
    parser.add_argument("--orders", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument(
        "--target", choices=["all", "postgres", "mongo", "files-only"], default="all"
    )
    parser.add_argument("--batch-size", type=int, default=5000)

    # Connection params
    parser.add_argument("--pg-host", default=os.getenv("POSTGRES_HOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.getenv("POSTGRES_PORT", "5432")))
    parser.add_argument("--pg-user", default=os.getenv("POSTGRES_USER", "benchmark"))
    parser.add_argument("--pg-password", default=os.getenv("POSTGRES_PASSWORD", "benchmark_secret"))
    parser.add_argument("--pg-db", default=os.getenv("POSTGRES_DB", "ecommerce_benchmark"))

    parser.add_argument("--mongo-host", default=os.getenv("MONGO_HOST", "localhost"))
    parser.add_argument("--mongo-port", type=int, default=int(os.getenv("MONGO_PORT", "27017")))
    parser.add_argument("--mongo-db", default=os.getenv("MONGO_DB", "ecommerce_benchmark"))

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    preset = SCALE_PRESETS[args.scale]
    n_users = args.users or preset["users"]
    n_products = args.products or preset["products"]
    n_orders = args.orders or preset["orders"]

    # 1. Generate files
    generate_dataset(
        scale_name=args.scale,
        num_users=n_users,
        num_products=n_products,
        num_orders=n_orders,
        seed=args.seed,
        data_dir=data_dir,
    )

    if args.target == "files-only":
        logger.info("Target is 'files-only'; data generation finished.")
        return

    # 2. Bulk load Postgres
    if args.target in ("all", "postgres"):
        try:
            load_postgres(
                data_dir=data_dir,
                host=args.pg_host,
                port=args.pg_port,
                user=args.pg_user,
                password=args.pg_password,
                dbname=args.pg_db,
                batch_size=args.batch_size,
            )
        except Exception as e:
            logger.error("Failed to load PostgreSQL: %s", e)
            if args.target == "postgres":
                sys.exit(1)

    # 3. Bulk load Mongo
    if args.target in ("all", "mongo"):
        try:
            load_mongo(
                data_dir=data_dir,
                host=args.mongo_host,
                port=args.mongo_port,
                dbname=args.mongo_db,
                batch_size=args.batch_size,
            )
        except Exception as e:
            logger.error("Failed to load MongoDB: %s", e)
            if args.target == "mongo":
                sys.exit(1)


if __name__ == "__main__":
    main()
