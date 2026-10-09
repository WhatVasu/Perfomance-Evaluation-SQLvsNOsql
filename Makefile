# Makefile for E-Commerce Database Benchmark (PostgreSQL 16 vs MongoDB 7)

PYTHON ?= python
SCALE ?= small

.PHONY: help up down seed bench bench-quick analyze test lint format clean

help:
	@echo "Available commands:"
	@echo "  make up           - Start PostgreSQL, MongoDB replica set, and services in Docker Compose"
	@echo "  make down         - Stop Docker Compose services"
	@echo "  make seed         - Generate deterministic dataset & bulk-load (e.g. make seed SCALE=medium)"
	@echo "  make bench        - Execute full benchmark matrix (concurrency: 10, 50, 100, 500 across 5 runs)"
	@echo "  make bench-quick  - Execute rapid smoke benchmark run for quick verification"
	@echo "  make analyze      - Compute statistical aggregates (95% CI) and generate 200 dpi figures"
	@echo "  make test         - Run parameterized pytest test suite"
	@echo "  make lint         - Run ruff linter check"
	@echo "  make format       - Format code using ruff"
	@echo "  make clean        - Remove generated data, raw benchmark CSVs, and artifacts"

up:
	docker compose up -d

down:
	docker compose down

seed:
	$(PYTHON) scripts/seed.py --scale $(SCALE)

bench:
	$(PYTHON) scripts/run_benchmark.py --scale $(SCALE)

bench-quick:
	$(PYTHON) scripts/run_benchmark.py --quick

analyze:
	$(PYTHON) analysis/analyze.py

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .

clean:
	rm -rf data/*.json data/*.jsonl results/raw/*.csv results/resources/*.csv results/figures/*.png results/summary.* .pytest_cache .ruff_cache
