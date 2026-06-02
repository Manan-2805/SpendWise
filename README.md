# SpendWise API

SpendWise is a personal expense tracker API built with Python, FastAPI, and PostgreSQL. It provides a structured backend for managing users, tracking income and expenses, and generating financial reports.

## Features

- **Users** — registration, login, profile management, password change.
- **Categories** — user-owned income/expense categories.
- **Transactions** — the core resource: income and expense records with amount, date, category, description, attachments metadata.
- **Reports** — aggregation endpoints: monthly summary, category breakdown, balance over time, top spending categories.

## Prerequisites

Ensure the following system dependencies are installed:

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) (Extremely fast Python package installer)
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- [GNU Make](https://www.gnu.org/software/make/) (For running developer shortcuts)
- PostgreSQL 16 & Redis 5.0+ (Only if not using Docker)

## Development Workflow

This project includes a comprehensive `Makefile` to simplify common development tasks. Run `make help` to see all available commands.

### 1. Initial Setup

 Clone the repository and navigate to the project root:

```bash
git clone https://github.com/Manan-2805/SpendWise.git
cd SpendWise
```

Create a `.env` file in the project root containing your database URIs, JWT secrets, and Redis broker URLs.

Install all dependencies (this uses `uv` under the hood):

```bash
# Install development and production dependencies
make install
```

Install Git pre-commit hooks to ensure code format/lint checks pass on every commit:

```bash
# Install pre-commit hooks
make pre-commit-install
```

### 2. Database Migrations

Apply the latest database schemas using Alembic:

```bash
make migrate
```

### 3. Running the Application

**Using Docker (Recommended):**

Start the entire stack (API, DB, Redis) in the background:

```bash
make up
```

*(You can tail the logs using `make logs` or `make logs-api`)*

**Running Locally:**

To start the API development server with hot-reload enabled:

```bash
make dev
```

## Testing & Quality

Run the test suite and code quality checks using shortcuts:

```bash
# Run all tests natively
make test

# Generate an HTML coverage report
make test-cov

# Run the Ruff linter
make lint

# Run Bandit security tests
make security-check

# Audit dependencies for known vulnerabilities
make audit

# Run all checks (lint, format, typecheck, security, audit)
make check
```

## API Documentation

Once the server is running, the interactive API documentation defaults can be accessed at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
