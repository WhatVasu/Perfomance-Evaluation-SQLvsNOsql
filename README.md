# A Performance Evaluation of MongoDB and PostgreSQL Using an Identical E-Commerce Application

A reproducible empirical research project comparing **PostgreSQL 16** (relational, 3NF normalized, ACID) and **MongoDB 7** (document model, embedded subdocuments, multi-document ACID transactions) under identical e-commerce workloads.

> **Methodological Guarantee**: The database backend is the **ONLY variable** between runs. The REST API contracts, business services, network concurrency, connection pooling, and Docker hardware resource limits are 100% identical.

---

## Architecture Overview

```
                                +-----------------------------+
                                |  Load Generator (Locust)    |
                                |  Browse / Cart / Checkout   |
                                +--------------+--------------+
                                               | HTTP (JSON)
                                               v
                                +-----------------------------+
                                |      FastAPI Web API        |
                                |       (Python 3.12)         |
                                +--------------+--------------+
                                               |
                                +--------------v--------------+
                                |      Repository Factory     |
                                |  DB_BACKEND=postgres|mongo  |
                                +-------+-------------+-------+
                                        |             |
                 +----------------------+             +----------------------+
                 |                                                           |
                 v                                                           v
  +------------------------------+                            +------------------------------+
  |    PostgreSQL Repository     |                            |      MongoDB Repository      |
  |  - SQLAlchemy 2.0 + psycopg3 |                            |  - Motor 3.6 / PyMongo async |
  |  - Connection Pool: 50       |                            |  - Connection Pool: 50       |
  |  - synchronous_commit = on   |                            |  - w="majority", j=True      |
  |  - 3NF Normalized Tables     |                            |  - Embedded Documents (rs0)  |
  +--------------+---------------+                            +--------------+---------------+
                 |                                                           |
                 v                                                           v
  +------------------------------+                            +------------------------------+
  |    PostgreSQL 16 Container   |                            |     MongoDB 7.0 Container    |
  |  (2.0 CPUs, 2GB RAM Limit)   |                            |   (2.0 CPUs, 2GB RAM Limit)  |
  +------------------------------+                            +------------------------------+
```

---

## Repository Structure

```text
FSWD-proj/
├── app/
│   ├── config.py                 # Pydantic v2 settings & database connection strings
│   ├── database.py               # Async engine (SQLAlchemy/psycopg3) & Motor setup
│   ├── dependencies.py           # Dependency injection for repositories & auth
│   ├── exceptions.py             # Unified domain exceptions (Stock, Cart, Conflict)
│   ├── main.py                   # FastAPI application factory & lifespan handler
│   ├── models/                   # PostgreSQL SQLAlchemy 2.0 ORM models
│   ├── schemas/                  # Pydantic v2 domain & API schemas
│   ├── repositories/
│   │   ├── base.py               # Abstract interfaces (UserRepository, ProductRepository, etc.)
│   │   ├── factory.py            # Dynamic backend resolution factory
│   │   ├── postgres/             # PostgreSQL 16 implementation
│   │   └── mongo/                # MongoDB 7 implementation (with replica set transactions)
│   ├── services/                 # Database-agnostic business logic (auth, checkout)
│   ├── routers/                  # REST endpoints (/auth, /products, /cart, /orders)
│   └── templates/                # Minimal Jinja2 templates (products, cart, orders)
├── scripts/
│   ├── seed.py                   # Deterministic dataset generator & bulk loader
│   └── run_benchmark.py          # Benchmark orchestrator (Locust + resource sampler)
├── loadtest/
│   ├── locustfile.py             # Locust user workloads (Browse, Search, Cart, Checkout, Mixed)
│   └── sampler.py                # CPU % and Memory (MB) sampler for database containers
├── analysis/
│   └── analyze.py                # Statistical analysis, 95% CI tables, and 200 dpi figures
├── docs/
│   ├── schema.md                 # Detailed normalized vs document schema specification
│   └── methodology.md            # Experimental rigor, testing protocol & validity threats
├── tests/                        # Parametrized pytest test suite across both backends
├── results/                      # Raw CSVs, resource metrics, summary tables & charts
├── docker-compose.yml            # Docker definitions with hardware limits (2 CPU, 2GB RAM)
├── Dockerfile                    # Container definition for API server
├── Makefile                      # Cross-platform command targets
└── pyproject.toml                # Pinned dependencies & tooling config
```

---

## Quickstart & Setup

### 1. Prerequisites
- **Python 3.12+**
- **Docker & Docker Compose**

### 2. Environment Setup
Clone the repository and install dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

Copy the example environment configuration:
```bash
cp .env.example .env
```

### 3. Start Database Containers
```bash
make up
# Or: docker compose up -d
```
This boots:
- PostgreSQL 16 with `synchronous_commit=on` (Port `5432`).
- MongoDB 7 initialized with single-node replica set `rs0` for multi-document ACID transactions (Port `27017`).

---

## Switching Database Backends

The database backend is controlled **strictly by one environment variable**:
```bash
# In .env or shell environment:
DB_BACKEND=postgres
# or
DB_BACKEND=mongo
```

No routes, domain services, or client code change. The repository factory (`app/repositories/factory.py`) automatically instantiates the corresponding driver and repository layer.

---

## Generating Synthetic Data

To generate a deterministic synthetic dataset and bulk-load identical records into both databases:

```bash
# Small scale: 10k users, 5k products, 50k orders (default)
make seed SCALE=small

# Medium scale: 100k users, 50k products, 500k orders
make seed SCALE=medium

# Test scale (fast smoke test): 100 users, 50 products, 200 orders
python scripts/seed.py --scale test
```

Data records are deterministically generated to static files in `data/` using a fixed seed (`--seed 42`), ensuring **byte-for-byte identical datasets in both databases**.

---

## Running the Benchmark

### Full Benchmark Matrix
To run the full evaluation across all concurrency levels (`10, 50, 100, 500 users`), 5 repeated runs per level, with 60 s warmup and 5 min measurement:

```bash
make bench
```

### Quick Verification Run
To verify the full automated pipeline end-to-end in seconds:
```bash
make bench-quick
# Or: python scripts/run_benchmark.py --quick
```

During execution:
- Locust drives traffic against the target API backend.
- Background resource sampler captures container CPU % and RAM MB every 1 second.
- Raw per-request latency logs are flushed to `results/raw/`.
- Container resource logs are flushed to `results/resources/`.

---

## Statistical Analysis & Reports

After benchmark completion, generate analytical tables and high-resolution charts:

```bash
make analyze
```

This generates:
1. `results/summary.csv`: Tabular aggregates (throughput, p50, p95, p99 latency, error rates, % differences).
2. `results/summary.md`: Formatted Markdown report with 95% Confidence Intervals across runs.
3. `results/figures/`: High-resolution figures (200 DPI PNG):
   - `throughput_vs_concurrency.png`: Requests/sec scaling curves with error bands.
   - `latency_p95_vs_concurrency.png`: Tail latency scaling curves.
   - `latency_by_endpoint.png`: Endpoint-by-endpoint latency comparison.
   - `resource_utilization.png`: Average CPU % and Memory footprint per database.

---

## Running Tests

Run the complete test suite parameterized across **both** backends:

```bash
make test
# Or: pytest -v
```

The tests verify:
- Authentication & JWT token security
- Product browsing, category filtering, and keyword text search
- Shopping cart additions, updates, and removal
- Atomic checkout transaction semantics
- **Concurrent checkout race condition**: When 10 concurrent requests compete for the last 5 items, exactly 5 succeed, 5 fail with conflict, and **inventory never drops below zero**.

---

## Code Quality & Linting

```bash
# Check code style with ruff
make lint

# Format codebase
make format
```
