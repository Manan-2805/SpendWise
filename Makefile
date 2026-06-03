# Makefile — Developer shortcuts for SpendWise

# ─────────────────────────────────────────
# Variables
# ─────────────────────────────────────────
APP_NAME    := spendwise
DOCKER_COMP := docker compose
PYTHON      := uv run python
UV          := uv

.DEFAULT_GOAL := help

# ─────────────────────────────────────────
# Help — auto-generated from comments
# ─────────────────────────────────────────
.PHONY: help
help:  ## Show this help message
	@python -c "import sys, re; lines = [m.groups() for f in sys.argv[1:] for l in open(f, encoding='utf-8') if (m := re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', l))]; [print(f'  \x1b[36m{k:<20}\x1b[0m {v}') for k, v in sorted(lines)]" $(MAKEFILE_LIST)

# ─────────────────────────────────────────
# Development environment
# ─────────────────────────────────────────
.PHONY: install
install:  ## Install all dependencies (including dev)
	$(UV) sync --group dev

.PHONY: install-prod
install-prod:  ## Install production dependencies only
	$(UV) sync --no-dev

.PHONY: update
update:  ## Update all dependencies to latest allowed versions
	$(UV) lock --upgrade
	$(UV) sync --group dev

# ─────────────────────────────────────────
# Running the application
# ─────────────────────────────────────────
.PHONY: dev
dev:  ## Run development server with hot reload (requires running DB and Redis)
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app

.PHONY: run
run:  ## Run production server locally
	$(UV) run granian --interface asgi app.main:app \
		--workers 4 \
		--host 0.0.0.0 \
		--port 8000

# ─────────────────────────────────────────
# Docker
# ─────────────────────────────────────────
.PHONY: up
up:  ## Start the full stack (API + DB + Redis) in background
	$(DOCKER_COMP) up -d

.PHONY: up-build
up-build:  ## Build images and start the stack
	$(DOCKER_COMP) up -d --build

.PHONY: down
down:  ## Stop and remove containers
	$(DOCKER_COMP) down

.PHONY: down-volumes
down-volumes:  ## Stop containers and remove volumes (DESTROYS DATA)
	$(DOCKER_COMP) down -v

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
.PHONY: test
test:  ## Run all tests
	$(UV) run pytest

.PHONY: test-unit
test-unit:  ## Run unit tests only
	$(UV) run pytest tests/unit/ -v

.PHONY: test-integration
test-integration:  ## Run integration tests only
	$(UV) run pytest tests/integration/ -v

.PHONY: test-cov
test-cov:  ## Run tests with coverage report
	$(UV) run pytest --cov=app --cov-report=html --cov-report=term-missing

.PHONY: test-fast
test-fast:  ## Run tests — stop on first failure, no coverage
	$(UV) run pytest -x -q

.PHONY: test-watch
test-watch:  ## Run tests and re-run on file changes (requires pytest-watch)
	$(UV) run ptw -- -x -q

# ─────────────────────────────────────────
# Code quality & Security
# ─────────────────────────────────────────
.PHONY: pre-commit-install
pre-commit-install:  ## Install git pre-commit hook
	$(UV) run pre-commit install

.PHONY: pre-commit-run
pre-commit-run:  ## Run pre-commit hooks manually on all files
	$(UV) run pre-commit run --all-files

.PHONY: lint
lint:  ## Run ruff linter
	$(UV) run ruff check alembic/ app/ tests/

.PHONY: lint-fix
lint-fix:  ## Run ruff linter and auto-fix issues
	$(UV) run ruff check --fix alembic/ app/ tests/

.PHONY: format
format:  ## Format code with ruff
	$(UV) run ruff format alembic/ app/ tests/

.PHONY: format-check
format-check:  ## Check code formatting without making changes
	$(UV) run ruff format --check alembic/ app/ tests/

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
check: lint format-check typecheck security-check audit  ## Run all code quality and security checks

# ─────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────
.PHONY: seed
seed:  ## Seed the development database with sample data
	$(PYTHON) scripts/seed_db.py

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

.PHONY: build
build:  ## Build the production Docker image
	docker build -t $(APP_NAME):latest -f docker/Dockerfile .

.PHONY: build-dev
build-dev:  ## Build the development Docker image
	docker build -t $(APP_NAME):dev -f docker/Dockerfile.dev .
