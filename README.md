# SpendWise API

SpendWise is a production-ready, high-performance personal expense tracker REST API built using Python 3.12+, FastAPI, and PostgreSQL. It delivers a secure and structured backend designed for managing user authentication, custom income/expense categories, financial transactions, and generating aggregated reports.

The application is architected around the **Repository & Service Pattern (Clean Architecture principles)**, ensuring database access is completely decoupled from business logic and controllers. It also features distributed background task processing via Celery and Redis, strict API rate limiting, robust error mapping, unified structured JSON logging, distributed OpenTelemetry tracing, and Grafana-monitored metrics.

---

## Table of Contents

- [Architectural Design & Layers](#architectural-design--layers)
- [Enterprise Features & Tech Stack](#enterprise-features--tech-stack)
- [Configuration Guide](#configuration-guide)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [Local Setup (All Platforms)](#local-setup-all-platforms)
- [Running the Application](#running-the-application)
  - [1. Development Mode](#1-development-mode)
  - [2. Production Mode](#2-production-mode)
- [Developer Commands & Makefile Reference](#developer-commands--makefile-reference)
- [API Documentation](#api-documentation)

---

## Architectural Design & Layers

The codebase is structured under the [app/](./app/) directory using a strict layered architecture pattern. Each layer has a distinct responsibility, which isolates changes, guarantees high testability, and maintains thin, declarative endpoint handlers.

```mermaid
graph TD
    Client[Client Request] --> API[API Endpoints / Controllers]
    API --> Services[Business Services Layer]
    Services --> Repositories[Repositories Layer]
    Repositories --> DB[(PostgreSQL Database)]
    Services -.-> Worker[Celery Background Tasks]
    Worker -.-> Redis[(Redis Broker)]
```

### Folder Breakdown and Usage

- **[app/api/](./app/api)** (HTTP Controllers & Routing)
  - *Purpose:* Acts as the interface layer for handling incoming HTTP requests and routing them to the correct service handlers.
  - *Why we need it:* Decouples network communication details (HTTP methods, status codes, headers, parameter binding) from core business logic. Endpoints here are declarative, leaving business rules to the services layer.
  - *Usage:* Contains API routes (organized in versioned subfolders like [v1/endpoints/](./app/api/v1/endpoints)) and global dependency injections (such as authenticated user resolvers in [deps.py](./app/api/deps.py)).

- **[app/services/](./app/services)** (Business Logic Layer)
  - *Purpose:* Encapsulates all domain-specific validation, business rules, transactional orchestrations, and background task dispatches.
  - *Why we need it:* Ensures the core functionality of the application remains database-agnostic and client-agnostic. Multiple entry points (e.g. REST API, Celery worker task, or CLI script) can invoke the same business logic, enforcing a single source of truth.
  - *Usage:* Orchestrates data fetching from repositories, performs computations (e.g., reports generation, password hashing checks), validates domain constraints, and triggers celery tasks.

- **[app/repositories/](./app/repositories)** (Data Access Layer)
  - *Purpose:* Abstract data access logic using the Repository Pattern. All queries (using SQLAlchemy async sessions) are isolated inside repositories.
  - *Why we need it:* Decouples database operations and query building from the business services. If the database engine or ORM syntax changes, only the repositories need to be updated. It also simplifies unit testing by allowing repositories to be mocked.
  - *Usage:* Implements standard CRUD operations and custom complex SQL queries (using async SQLAlchemy select/insert statements) for users, transactions, categories, and audit logs.

- **[app/models/](./app/models)** (Database Entity Definitions)
  - *Purpose:* Defines SQLAlchemy ORM models representing the physical schema of the database.
  - *Why we need it:* Declares tables, database columns, constraints, indices, and relationships between tables.
  - *Usage:* Declares Python classes mapped to database tables (e.g., `User`, `Transaction`, `Category`, `AuditLog`) inheriting from the SQLAlchemy `Base` class.

- **[app/schemas/](./app/schemas)** (Data Parsing & Validation)
  - *Purpose:* Contains Pydantic models for request payload validation and response serialization.
  - *Why we need it:* Ensures incoming request data strictly matches expected formats (deserialization and validation) and guarantees that outbound API data is filtered properly (serialization, hiding passwords, structuring objects).
  - *Usage:* Defines request schemas (e.g., `UserCreate`, `TransactionCreate`) and response models (e.g., `UserResponse`, `TransactionResponse`).

- **[app/core/](./app/core)** (Cross-Cutting Infrastructure)
  - *Purpose:* Holds core system configurations, central settings, security/cryptography mechanisms, caching decorators, custom exceptions, and telemetry setups.
  - *Why we need it:* Provides system-wide utility setups that other layers import, ensuring clean configurations.
  - *Usage:* Contains global settings in [config.py](./app/core/config.py), OpenTelemetry configurations in [tracing.py](./app/core/tracing.py), Redis interfaces in [redis.py](./app/core/redis.py), and rate limiters in [rate_limit.py](./app/core/rate_limit.py).

- **[app/middleware/](./app/middleware)** (HTTP Request Processing Pipeline)
  - *Purpose:* Custom ASGI middlewares running code on incoming requests before they hit endpoints, and on outgoing responses before they return to the client.
  - *Why we need it:* Captures correlation IDs, measures request execution time, injects security headers, and handles structured logs globally.
  - *Usage:* Middlewares for request logging, correlation ID injection, security headers, and execution profiling.

- **[app/worker/](./app/worker)** (Asynchronous Task Queue)
  - *Purpose:* Configures Celery and schedules background/periodic tasks (Celery Beat).
  - *Why we need it:* Offloads time-consuming tasks (sending emails, purging old logs, generating reports) from the request-response thread to background workers, improving API responsiveness.
  - *Usage:* Celery app definitions and background task implementations in [tasks.py](./app/worker/tasks.py).

---

## Enterprise Features & Tech Stack

This project is built using a modern, production-grade python stack showcasing software engineering best practices:

1. **Rust-Powered Execution Server (Granian):** Rather than standard Uvicorn/Gunicorn, SpendWise uses `granian` (ASGI runner written in Rust) for maximum performance, multi-threading, and reduced latency.
2. **Deterministic Dependency Resolution (uv):** Packaged and resolved using Astral's `uv` tool. Ensures extremely fast, reproducible environments via [uv.lock](./uv.lock).
3. **Structured JSON Logging (structlog):** Standardized logging using `structlog`. In production, logs are written in structured JSON formats, enriched with correlation IDs, response times, and HTTP context, making them immediately parseable by ELK, Grafana Loki, or Datadog.
4. **Resilient Rate Limiting (SlowAPI):** Endpoints are secured against abuse using `slowapi`, which provides token-bucket and sliding-window rate limiting backed by Redis.
5. **Robust Caching (fastapi-cache2):** Redis-based cache decorator implementation. High-load endpoints (such as monthly report aggregations) utilize caching to dramatically reduce database query pressure.
6. **Distributed Tracing (OpenTelemetry):** Setup with OpenTelemetry SDKs, offering automatic instrumentations for FastAPI endpoints, Redis operations, SQLAlchemy queries, and outgoing HTTPX requests.
7. **Comprehensive Monitoring & Metrics Dashboard:**
   - Exposes Prometheus-format metrics via `prometheus-fastapi-instrumentator` on the `/metrics` endpoint.
   - Built-in configurations for Prometheus servers and Grafana dashboards inside [docker-compose.monitoring.yml](./docker-compose.monitoring.yml) for visualizing latency percentiles, request counts, and system metrics.
8. **Asynchronous Background Processing (Celery & Celery Beat):** Uses Celery workers to asynchronously handle tasks like sending user verification/reset emails and Celery Beat to execute periodic database audit logs maintenance.
9. **Rigorous Test Suite (Pytest & Factory-Boy):** Fast, async unit and integration testing using `pytest`, `pytest-asyncio`, and `pytest-cov` (configured to enforce a minimum coverage threshold of 85%).
10. **Strict Git Pre-commit Hooks:** Enforces code quality checks on every commit via [.pre-commit-config.yaml](./.pre-commit-config.yaml) running:
    - **Ruff:** Ultra-fast python linter and formatter.
    - **Mypy:** Strict static type checking (`strict = true` in [pyproject.toml](./pyproject.toml)).
    - **Bandit:** Static analysis scanner checking for common security vulnerabilities.
    - **Pip-Audit:** Dependency vulnerability audits.
    - **Gitleaks:** Scans files to prevent committing hardcoded secrets or API tokens.

---

## Configuration Guide

The project uses Pydantic Settings to manage configuration. Environment variables are loaded dynamically from environment files based on the target deployment.

### Available Configuration Files

- `.env` — Main configuration file for running locally.
- `.env.docker` — Configures environment variables suitable for running the API and services containerized inside a Docker bridge network.
- `.env.prod` — Optimized settings, turned off debug modes, and higher pool capacities for production.
- `.env.test` — Database and caching configurations for sandbox test runs (uses a isolated test database and memory/in-memory caches).

### Key Variables Table

| Variable Name | Default / Example Value | Description |
|---|---|---|
| `APP_NAME` | `"SpendWise"` | Name of the FastAPI application. |
| `DEBUG` | `true` | Enables hot reload, interactive Swagger docs, and verbose logging. |
| `DATABASE_URL` | `postgresql+asyncpg://spendwise:password@localhost:5432/spendwise` | Async SQLAlchemy PostgreSQL connection string. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis instance URL for caching and rate limiting. |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Redis broker database for Celery queues. |
| `SECRET_KEY` | `CHANGE_ME_token_hex_string` | Secret hex string used for signing JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `30` | Expiration lifespan of JWT access tokens. |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.mailtrap.io` / `587` | Outbound mail server connection settings (optional). |

---

## Installation & Setup

### Prerequisites

Ensure you have the following installed on your system before proceeding:

- **All Platforms:** [Docker Desktop](https://www.docker.com/) and [uv](https://github.com/astral-sh/uv) (v0.1+).
- **macOS & Linux:** GNU Make (`make` command utility).
- **Windows:** PowerShell v5+ (Make commands are mapped to native PowerShell commands below for Windows users without GNU Make installed).

---

### Local Setup (All Platforms)

#### 1. Clone the repository and enter the directory
```bash
git clone https://github.com/Manan-2805/SpendWise.git
cd SpendWise
```

#### 2. Create the Environment File
Copy the example file to `.env`:
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```
- **Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```

#### 3. Setup Virtual Environment and Install Dependencies
This project uses `uv` for lightning-fast virtual environment management.
- **macOS / Linux:**
  ```bash
  # Creates .venv, syncs dependencies, and configures project
  uv sync --group dev
  ```
- **Windows (PowerShell):**
  ```powershell
  # Creates .venv and syncs dependencies
  uv sync --group dev
  ```

#### 4. Activate the Virtual Environment
- **macOS / Linux:**
  ```bash
  source .venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

#### 5. Install Git Pre-commit Hooks
Register hooks in the git lifecycle so checks run automatically before committing code:
```bash
uv run pre-commit install
```

---

## Running the Application

### 1. Development Mode

#### Natively (Local Machine)
Ensure PostgreSQL and Redis services are running locally and configurations in `.env` are updated correctly. Then run:

```bash
# Run database migrations
uv run alembic upgrade head

# Seed database with sample transactions and categories
uv run python -B scripts/seed_db.py

# Start the development reload server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
```

#### Containerized (Docker Compose)
To spin up all required infrastructure services (PostgreSQL, Redis, Celery, and the API app) with code volumes mounted for hot reloading, execute:

- **macOS / Linux:**
  ```bash
  make up
  ```
- **Windows (PowerShell):**
  ```powershell
  docker compose up -d
  ```

---

### 2. Production Mode

#### Natively (Local Machine)
To run in production mode locally, copy `.env.prod` configurations, load them, and start the high-performance Granian runner:

- **macOS / Linux:**
  ```bash
  uv sync --no-dev
  uv run granian --interface asgi app.main:app --workers 4 --host 0.0.0.0 --port 8000
  ```
- **Windows (PowerShell):**
  ```powershell
  uv sync --no-dev
  uv run granian --interface asgi app.main:app --workers 4 --host 0.0.0.0 --port 8000
  ```

#### Containerized (Docker Compose)
This spins up production-optimized builds using multi-stage builds defined in the production Dockerfile:

- **macOS / Linux:**
  ```bash
  docker compose -f docker-compose.prod.yml up -d --build
  ```
- **Windows (PowerShell):**
  ```powershell
  docker compose -f docker-compose.prod.yml up -d --build
  ```

*Monitoring stack (Prometheus & Grafana) can also be started in parallel:*
```bash
docker compose -f docker-compose.monitoring.yml up -d
```

---

## Developer Commands & Makefile Reference

The project includes a [Makefile](./Makefile) containing shortcuts for daily development workflows. Below is a comprehensive command list with their native PowerShell equivalents for Windows developers:

| Make Command | Native PowerShell Equivalent (Windows) | Description |
|---|---|---|
| `make install` | `uv sync --group dev` | Installs all core and development dependencies. |
| `make install-prod` | `uv sync --no-dev` | Installs production dependencies only. |
| `make dev` | `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app` | Starts the hot-reloading development API server. |
| `make run` | `uv run granian --interface asgi app.main:app --workers 4 --host 0.0.0.0 --port 8000` | Runs the API server inside the Granian ASGI runner (production). |
| `make up` | `docker compose up -d` | Starts the entire development Docker stack in background. |
| `make up-build` | `docker compose up -d --build` | Force rebuilds and starts the development Docker containers. |
| `make down` | `docker compose down` | Stops and removes development Docker containers. |
| `make down-volumes`| `docker compose down -v` | Stops containers and destroys all database volumes. |
| `make logs` | `docker compose logs -f` | Follows logs from all running containers. |
| `make logs-api` | `docker compose logs -f api` | Follows logs from the API container only. |
| `make migrate` | `uv run alembic upgrade head` | Applies all pending database migrations. |
| `make migration name="abc"` | `uv run alembic revision --autogenerate -m "abc"` | Autogenerates a new database migration file. |
| `make rollback` | `uv run alembic downgrade -1` | Rolls back the last applied migration. |
| `make db-reset` | `uv run alembic downgrade base; uv run alembic upgrade head` | Rolls back all migrations and re-runs them from scratch. |
| `make test` | `uv run pytest` | Executes the complete test suite. |
| `make test-unit` | `uv run pytest tests/unit/ -v` | Runs unit tests only with verbose output. |
| `make test-integration`| `uv run pytest tests/integration/ -v` | Runs integration tests only with verbose output. |
| `make test-cov` | `uv run pytest --cov=app --cov-report=html --cov-report=term-missing` | Runs tests, displays terminal coverage, and outputs HTML report. |
| `make lint` | `uv run ruff check alembic/ app/ tests/` | Runs Ruff linter on all python modules. |
| `make lint-fix` | `uv run ruff check --fix alembic/ app/ tests/` | Lints code and auto-fixes resolvable code errors. |
| `make format` | `uv run ruff format alembic/ app/ tests/` | Formats all modules using the Ruff formatter. |
| `make typecheck` | `uv run mypy app/` | Runs Mypy static type checker on the app package. |
| `make security-check`| `uv run bandit -c pyproject.toml -r app/` | Runs Bandit security analysis. |
| `make audit` | `uv run pip-audit` | Audits installed packages for known vulnerabilities. |
| `make check` | *(Runs lint, format-check, typecheck, security-check, audit)* | Sequences all quality assurance checks. |
| `make seed` | `uv run python -B scripts/seed_db.py` | Seeds the database with default categories and transactions. |
| `make create-superuser`| `uv run python -B scripts/create_superuser.py` | Runs interactive CLI script to create an admin user. |
| `make secret` | `uv run python -B -c "import secrets; print(secrets.token_hex(32))"` | Generates a cryptographically secure JWT secret key. |
| `make clean` | `Get-ChildItem -Path . -Filter "__pycache__" -Recurse \| Remove-Item -Force -Recurse` | Cleans up system caches, python objects, and coverage output files. |

---

## API Documentation

Once the backend server is running locally (either via Docker or natively), you can view and test the API endpoints using interactive documentation interfaces at:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs) (Interactive endpoint explorer & testing tool)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc) (Clean, structured static api reference manual)
- **Prometheus Metrics:** [http://localhost:8000/metrics](http://localhost:8000/metrics) (Prometheus metric feeds)
