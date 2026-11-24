# SpendWise

[![CI](https://github.com/Manan-2805/SpendWise/actions/workflows/ci.yml/badge.svg)](https://github.com/Manan-2805/SpendWise/actions/workflows/ci.yml)
[![Frontend](https://github.com/Manan-2805/SpendWise/actions/workflows/frontend.yml/badge.svg)](https://github.com/Manan-2805/SpendWise/actions/workflows/frontend.yml)

SpendWise is a personal expense tracker. Record income and expenses, organize them into categories, and review monthly totals and category breakdowns. The responsive web app supports light and dark themes, keyboard navigation, and reduced motion.

![SpendWise dashboard in light mode](docs/screenshots/frontend/dashboard-light.png)

[Sign in](docs/screenshots/frontend/sign-in.png) · [Dark dashboard](docs/screenshots/frontend/dashboard-dark.png) · [Categories](docs/screenshots/frontend/categories.png) · [Mobile transactions](docs/screenshots/frontend/transactions-mobile.png)

## Run locally with Docker

Use Docker with Compose, GNU Make, and Python 3 for local settings generation.

```sh
git clone https://github.com/Manan-2805/SpendWise.git
cd SpendWise
python3 scripts/setup_dev.py
make up-build
make seed
make smoke
```

Open [SpendWise](http://localhost:3000) and sign in with the demo account printed by the first seed run, or create your own account. Compose runs nginx, FastAPI, Celery, PostgreSQL, Redis, and Mailpit. The migration container applies Alembic changes before the API starts. Rerun `make up-build` after changing frontend files.

## Verify an email address

The Docker development stack sends mail to [Mailpit](http://localhost:8025). Mailpit captures mail locally, including mail addressed to a real email address. Sign up or select **Send verification email**, open the message in Mailpit, and follow the link back to SpendWise.

For delivery to a real inbox, set the Docker development overrides in the ignored local `.env`. Use `SPENDWISE_DEV_SMTP_HOST`, `SPENDWISE_DEV_SMTP_PORT`, `SPENDWISE_DEV_SMTP_FROM`, `SPENDWISE_DEV_SMTP_USERNAME`, `SPENDWISE_DEV_SMTP_PASSWORD`, and `SPENDWISE_DEV_SMTP_STARTTLS=true`. Choose a sender approved by your provider. Set `SPENDWISE_DEV_FRONTEND_URL` to the URL recipients can reach and rerun `make up`. A successful explicit send confirms that the relay accepted the message. Inbox delivery depends on the provider and recipient.

## Development checks

```sh
make install
make frontend-install
make check
make frontend-check
```

The backend suite starts disposable PostgreSQL and Redis and enforces 85% line coverage. Frontend checks cover lint, type checking, Vitest, production build, contrast, and bundle budgets. With Playwright Chromium and its dependencies available, `make frontend-e2e` exercises the browser flow against disposable services.

To run the browser tests against the running Docker app, use `SPENDWISE_E2E_BASE_URL=http://localhost:3000 npm --prefix frontend exec -- playwright test`.

Regenerate API types with `make openapi` and `npm --prefix frontend run api:generate`.

## Project layout

| Path | Purpose |
|---|---|
| `frontend/` | React app with TanStack Query, React Hook Form, and Radix controls |
| `app/` | FastAPI routes, business rules, SQLAlchemy repositories, and Celery jobs |
| `alembic/` | PostgreSQL migrations |
| `docker/` | API images and optional monitoring resources |
| `docs/` | API contract, restore procedure, and maintenance records |

## Operations

- `make up` starts the Docker app with existing images. `make down` removes the containers and keeps the database volume.
- Production uses private PostgreSQL and Redis, a configured SMTP relay, and HTTPS ingress. Supply the required settings in `docker-compose.prod.yml`, run `make prod-migrate` once with the migration role, then run `make prod-up`.
- See the [API contract](docs/api-contract.md) for authentication and proxy configuration and the [PostgreSQL restore runbook](docs/RESTORE.md) for backup and recovery.
