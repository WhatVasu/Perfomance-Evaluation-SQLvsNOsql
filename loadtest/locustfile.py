import os
import random
import threading
from datetime import UTC, datetime
from pathlib import Path

from locust import HttpUser, between, events, task

# Environment metadata injected by benchmark runner
BENCH_BACKEND = os.getenv("BENCH_BACKEND", "postgres")
BENCH_SCALE = os.getenv("BENCH_SCALE", "small")
BENCH_USERS = os.getenv("BENCH_USERS", "10")
BENCH_RUN = os.getenv("BENCH_RUN", "1")
RAW_CSV_PATH = os.getenv("RAW_CSV_PATH", "")
WARMUP_UNTIL = float(os.getenv("WARMUP_UNTIL", "0"))

# Thread-safe raw metrics logger
raw_file_lock = threading.Lock()
raw_csv_initialized = False

SEARCH_KEYWORDS = [
    "Item",
    "Audio",
    "Wireless",
    "Headphones",
    "Cable",
    "Cotton",
    "Shoes",
    "Book",
    "Kitchen",
    "Pro",
    "Max",
    "Fast",
    "Ultra",
]


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    global raw_csv_initialized
    if RAW_CSV_PATH:
        raw_path = Path(RAW_CSV_PATH)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_file_lock:
            if not raw_path.exists() or raw_path.stat().st_size == 0:
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write("backend,scale,users,run,endpoint,timestamp,latency_ms,status\n")
            raw_csv_initialized = True


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    # If currently in warmup phase, discard from measured CSV
    now_ts = datetime.now(UTC).timestamp()
    if now_ts < WARMUP_UNTIL:
        return

    if RAW_CSV_PATH:
        status_str = "SUCCESS" if exception is None else "FAILURE"
        iso_time = datetime.now(UTC).isoformat()
        line = f"{BENCH_BACKEND},{BENCH_SCALE},{BENCH_USERS},{BENCH_RUN},{name},{iso_time},{response_time:.2f},{status_str}\n"
        with raw_file_lock:
            with open(RAW_CSV_PATH, "a", encoding="utf-8") as f:
                f.write(line)


class BaseBenchmarkUser(HttpUser):
    abstract = True
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.user_email = f"locust_{random.randint(100000, 99999999)}@benchmark.test"
        self.password = "Password123!"
        self.auth_headers = {}
        self.product_ids: list[str] = []
        self.category_ids: list[str] = []

        # 1. Register & Login
        reg_res = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.user_email, "full_name": "Locust User", "password": self.password},
            name="/api/v1/auth/register",
        )
        if reg_res.status_code == 201:
            login_res = self.client.post(
                "/api/v1/auth/login",
                json={"email": self.user_email, "password": self.password},
                name="/api/v1/auth/login",
            )
            if login_res.status_code == 200:
                token = login_res.json().get("access_token")
                self.auth_headers = {"Authorization": f"Bearer {token}"}

        # 2. Pre-fetch catalog sample
        cat_res = self.client.get("/api/v1/products/categories", name="/api/v1/products/categories")
        if cat_res.status_code == 200:
            self.category_ids = [c["id"] for c in cat_res.json()]

        prod_res = self.client.get("/api/v1/products?page=1&page_size=50", name="/api/v1/products")
        if prod_res.status_code == 200:
            self.product_ids = [p["id"] for p in prod_res.json().get("items", [])]


class BrowseUser(BaseBenchmarkUser):
    @task(3)
    def list_products(self):
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/products?page={page}&page_size=20", name="/api/v1/products")

    @task(2)
    def filter_by_category(self):
        if self.category_ids:
            cat_id = random.choice(self.category_ids)
            self.client.get(
                f"/api/v1/products?category_id={cat_id}", name="/api/v1/products?category"
            )

    @task(2)
    def filter_by_price(self):
        min_p = random.randint(10, 50)
        max_p = min_p + random.randint(20, 200)
        self.client.get(
            f"/api/v1/products?min_price={min_p}&max_price={max_p}", name="/api/v1/products?price"
        )

    @task(3)
    def view_product(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.get(f"/api/v1/products/{pid}", name="/api/v1/products/{id}")


class SearchUser(BaseBenchmarkUser):
    @task(1)
    def search_products(self):
        query = random.choice(SEARCH_KEYWORDS)
        self.client.get(f"/api/v1/products?search={query}", name="/api/v1/products?search")


class CartUser(BaseBenchmarkUser):
    @task(2)
    def view_cart(self):
        self.client.get("/api/v1/cart", headers=self.auth_headers, name="/api/v1/cart")

    @task(3)
    def add_to_cart(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.post(
                "/api/v1/cart/items",
                json={"product_id": pid, "quantity": random.randint(1, 2)},
                headers=self.auth_headers,
                name="/api/v1/cart/items [POST]",
            )

    @task(2)
    def update_quantity(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.put(
                f"/api/v1/cart/items/{pid}",
                json={"quantity": random.randint(1, 3)},
                headers=self.auth_headers,
                name="/api/v1/cart/items/{id} [PUT]",
            )

    @task(1)
    def remove_item(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.delete(
                f"/api/v1/cart/items/{pid}",
                headers=self.auth_headers,
                name="/api/v1/cart/items/{id} [DELETE]",
            )


class CheckoutUser(BaseBenchmarkUser):
    @task(1)
    def checkout_flow(self):
        # 1. Add item
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.post(
                "/api/v1/cart/items",
                json={"product_id": pid, "quantity": 1},
                headers=self.auth_headers,
                name="/api/v1/cart/items [POST]",
            )
        # 2. Place order
        self.client.post(
            "/api/v1/orders/checkout",
            headers=self.auth_headers,
            name="/api/v1/orders/checkout",
        )
        # 3. View history
        self.client.get(
            "/api/v1/orders",
            headers=self.auth_headers,
            name="/api/v1/orders",
        )


class MixedEcommerceUser(BaseBenchmarkUser):
    """
    Standard Mixed Profile:
    - 70% Reads (browse, filter, view, search)
    - 20% Cart writes (add, update, remove)
    - 10% Checkout (place order)
    """

    # --- 70% READ WORKLOAD (weights total = 70) ---
    @task(25)
    def browse_products(self):
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/products?page={page}&page_size=20", name="/api/v1/products")

    @task(15)
    def view_product_detail(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.get(f"/api/v1/products/{pid}", name="/api/v1/products/{id}")

    @task(15)
    def search_products(self):
        term = random.choice(SEARCH_KEYWORDS)
        self.client.get(f"/api/v1/products?search={term}", name="/api/v1/products?search")

    @task(15)
    def filter_products(self):
        if random.random() < 0.5 and self.category_ids:
            cat_id = random.choice(self.category_ids)
            self.client.get(
                f"/api/v1/products?category_id={cat_id}", name="/api/v1/products?category"
            )
        else:
            min_p = random.randint(10, 40)
            self.client.get(
                f"/api/v1/products?min_price={min_p}&max_price={min_p + 100}",
                name="/api/v1/products?price",
            )

    # --- 20% CART WORKLOAD (weights total = 20) ---
    @task(10)
    def add_item_to_cart(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.post(
                "/api/v1/cart/items",
                json={"product_id": pid, "quantity": 1},
                headers=self.auth_headers,
                name="/api/v1/cart/items [POST]",
            )

    @task(6)
    def update_cart_item(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.put(
                f"/api/v1/cart/items/{pid}",
                json={"quantity": random.randint(1, 4)},
                headers=self.auth_headers,
                name="/api/v1/cart/items/{id} [PUT]",
            )

    @task(4)
    def remove_cart_item(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.delete(
                f"/api/v1/cart/items/{pid}",
                headers=self.auth_headers,
                name="/api/v1/cart/items/{id} [DELETE]",
            )

    # --- 10% CHECKOUT WORKLOAD (weights total = 10) ---
    @task(10)
    def checkout_order(self):
        # Ensure cart has at least 1 item before checking out
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.post(
                "/api/v1/cart/items",
                json={"product_id": pid, "quantity": 1},
                headers=self.auth_headers,
                name="/api/v1/cart/items [POST]",
            )

        res = self.client.post(
            "/api/v1/orders/checkout",
            headers=self.auth_headers,
            name="/api/v1/orders/checkout",
        )
        if res.status_code == 201:
            self.client.get(
                "/api/v1/orders",
                headers=self.auth_headers,
                name="/api/v1/orders",
            )
