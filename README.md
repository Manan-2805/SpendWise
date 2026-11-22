# SpendWise

[![CI](https://github.com/Manan-2805/SpendWise/actions/workflows/ci.yml/badge.svg)](https://github.com/Manan-2805/SpendWise/actions/workflows/ci.yml) [![Local coverage: 87.23%](https://img.shields.io/badge/local%20coverage-87.23%25-brightgreen)](#tests-and-checks)

SpendWise is a REST API for recording income and expenses and summarizing activity by month or category. It uses FastAPI, PostgreSQL, and Redis. The repository includes database migrations, a Celery worker, and tests.

## Quick start

On Linux or Windows with WSL2, install GNU Make, uv, and Docker with Compose. Run these commands from the repository root.

```sh
git clone https://github.com/Manan-2805/SpendWise.git
cd SpendWise
make install
make dev
```

Open the API at `http://localhost:8000/api/v1/health`. Development uses Uvicorn for reload. `make run` uses the same Granian ASGI server and worker model as the production image. Both targets start local PostgreSQL and Redis and apply migrations. Swagger, ReDoc, and OpenAPI are available when `DEBUG=true` outside production.

## API examples

These examples use a fresh local database. The values shown in the responses are examples. Use the ID returned by the category request and the access token returned by login.

```sh
api=http://localhost:8000/api/v1
curl -fsS "$api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","username":"demo","password":"DemoPass123!","confirm_password":"DemoPass123!"}'

curl -fsS "$api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"DemoPass123!"}'
```

Both endpoints return an access token. For subsequent commands, set `token` to the returned `access_token`.

```json
{"access_token":"<access token>","token_type":"bearer","expires_in":1800}
```

```sh
curl -fsS "$api/categories/" -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' -d '{"name":"Groceries","type":"expense"}'

curl -fsS "$api/transactions/" -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' \
  -d '{"category_id":1,"amount":"24.50","description":"Groceries","transaction_date":"2026-11-20","type":"expense"}'

curl -fsS "$api/reports/monthly-summary?year=2026&month=11" \
  -H "Authorization: Bearer $token"
```

Category creation returns `201 Created` with a category ID, name, and type. The transaction also returns `201 Created`, with the transaction ID, category ID, and amount. For a database with only the sample expense, the report returns these totals.

```json
{"year":2026,"month":11,"income":"0","expense":"24.50","balance":"-24.50"}
```

## Repository map

```text
app/
  api/           Routes and request dependencies
  core/          Settings, authentication, Redis, logging, and tracing
  db/            Sessions and database helpers
  middleware/    Request context, timing, and security headers
  models/        SQLAlchemy mappings
  repositories/  PostgreSQL queries and persistence
  schemas/       HTTP contracts
  services/      Business rules and report caching
  worker/        Celery tasks and schedule
alembic/         Schema migrations
docker/          Image definitions and service provisioning
scripts/         Development and benchmark tools
tests/           Unit, integration, and load tests
```

Repositories centralize ownership filters and PostgreSQL queries. The API computes reports from transaction data and caches recurring queries in Redis. Redis also stores rate-limit counters and supports Celery as a broker and result backend. Beat schedules token maintenance and report generation.

| PostgreSQL tables | Purpose |
|---|---|
| `users` | Accounts and verification state |
| `categories`, `transactions` | User categories and financial entries |
| `refresh_tokens`, `oauth_accounts` | Refresh session history and provider links |
| `audit_logs` | Recorded account and financial events |

Transactions belong to a user and can reference a category. Refresh tokens and provider links also belong to users.

## Tests and checks

```sh
make test
make check
make pre-commit-install
```

Make starts disposable PostgreSQL and Redis on ports 55432 and 56379 for integration tests. `make test-unit` runs without those services. The full suite enforces 85% application line coverage, and CI builds the image after the hooks pass. The local verification on 2026-11-22 passed 164 tests at 87.23% coverage. Ruff, Mypy, Bandit, and pip-audit also passed.

## Performance

A local smoke benchmark on 2026-11-22 used an AMD Ryzen 7 7840HS, four visible logical CPUs, and 5.8 GiB of RAM. Two Granian workers served four concurrent clients for five seconds against 25 seeded transactions. The test alternated transaction listings and a warmed monthly report.

| Scenario | Requests | Requests/s | p95 |
|---|---:|---:|---:|
| Combined | 1,024 | 204.35 | 24.69 ms |
| Transaction listing | 513 | 102.37 | 25.88 ms |
| Cached monthly summary | 511 | 101.97 | 21.51 ms |

All measured requests succeeded. The benchmark raises the rate limit for its disposable API instance. These are local measurements with a small dataset and a warmed cache.

```sh
make benchmark BENCHMARK_ARGS='--seconds 5 --concurrency 4 --transactions 25'
```

## Deployment

Build the production image with `make build` and publish a versioned tag to your registry. Provision PostgreSQL and Redis on private networks. Provide signing and database credentials through the deployment's secret store. Set the `SPENDWISE_*` values required by `docker-compose.prod.yml`, then run `make prod-migrate` once with the migration role before running `make prod-up`. Give the API and worker runtime roles only the access they require.

Run Granian behind HTTPS. Probe `/api/v1/health/live` for liveness and `/api/v1/health/ready` for PostgreSQL, Redis, and broker connectivity. Keep metrics and monitoring on the intended management network.

## Security and operations

- Keep local environment files and credentials out of Git and container builds.
- Production rejects debug mode, placeholder keys, and Redis URLs without authentication. Use a distinct signing key and authenticated Redis roles. Configure SMTP for verification and password-reset delivery.
- `make down` stops the development stack. **`make down-volumes` deletes the development database and Redis data.**
- `make logs` displays container logs. Keep recovery links and tokens out of log output.

## Troubleshooting

| Symptom | Check |
|---|---|
| uv cannot find Python 3.12 | Install the pinned Python version with uv, then rerun `make install`. |
| The API cannot reach its dependencies | Check Docker, then run `make dev-services`. Override `DEV_POSTGRES_PORT` or `DEV_REDIS_PORT` on the Make command if ports 15432 or 16379 are in use. |
| Swagger returns 404 | Set `DEBUG=true` for the development server. |
| Tests cannot connect | Check the disposable test PostgreSQL and Redis services. |
