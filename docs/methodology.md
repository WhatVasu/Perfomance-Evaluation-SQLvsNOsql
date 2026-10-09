# Experimental Methodology: Comparative Evaluation of MongoDB 7 and PostgreSQL 16

**Research Project Title:** *A Performance Evaluation of MongoDB and PostgreSQL Using an Identical E-Commerce Application*  
**Author:** Antigravity Engineering Research  
**Target Environment:** Python 3.12, FastAPI, PostgreSQL 16, MongoDB 7 (Single-Node Replica Set `rs0`)

---

## 1. Research Question & Hypothesis

### 1.1 Research Question
How do PostgreSQL 16 (a relational database with normalized schema and ACID transactions) and MongoDB 7 (a document database with embedded subdocuments and multi-document ACID transactions) compare in terms of **throughput (RPS)**, **tail latency (p95, p99)**, **resource utilization (CPU % and RAM MB)**, and **scalability** when executing an identical e-commerce workload where the database backend is the **sole variable**?

### 1.2 Hypotheses
- **Hypothesis 1 (Read-heavy Browse/Search)**: MongoDB's document model with pre-joined embedded structures and native full-text indexes will yield comparable or lower latency on read-heavy browsing, whereas PostgreSQL will excel in structured relational filtering due to mature query planning.
- **Hypothesis 2 (Frequent Small Writes / Cart)**: MongoDB will achieve equal or higher write throughput for cart item manipulations because embedded array modifications require only single-document lock acquisition.
- **Hypothesis 3 (Multi-step Transactional Checkout)**: PostgreSQL will demonstrate lower latency and lower resource amplification during ACID checkout operations under high concurrency due to lightweight row-level locks compared to MongoDB's WiredTiger ticket acquisition and WiredTiger cache overhead during multi-document transactions.

---

## 2. Experimental Rigor & Fairness Controls

To ensure scientific validity and reproducibility, all confounding variables outside the database engine are strictly held constant:

```
+-----------------------------------------------------------------------------------+
|                            FastAPI E-Commerce Service                             |
|                                                                                   |
|  [ Routers ]  --->  [ Domain Services ]  --->  [ Repository Factory Interface ]  |
+-----------------------------------------------------------------------------------+
                                                          |
                       +----------------------------------+----------------------------------+
                       |                                                                     |
                       v                                                                     v
          [ PostgreSQL 16 Engine ]                                              [ MongoDB 7 Engine ]
          - Driver: psycopg 3 (async)                                           - Driver: Motor 3.6 / PyMongo (async)
          - Connection Pool: 50 fixed                                           - Connection Pool: 50 fixed
          - Durability: synchronous_commit=on                                   - Durability: w=majority, j=True
          - Resource Quota: 2.0 CPUs, 2GB RAM                                   - Resource Quota: 2.0 CPUs, 2GB RAM
          - Equivalent B-Tree & Text Indexes                                    - Equivalent B-Tree & Text Indexes
```

### 2.1 Driver & Concurrency Parity
Both engines are accessed asynchronously from FastAPI using modern async I/O drivers:
- **PostgreSQL**: `SQLAlchemy 2.0` async core engine backed by `psycopg 3` (`postgresql+psycopg://`).
- **MongoDB**: `Motor 3.6` (`AsyncIOMotorClient`) running on top of PyMongo.
- **Connection Pools**: Strictly pinned to `pool_size = 50` with `max_overflow = 0` (or `maxPoolSize = 50`, `minPoolSize = 10`).

### 2.2 Durability & ACID Guarantees
- **PostgreSQL**: Configured with `synchronous_commit = on`. Write-Ahead Logging (WAL) is flushed to disk before transaction commits return.
- **MongoDB**: Configured with Write Concern `w = "majority"` and `j = true` (journaling enabled). Writes and multi-document transactions must be flushed to the journal before acknowledgment.

### 2.3 Compute & Memory Isolation
Both database instances are containerized in Docker with identical resource limits:
- `cpus: "2.0"`
- `memory: 2G`

### 2.4 Indexing Parity
Identical index topologies are generated and verified prior to every test cycle:
- `users`: Unique index on `email`.
- `products`: Indexes on `category_id`, `price`, and text search on `name`.
- `orders`: Compound index on `(user_id, created_at DESC)`.

---

## 3. Synthetic Dataset & Scale Profiles

The dataset is generated deterministically using Python's `Faker` library with a fixed random seed (`--seed 42`). The generated records are exported to disk once in `data/` and then bulk-loaded into both databases, ensuring that record counts, IDs, strings, prices, and relationships are 100% identical.

| Scale Preset | Users | Products | Historical Orders | Disk Size (Approx) |
| :--- | :--- | :--- | :--- | :--- |
| **Test** | 100 | 50 | 200 | < 1 MB |
| **Small** | 10,000 | 5,000 | 50,000 | ~ 45 MB |
| **Medium** | 100,000 | 50,000 | 500,000 | ~ 450 MB |
| **Large** | 1,000,000 | 200,000 | 5,000,000 | ~ 4.8 GB |

---

## 4. Workload Specification

Load generation is driven by **Locust** in headless mode. The primary evaluation uses a **realistic mixed e-commerce user profile**:

### 4.1 Workload Distribution
- **70% Read Workload**:
  - `GET /api/v1/products?page={}&page_size=20` (Paginated catalog browse)
  - `GET /api/v1/products/{id}` (Product detail view)
  - `GET /api/v1/products?category_id={}` and `min_price={}&max_price={}` (Filtered browse)
  - `GET /api/v1/products?search={term}` (Catalog keyword text search)
- **20% Cart Write Workload**:
  - `POST /api/v1/cart/items` (Add product to cart)
  - `PUT /api/v1/cart/items/{product_id}` (Update item quantity)
  - `DELETE /api/v1/cart/items/{product_id}` (Remove item from cart)
  - `GET /api/v1/cart` (Inspect active cart)
- **10% Multi-Document ACID Checkout Workload**:
  - `POST /api/v1/orders/checkout` (Atomic checkout transaction)
  - `GET /api/v1/orders` (Fetch completed order history)

---

## 5. Testing Protocol & Experimental Matrix

### 5.1 Concurrency Matrix
Four concurrent load levels are evaluated: **10, 50, 100, and 500 virtual users**.

### 5.2 Test Execution Cycle
For every concurrency tier and database backend:
1. **Database Reset**: Tables/collections are reset and reloaded with the identical dataset.
2. **Warm-up Window (60 seconds)**: Locust spawns users and executes traffic. All requests captured during this window are discarded from the metric computations to eliminate cold-start cache anomalies.
3. **Measurement Window (300 seconds / 5 minutes)**: Raw request logs (timestamp, endpoint, latency, status) are recorded to `results/raw/`.
4. **Repetitions (5 runs)**: Each tier is repeated **5 independent times**.
5. **Alternating Order**: The execution order of backends alternates between runs (e.g., Run 1: Postgres -> Mongo; Run 2: Mongo -> Postgres) to eliminate thermal throttling or host caching bias.

---

## 6. Metrics & Statistical Treatment

### 6.1 Performance Metrics
- **Throughput**: Sustained requests per second ($\text{RPS} = \frac{N_{\text{requests}}}{T_{\text{measured}}}$).
- **Latency**: Mean, median (p50), 95th percentile (p95), and 99th percentile (p99) response time in milliseconds.
- **Error Rate**: Percentage of requests returning HTTP 4xx/5xx or timeouts.

### 6.2 System Resource Sampling
A background sampler records CPU utilization (%) and Memory footprint (MB) every 1 second:
- Monitored via `docker stats` container sampling and verified via `psutil`.

### 6.3 Statistical Confidence Intervals
Across the 5 repeated runs per configuration, we report the sample mean $\bar{x}$ and the **95% Confidence Interval** calculated using the Student's $t$-distribution:
$$\text{CI}_{95\%} = \bar{x} \pm t_{0.025, n-1} \cdot \frac{s}{\sqrt{n}}$$
Where $n = 5$, and $s$ is the sample standard deviation across runs.

---

## 7. Threats to Validity & Mitigations

| Threat | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **Driver Overhead** | Asymmetric Python client drivers could skew latency. | Both engines use native C/Rust-backed async drivers (`psycopg-binary` for PG, `pymongo/motor` with C BSON extensions for Mongo). |
| **Cache Warming Bias** | The first backend tested might suffer cold OS/disk caches. | 60-second warmup window discarded from analysis; backend test order alternates systematically on every run. |
| **Host Resource Starvation** | Unconstrained processes consuming arbitrary host RAM. | Strict Docker container quotas (`cpus: 2.0`, `memory: 2G`) enforced via `docker-compose.yml`. |
| **Dataset Drift** | Random data varying between backends. | Data generated deterministically to static files once (`data/*.json*`) and bulk-loaded identically into both databases. |
| **Concurrency Deadlocks** | Concurrent checkout transactions aborting due to row lock cycles. | Both repository implementations sort product IDs deterministically before acquiring locks or executing inventory decrements. |
