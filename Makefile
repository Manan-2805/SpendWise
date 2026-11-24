# Makefile — Developer shortcuts for SpendWise

# ─────────────────────────────────────────
# Variables
# ─────────────────────────────────────────
APP_NAME    := spendwise
DOCKER_COMP := docker compose
TEST_COMP   := $(DOCKER_COMP) -p spendwise-test -f docker-compose.test.yml
MONITOR_COMP := $(DOCKER_COMP) --env-file .env --env-file .env.monitoring -f docker-compose.yml -f docker-compose.monitoring.yml
PYTHON      := uv run python
UV          := uv

DEV_POSTGRES_PORT ?= 15432
DEV_REDIS_PORT ?= 16379
CAPACITY_PROJECT ?= spendwise-capacity-isolated
CAPACITY_POSTGRES_PORT ?= 15434
CAPACITY_REDIS_PORT ?= 16381
export CAPACITY_PROJECT CAPACITY_POSTGRES_PORT CAPACITY_REDIS_PORT
CAPACITY_COMP := $(DOCKER_COMP) -p "$$CAPACITY_PROJECT" -f docker-compose.capacity.yml
CAPACITY_SETTINGS = DATABASE_URL=postgresql://spendwise_capacity:spendwise_capacity_local@127.0.0.1:$(CAPACITY_POSTGRES_PORT)/spendwise_capacity \
	REDIS_URL=redis://127.0.0.1:$(CAPACITY_REDIS_PORT)/0 \
	CELERY_BROKER_URL=redis://127.0.0.1:$(CAPACITY_REDIS_PORT)/1 \
	CELERY_RESULT_BACKEND=redis://127.0.0.1:$(CAPACITY_REDIS_PORT)/2 \
	CAPACITY_POSTGRES_ID="$$($(CAPACITY_COMP) ps -q capacity-postgres)" \
	CAPACITY_REDIS_ID="$$($(CAPACITY_COMP) ps -q capacity-redis)"
export DEV_POSTGRES_PORT DEV_REDIS_PORT
DEV_SETTINGS = DATABASE_URL=postgresql://spendwise:spendwise_dev_password@127.0.0.1:$(DEV_POSTGRES_PORT)/spendwise \
	REDIS_URL=redis://127.0.0.1:$(DEV_REDIS_PORT)/0 \
	CELERY_BROKER_URL=redis://127.0.0.1:$(DEV_REDIS_PORT)/1 \
	CELERY_RESULT_BACKEND=redis://127.0.0.1:$(DEV_REDIS_PORT)/2

.DEFAULT_GOAL := help

# ─────────────────────────────────────────
# Help — auto-generated from comments
# ─────────────────────────────────────────
.PHONY: help
help:  ## Show this help message
	@python3 -c "import sys, re; lines = [m.groups() for f in sys.argv[1:] for l in open(f, encoding='utf-8') if (m := re.match(r'^([a-zA-Z0-9_-]+):.*?## (.*)$$', l))]; [print(f'  \x1b[36m{k:<20}\x1b[0m {v}') for k, v in sorted(lines)]" $(MAKEFILE_LIST)

# ─────────────────────────────────────────
# Development environment
# ─────────────────────────────────────────
.PHONY: install
install:  ## Install all dependencies (including dev)
	$(UV) sync --locked --group dev
	$(PYTHON) scripts/setup_dev.py

.PHONY: install-prod
install-prod:  ## Install production dependencies only
	$(UV) sync --locked --no-dev

.PHONY: update
update:  ## Update all dependencies to latest allowed versions
	$(UV) lock --upgrade
	$(UV) sync --group dev

# ─────────────────────────────────────────
# Running the application
# ─────────────────────────────────────────
.PHONY: dev-services prepare-dev worker smoke
dev-services:  ## Start development PostgreSQL and Redis and wait until healthy
	$(DOCKER_COMP) up -d --wait postgres redis

prepare-dev: dev-services
	@$(DEV_SETTINGS) $(UV) run alembic upgrade head

smoke:  ## Check local API liveness and readiness
	curl --fail-with-body -sS http://127.0.0.1:8000/api/v1/health/live
	curl --fail-with-body -sS http://127.0.0.1:8000/api/v1/health/ready

.PHONY: openapi
openapi:  ## Export the canonical API schema without starting services
	@cd docs && test ! -e .env && env -i PATH="$$PATH" PYTHONPATH=.. \
		DATABASE_URL=postgresql://127.0.0.1/spendwise_schema \
		REDIS_URL=redis://127.0.0.1/0 CELERY_BROKER_URL=redis://127.0.0.1/1 \
		CELERY_RESULT_BACKEND=redis://127.0.0.1/2 SECRET_KEY=schema-placeholder \
		$(UV) --no-cache run --no-sync python -B -c 'import json; from pathlib import Path; from app.main import app; Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")'

worker: prepare-dev  ## Start the local Celery worker
	@$(DEV_SETTINGS) $(UV) run celery -A app.worker.celery_app worker --loglevel=info

.PHONY: dev
dev: prepare-dev  ## Run development server with reload
	@$(DEV_SETTINGS) $(UV) run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

.PHONY: run
run: prepare-dev  ## Run Granian locally with development settings
	@$(DEV_SETTINGS) $(UV) run granian --interface asgi app.main:app \
		--workers 2 \
		--host 127.0.0.1 \
		--port 8000

# ─────────────────────────────────────────
# Docker
# ─────────────────────────────────────────
.PHONY: up
up:  ## Start the development app, database, Redis, worker and Mailpit
	$(DOCKER_COMP) --profile frontend up -d --wait

.PHONY: up-build
up-build:  ## Build images and start the development stack
	$(DOCKER_COMP) --profile frontend up -d --build --wait

.PHONY: monitoring monitoring-smoke monitoring-stop
monitoring: install  ## Build and start the local stack with Granian, Prometheus and Grafana
	DEBUG=false LOCAL_DOCKERFILE=docker/Dockerfile $(MONITOR_COMP) up --build --wait

monitoring-smoke:  ## Check local Prometheus and Grafana health
	curl --fail-with-body -sS http://127.0.0.1:9090/-/ready
	curl --fail-with-body -sS http://127.0.0.1:3000/api/health

monitoring-stop:  ## Stop the monitored local stack and keep its data
	$(MONITOR_COMP) stop

.PHONY: down
down:  ## Stop and remove containers
	$(DOCKER_COMP) --profile frontend down

.PHONY: down-volumes
down-volumes:  ## Stop containers and remove volumes (DESTROYS DATA)
	$(DOCKER_COMP) --profile frontend down -v

.PHONY: logs
logs:  ## Follow logs from all containers
	$(DOCKER_COMP) logs -f

.PHONY: logs-api
logs-api:  ## Follow logs from the API container only
	$(DOCKER_COMP) logs -f api

.PHONY: shell
shell:  ## Open a shell in the running API container
	$(DOCKER_COMP) exec api bash

.PHONY: db-shell
db-shell:  ## Open a psql shell in the PostgreSQL container
	$(DOCKER_COMP) exec postgres psql -U spendwise -d spendwise

.PHONY: redis-shell
redis-shell:  ## Open a redis-cli shell
	$(DOCKER_COMP) exec redis redis-cli

# ─────────────────────────────────────────
# Database migrations (Alembic)
# ─────────────────────────────────────────
.PHONY: migrate
migrate:  ## Apply all pending migrations (alembic upgrade head)
	$(UV) run alembic upgrade head

.PHONY: migration
migration:  ## Create a new migration: make migration name="add users table"
	$(UV) run alembic revision --autogenerate -m "$(name)"

.PHONY: rollback
rollback:  ## Roll back the last migration
	$(UV) run alembic downgrade -1

.PHONY: db-reset
db-reset:  ## Roll back all migrations and re-apply (DESTROYS DATA)
	$(UV) run alembic downgrade base
	$(UV) run alembic upgrade head

.PHONY: db-history
db-history:  ## Show migration history
	$(UV) run alembic history --verbose

.PHONY: db-current
db-current:  ## Show current migration state
	$(UV) run alembic current

# ─────────────────────────────────────────
# Testing
# ─────────────────────────────────────────
.PHONY: test-services test benchmark
test-services:  ## Start disposable PostgreSQL and Redis on dedicated local ports
	$(TEST_COMP) up -d --wait

benchmark: test-services  ## Measure API throughput and p95 on disposable services
	$(PYTHON) scripts/run_load_test.py $(BENCHMARK_ARGS)

.PHONY: capacity capacity-db-shell capacity-services
capacity-services:
	@case "$$CAPACITY_PROJECT" in spendwise-capacity-?*) ;; *) echo 'Use a spendwise-capacity- project'; exit 1;; esac
	$(CAPACITY_COMP) up -d --wait

capacity: seed-capacity  ## Run the open-loop capacity test with two API and two Celery workers
	@$(CAPACITY_SETTINGS) $(PYTHON) -m scripts.run_capacity_test $(CAPACITY_ARGS)

capacity-db-shell:  ## Open psql on the isolated capacity database
	$(CAPACITY_COMP) exec capacity-postgres psql -U spendwise_capacity -d spendwise_capacity

test: test-services  ## Run all tests with the 85% coverage gate
	$(UV) run pytest

.PHONY: test-unit
test-unit:  ## Run unit tests without starting services
	$(UV) run pytest --no-cov tests/unit/

.PHONY: test-integration
test-integration: test-services  ## Run integration tests against disposable services
	$(UV) run pytest --no-cov tests/integration/

.PHONY: test-cov
test-cov: test-services  ## Run tests with coverage report
	$(UV) run pytest --cov=app --cov-report=html --cov-report=term-missing

.PHONY: test-fast
test-fast: test-services  ## Run tests with coverage and stop on the first failure
	$(UV) run pytest -x -q

.PHONY: test-watch
test-watch:  ## Rerun tests on application or test source changes
	$(UV) run watchfiles "make test-fast" app tests

# ─────────────────────────────────────────
# Code quality & Security
# ─────────────────────────────────────────
.PHONY: pre-commit-install
pre-commit-install:  ## Install git pre-commit hook
	$(UV) run pre-commit install --install-hooks

.PHONY: pre-commit-run
pre-commit-run:  ## Run pre-commit hooks manually on all files
	$(UV) run pre-commit run --all-files

.PHONY: lint
lint:  ## Run ruff linter
	$(UV) run ruff check alembic/ app/ scripts/ tests/

.PHONY: lint-fix
lint-fix:  ## Run ruff linter and auto-fix issues
	$(UV) run ruff check --fix alembic/ app/ scripts/ tests/

.PHONY: format
format:  ## Format code with ruff
	$(UV) run ruff format alembic/ app/ scripts/ tests/

.PHONY: format-check
format-check:  ## Check code formatting without making changes
	$(UV) run ruff format --check alembic/ app/ scripts/ tests/

.PHONY: typecheck
typecheck:  ## Run mypy type checker
	$(UV) run mypy app/

.PHONY: security-check
security-check:  ## Run bandit to find common security issues in python code
	$(UV) run bandit -c pyproject.toml -r app/

.PHONY: audit
audit:  ## Run pip-audit to scan dependencies for known vulnerabilities
	$(UV) run pip-audit

.PHONY: check
check: lint format-check typecheck security-check audit test  ## Run tests, lint, type checks and security checks

# ─────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────
.PHONY: seed
seed: up  ## Seed the Docker development database with sample data
	$(DOCKER_COMP) exec -T api python -m scripts.seed_db

.PHONY: seed-capacity
seed-capacity: capacity-services  ## Seed 5,000 users, 20,000 categories and 320,000 transactions in the capacity database
	@$(CAPACITY_SETTINGS) $(PYTHON) -m scripts.seed_load_test_db --capacity

.PHONY: create-superuser
create-superuser:  ## Create an admin user interactively
	$(PYTHON) scripts/create_superuser.py

.PHONY: secret
secret:  ## Generate a new SECRET_KEY value
	$(PYTHON) -c "import secrets; print(secrets.token_hex(32))"

.PHONY: clean
clean:  ## Remove Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	find . -type f -name "*.pyo" -delete 2>/dev/null; true
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/

.PHONY: prod-migrate prod-up
prod-migrate:  ## Run production migrations with the migration-role database URL
	@test -n "$${SPENDWISE_MIGRATION_DATABASE_URL:-}" || { echo "Set SPENDWISE_MIGRATION_DATABASE_URL"; exit 1; }
	$(DOCKER_COMP) -f docker-compose.prod.yml run --rm migrate

prod-up:  ## Start production services after a successful migration
	$(DOCKER_COMP) -f docker-compose.prod.yml up -d web frontend celery_worker celery_beat

.PHONY: build
build:  ## Build the production Docker image
	docker build -t $(APP_NAME):latest -f docker/Dockerfile .

.PHONY: build-dev
build-dev:  ## Build the development Docker image
	docker build -t $(APP_NAME):dev -f docker/Dockerfile.dev .

# Frontend
NPM ?= npm
.PHONY: frontend-install frontend-dev frontend-lint frontend-test frontend-typecheck frontend-build frontend-check frontend-e2e
frontend-install:  ## Install the locked frontend dependencies
	$(NPM) --prefix frontend ci --strict-peer-deps

frontend-dev:  ## Serve the frontend on localhost:3000
	$(NPM) --prefix frontend run dev

frontend-lint:  ## Check frontend lint with zero warnings
	$(NPM) --prefix frontend run lint

frontend-typecheck:  ## Check strict frontend TypeScript
	$(NPM) --prefix frontend run typecheck

frontend-test:  ## Run frontend unit and component tests
	$(NPM) --prefix frontend test

frontend-build:  ## Build the frontend production assets
	$(NPM) --prefix frontend run build

frontend-check: frontend-lint frontend-test frontend-build  ## Run frontend checks and budgets
	$(NPM) --prefix frontend run check:bundle
	$(NPM) --prefix frontend run check:contrast

frontend-e2e:  ## Run the browser flow against an isolated API and databases
	$(NPM) --prefix frontend run test:e2e
