# AI change log
Every change made by an AI agent: file, what, why. Newest session first.

## 2026-11-23 — `codex/20261123-frontend`

Step 0 · Discover and document the API contract for the SpendWise frontend.

| File | What changed | Why |
|---|---|---|
| `Makefile` | Added `make openapi` to call `app.openapi()` with isolated placeholder settings and write sorted JSON | Export a repeatable schema without starting services or reading project environment files |
| `docs/openapi.json` | Recorded the canonical OpenAPI 3.1 export | Provide the input for future client generation |
| `docs/api-contract.md` | Documented browser auth, data shapes, runtime errors, and screen coverage with the verified proxy and email behavior | Give the frontend runtime details missing from the generated schema |
| `docs/CHANGELOG_AI.md` | Recorded the contract discovery changes | Track the files and reasons for this session |

The export uses the FastAPI schema method and runs with uv environment sync disabled. The production origin note follows the pinned Granian 2.7.5 runtime probe and Granian's documented proxy behavior. Docker Compose was run with its default environment-file loading disabled. [FastAPI schema generation](https://fastapi.tiangolo.com/how-to/extending-openapi/) · [uv CLI options](https://docs.astral.sh/uv/reference/cli/#uv-run--no-sync) · [Granian proxy handling](https://github.com/emmett-framework/granian/blob/master/README.md#proxies-and-forwarded-headers) · [Compose environment-file handling](https://docs.docker.com/compose/how-tos/environment-variables/envvars/#compose_disable_env_file)

### Step 1 · Research and origin allowlist regression

| File | What changed | Why |
|---|---|---|
| `tests/integration/test_api/test_persistence.py` | Tested an allowed HTTPS origin and a foreign HTTPS origin with a configured cookie origin allowlist | Verify the approved production configuration accepts only the expected origin in this deployment case |
| `docs/api-contract.md` | Documented deploy-time origin configuration, nginx Host forwarding, the Granian wrapper alternative, and the two follow-ups | Record the deployment decision and preserve deferred work |
| `docs/CHANGELOG_AI.md` | Recorded the regression test and documentation updates | Track Step 1 changes |

Forwarded-header behavior was checked against the installed Granian 2.7.5 wrapper and the upstream docs. [Granian proxy handling](https://github.com/emmett-framework/granian/blob/master/README.md#proxies-and-forwarded-headers) · [nginx proxy headers](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)

### Step 2 · Design brief

| File | What changed | Why |
|---|---|---|
| `frontend/design-preview.html` | Added a standalone dashboard, form and toast sample with three OKLCH palettes, two themes, embedded Fontsource preview subsets and three SVG marks | Compare the visual directions, typography, and icon choices offline before scaffolding |
| `frontend/check-palette-contrast.mjs` | Added dependency-free contrast measurements for five roles on both surfaces in each theme | Verify the actual preview tokens against WCAG AA and reject out-of-sRGB values |
| `docs/CHANGELOG_AI.md` | Recorded the design deliverables and compatibility checks | Track Step 2 changes and sources |

Contrast uses CSS Color 4 conversion and WCAG 2.2 thresholds. The preview uses an opaque glass fallback and embeds SIL Open Font License subsets. Application font packages await Step 3 approval. A disposable plain SMTP listener on port 1025 accepted the existing worker's verification email with `SMTP_STARTTLS=false` and an empty `SMTP_USERNAME`. Mailpit and backend configuration work are deferred to integration. [CSS Color 4](https://www.w3.org/TR/css-color-4/#color-conversion-code) · [WCAG text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) · [Reduced transparency](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-transparency) · [Fontsource](https://fontsource.org/docs/getting-started/cdn) · [Mailpit SMTP](https://mailpit.axllent.org/docs/configuration/smtp/)

## 2026-11-23 — `codex/20261123-overload-and-readme`

Measure API capacity, add overload protection, and update the README. Prepare a Make-only local setup for the API and monitoring.

| File | What changed | Why |
|---|---|---|
| `.gitignore` | Ignored `.env.monitoring` | Keep local Grafana credentials out of Git |
| `Makefile` | Wired installation, local Granian and monitoring startup. Added monitoring health, stop, isolated capacity seed and capacity database commands. Show failed API probe payloads. | Run, seed and diagnose the local stack with Make |
| `alembic.ini` | Add the checkout directory to the migration import path | Run migrations from the production image's uninstalled application source |
| `docker-compose.monitoring.yml` | Disabled the API image's HTTP probe for Celery | Use process status as the Celery startup signal |
| `docker-compose.yml` | Made the local application Dockerfile selectable | Reuse the production runtime image for local monitoring |
| `docs/plans/2026-11-23-overload.md` | Recorded acceptance targets, the session baseline, and a staged test-first plan | Review the overload changes before implementation |
| `scripts/capacity_observability.py` | Collect per-worker SQL, checkout, Redis and bcrypt timings on the benchmark process | Locate stalls through benchmark instrumentation |
| `scripts/run_capacity_test.py` | Added open-loop scheduling, health probes, per-process CPU and database container sampling. Clean up benchmark worker processes between rounds. | Reproduce the mixed workload and distinguish client scheduling limits from API behavior |
| `scripts/seed_load_test_db.py` | Added a deterministic capacity dataset, batched inserts and count validation | Reproduce and verify the required cardinality |
| `scripts/setup_dev.py` | Generate a private Grafana env file once | Support fresh installs and preserve the existing Grafana credential on restart |
| `tests/integration/test_seed_load.py` | Verify dataset ratios, an idempotent rerun and rejection of incomplete fixtures against PostgreSQL | Catch seed drift and duplicate data |
| `tests/unit/test_run_capacity_test.py` | Verify the workload mix, transaction payload, CPU output parsing and worker cleanup | Keep runs comparable and prevent benchmark workers from carrying load into the next round |
| `tests/unit/test_setup_dev.py` | Verify Grafana settings permissions and preservation | Catch credential exposure and inadvertent rotation |
| `docs/CHANGELOG_AI.md` | Recorded the local tooling work | Track changes for the session |

Compose layers the local application and Grafana settings files. [Docker Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/#substitute-with---env-file)

The migration configuration uses `prepend_sys_path` and `path_separator`. [Alembic configuration tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

Benchmark queue timing follows the SQLAlchemy implementation pinned in `uv.lock`. [SQLAlchemy 2.0 connection pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)

The benchmark samples PostgreSQL and Redis container CPU from Docker's live stats stream. [Docker container stats](https://docs.docker.com/reference/cli/docker/container/stats/)

### Task 1 · Disposable capacity database

| File | What changed | Why |
|---|---|---|
| `Makefile`, `docker-compose.capacity.yml` | Use a dedicated capacity project, databases and ports | Keep seed and load writes isolated |
| `scripts/capacity_environment.py` | Check Docker service labels, loopback bindings and PostgreSQL cluster identity | Refuse other servers before writes |
| `scripts/run_capacity_test.py`, `scripts/seed_load_test_db.py` | Verify provenance before capacity migrations, seeding and workload | Enforce the guard at both entry points |
| `tests/unit/test_capacity_environment.py` | Exercise URL refusal and cluster identity matching | Catch unsafe target selection |
| `docs/CHANGELOG_AI.md` | Record isolation and earlier development seed rows | Preserve their disposition |

An early benchmark left synthetic `capacity_user_*` accounts, their categories, and benchmark transactions in the default local development database. Those rows remain there. The new Compose project uses dedicated volumes. [Docker Compose labels](https://docs.docker.com/reference/compose-file/services/#labels) · [PostgreSQL 16 control data functions](https://www.postgresql.org/docs/16/functions-info.html#FUNCTIONS-PG-CONTROLDATA)

### Task 2 · Health probes

| File | What changed | Why |
|---|---|---|
| `app/api/v1/endpoints/health.py` | Exempt health routes from rate limiting and read readiness from the cached snapshot | Serve probes without request-time dependency I/O |
| `app/core/health.py`, `app/main.py` | Refresh readiness in the lifespan with dedicated bounded clients | Report dependency health independently of the request pool |
| `app/core/config.py` | Configure sampling interval, timeout, and snapshot lifetime | Bound dependency checks and expire stale status |
| `tests/integration/test_api/test_health.py` | Test probe exemptions, snapshot transitions, cancellation, and pool isolation | Regress readiness and liveness behavior |
| `docs/CHANGELOG_AI.md` | Record health changes | Track the implementation |

Readiness uses async Redis clients with short timeouts and cancellation. [redis-py async operations](https://redis.io/docs/latest/develop/clients/redis-py/async/)

### Task 3 · PostgreSQL checkout deadline

| File | What changed | Why |
|---|---|---|
| `app/core/config.py`, `app/db/session.py` | Set and validate checkout and retry defaults | Bound the time a request can queue for a connection |
| `app/api/responses.py`, `app/core/exceptions.py`, `app/main.py` | Map pool saturation to a retryable `503` and expose the header to browser clients | Give callers a consistent overload response |
| `tests/integration/test_api/test_persistence.py` | Hold the only connection during a write and retry after the `503` | Check deadline, rollback, and recovery against PostgreSQL |
| `docs/CHANGELOG_AI.md` | Record pool changes | Track the implementation |

SQLAlchemy uses `pool_timeout` for checkout waits and raises its `TimeoutError` when the pool is exhausted. [SQLAlchemy engine configuration](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.pool_timeout) · [SQLAlchemy core exceptions](https://docs.sqlalchemy.org/en/20/core/exceptions.html#sqlalchemy.exc.TimeoutError)

### Task 4 · Login bcrypt and checkout limits

| File | What changed | Why |
|---|---|---|
| `app/api/v1/endpoints/auth.py`, `app/services/auth.py` | Snapshot credentials, end the login read transaction, and recheck credentials under lock before issuing tokens | Release the connection during bcrypt and handle credential changes safely |
| `app/core/config.py` | Set a per-worker verification capacity | Bound CPU use by concurrent login checks |
| `tests/integration/test_api/test_auth.py` | Hold bcrypt open and verify checkout release, saturation, and account races | Exercise the request path against a real pool |
| `tests/unit/test_auth_service.py` | Verify request cancellation retains the slot until hashing finishes | Bound background hashing under disconnects |
| `docs/CHANGELOG_AI.md` | Record login changes | Track the implementation |

### Task 5 · Admission and OpenAPI

| File | What changed | Why |
|---|---|---|
| `app/middleware/overload.py`, `app/main.py` | Limit per-worker in-flight requests ahead of rate limiting and preserve probe paths | Shed excess requests promptly |
| `app/api/responses.py`, `app/api/v1/router.py` | Declare the overload payload, response code, and retry header in OpenAPI | Let generated clients handle overload |
| `app/core/config.py`, `docker-compose.yml`, `docker-compose.prod.yml` | Expose admission, health, login, pool and transport settings | Tune the limits for each deployment |
| `scripts/run_capacity_test.py` | Record rejection p95 and the effective admission setting | Compare the candidate limits |
| `tests/unit/test_overload.py` | Test slot release, health bypass, and OpenAPI | Protect runtime and client behavior |
| `docs/capacity.md` | Record the admission sweep and its issuance limits | Show the basis for selecting a default |
| `docs/plans/2026-11-23-overload.md` | Record the approved sweep, OpenAPI and approval gate updates | Align the staged plan with the approved scope |
| `docs/CHANGELOG_AI.md` | Record admission and schema changes | Track the implementation |

FastAPI merges router responses into the generated schema. [Additional Responses in OpenAPI](https://fastapi.tiangolo.com/advanced/additional-responses/)

### Final 160 req/s check and repository documentation

| File | What changed | Why |
|---|---|---|
| `docs/capacity.md` | Compare the final 160 req/s round with this session's baseline and record the test scope | Show the result with its measurement limits |
| `README.md` | Replace the smoke benchmark with measured capacity, document known limits, and add verified features and an architecture diagram | Explain the API and the measured behavior |
| `AGENTS.md` | Fill the Commands section from existing Make targets | Give contributors the repository's entry points |
| `docs/CHANGELOG_AI.md` | Record the feature evidence and deliberate omissions | Make the documentation claims traceable |

The admission sweep used short 60-second rounds. The API, PostgreSQL, Redis, Celery, and load generator all ran on the same laptop with 4 vCPU and 5.8 GiB RAM. The final round used a fresh disposable database after temporary containers were removed and the development stack was stopped. The named volumes were preserved.

#### Deliberate omissions

- Task 6 Prometheus overload metrics.
- The full before-and-after capacity rerun.
- The 960 req/s round.
- Recovery-time measurement.

#### README feature evidence

- Categories and transactions are implemented in `app/api/v1/endpoints/categories.py` and `app/api/v1/endpoints/transactions.py`. Integration coverage is in `tests/integration/test_api/test_categories.py` and `tests/integration/test_api/test_transactions.py`.
- Reports use `app/services/report.py` and `app/core/cache.py`. Report and cache behaviors are covered in `tests/integration/test_api/test_reports.py` and `tests/unit/test_cache.py`.
- Account flows and email jobs are in `app/api/v1/endpoints/auth.py`, `app/services/auth.py`, and `app/worker/tasks.py`. Coverage is in `tests/integration/test_api/test_auth.py` and `tests/unit/test_worker_tasks.py`.
- Probes, admission, and the retry header are in `app/api/v1/endpoints/health.py`, `app/core/health.py`, `app/middleware/overload.py`, and `app/api/responses.py`. Coverage is in `tests/integration/test_api/test_health.py` and `tests/unit/test_overload.py`.

## 2026-11-22 — `codex/audit-and-fixes`

Resolve the audit's runtime and release findings, verify Make targets, and publish evidence in the README. Google OAuth implementation and licensing were deferred at the user's request.

| File | What changed | Why |
|---|---|---|
| `.dockerignore` | Moved build exclusions to the context root | Keep local credentials and Git metadata out of images |
| `.env.example` | Documented development ports and left the signing key empty | Keep setup instructions consistent with generated settings |
| `.github/workflows/ci.yml` | Added hooks and image build to CI | Gate builds on tests, coverage, lint and security checks |
| `.pre-commit-config.yaml` | Aligned local test and scanner hooks with Make targets | Use isolated test services and shared verification commands |
| `Makefile` | Automated installation, startup, smoke checks, testing, benchmarking and migrations | Make the documented workflows runnable from a fresh checkout |
| `README.md` | Rewrote quick start, API examples, architecture, deployment and checks | Document reproducible commands and measured behavior |
| `alembic/versions/20261122_a8b7e2d1c690_integrity_and_sessions.py` | Added session fields, normalized identities, hashed recovery data and indexed lookups | Enforce integrity and migrate existing data |
| `app/api/deps.py` | Committed successful requests and added cookie-origin and session version checks | Persist writes before success and validate browser authentication |
| `app/api/v1/endpoints/auth.py` | Used configured rate limits, function-scoped sessions and error response cookie clearing | Make auth configuration and revocation effective |
| `app/api/v1/endpoints/categories.py` | Added pagination and function-scoped sessions | Expose additional pages and commit successful writes |
| `app/api/v1/endpoints/health.py` | Bound concurrent readiness probes | Keep dependency failures within the probe timeout |
| `app/api/v1/endpoints/reports.py` | Validated report months and date ranges | Reject invalid or costly queries before doing database work |
| `app/api/v1/endpoints/transactions.py` | Used the commit-before-response session scope | Persist successful financial requests |
| `app/api/v1/endpoints/users.py` | Removed the uninitialized profile cache and shared password change logic | Avoid profile errors and revoke sessions consistently |
| `app/core/cache.py` | Added owner-checked cache locks and Redis failure fallback | Preserve report reads and prevent releasing another writer's lock |
| `app/core/config.py` | Validated production debug, signing key, origins and Redis auth and added delivery settings | Require safe deployment inputs |
| `app/core/logging.py` | Preserved the configured JSON, redaction and trace processors | Emit usable structured application logs |
| `app/core/rate_limit.py` | Read the default limit from settings | Allow deployment-specific request limits |
| `app/core/security.py` | Included session versions in access tokens and unified cookie paths | Support immediate logout and password-change revocation |
| `app/core/tracing.py` | Made console span export opt-in | Keep tracing instrumentation without noisy default output |
| `app/db/session.py` | Added post-commit callbacks and removed query parameter logging | Defer side effects and protect sensitive values |
| `app/main.py` | Sanitized errors, mapped database constraints and handled auth cookies | Return stable client errors without exposing internals |
| `app/middleware/correlation.py` | Canonicalized incoming correlation UUIDs and isolated request context | Protect audit writes and retain useful correlation |
| `app/middleware/security_headers.py` | Applied a scoped docs CSP and auth cache policy | Keep debug docs functional and auth responses uncached |
| `app/models/auth.py` | Mapped refresh-token hash and expiry indexes | Match the migrated lookup and cleanup schema |
| `app/models/category.py` | Mapped active name indexes and shared-category ownership | Mirror database uniqueness and restrict shared access |
| `app/models/transaction.py` | Mapped a partial active transaction paging index | Support stable owner/date ordering |
| `app/models/user.py` | Mapped session version, verification expiry and recovery lookups | Track account security state |
| `app/repositories/auth.py` | Serialized account sessions and retained revoked tokens through expiry | Prevent concurrent rotation forks and preserve reuse detection |
| `app/repositories/category.py` | Used exact name lookups and owner-scoped transaction operations | Avoid pattern matches and cross-user reassignments |
| `app/repositories/transaction.py` | Scoped category joins, escaped search and stabilized ordering | Protect related data and keep page ordering deterministic |
| `app/repositories/user.py` | Matched normalized identities and locked digest lookups | Avoid wildcard matches and concurrent recovery consumption |
| `app/schemas/auth.py` | Shared password strength and UTF-8 byte validation | Keep validation aligned with bcrypt across auth endpoints |
| `app/schemas/category.py` | Validated patches and allowed nullable system ownership in responses | Handle supported data and reject invalid updates |
| `app/schemas/common.py` | Added explicit-null validation helper | Distinguish omitted fields from invalid null patches |
| `app/schemas/report.py` | Allowed an uncategorized breakdown row | Preserve reporting for transactions without a visible category |
| `app/schemas/transaction.py` | Aligned create and patch limits and accepted legacy nullable response fields | Avoid invalid writes and response failures |
| `app/schemas/user.py` | Validated profile patch fields | Reject invalid null and username updates |
| `app/services/audit.py` | Serialized dates and preserved decimal precision | Store valid audit JSON for financial changes |
| `app/services/auth.py` | Hardened rotation and recovery and queued email after commit | Prevent stale sessions and exposure of raw recovery values in storage |
| `app/services/category.py` | Validated reassignment and advanced report cache generations | Preserve category integrity and fresh reports |
| `app/services/report.py` | Keyed cached reports by transactional user generation | Invalidate committed data without keyspace scans |
| `app/services/transaction.py` | Validated category assignment and advanced report generations with writes | Keep financial records consistent with report output |
| `app/services/user.py` | Normalized identity edits and reverified changed addresses | Prevent a verified address or existing sessions from carrying over |
| `app/worker/celery_app.py` | Applied separate Redis settings and worker logging context | Honor broker and result configuration |
| `app/worker/tasks.py` | Implemented SMTP delivery and fixed task execution and report scheduling | Keep async clients on one loop and generate correct monthly jobs |
| `docker-compose.monitoring.yml` | Restricted monitoring ports and access and added persistent storage | Protect administration and keep monitoring state |
| `docker-compose.prod.yml` | Required deployment secrets and separated the migration job | Connect to privately provisioned services with scoped roles |
| `docker-compose.test.yml` | Added isolated disposable loopback services | Keep test traffic and schema changes separate from development |
| `docker-compose.yml` | Wired one-time migrations, development worker and loopback services | Support a predictable local startup |
| `docker/.dockerignore` | Relocated exclusions to the root | Match Docker's context discovery |
| `docker/Dockerfile` | Used a non-root runtime and corrected the health probe | Build the runtime image without startup migration races |
| `docker/Dockerfile.dev` | Used a non-root development image with narrow COPY instructions | Avoid embedding local files |
| `docker/entrypoint.sh` | Removed startup migrations and seed behavior | Leave job sequencing to deployment |
| `docker/prometheus/prometheus.yml` | Scraped the API by Compose service name | Reach the development API without a host port hop |
| `docs/AUDIT.md` | Recorded source findings, prior checks and README claim verdicts | Preserve the baseline for these fixes |
| `docs/CHANGELOG_AI.md` | Recorded each change and its reason | Maintain the repository change log |
| `docs/DEPENDENCY_CHANGES.md` | Recorded 29 security and compatibility lockfile changes | Document the versions and user approval |
| `scripts/run_load_test.py` | Replaced forced database recreation with an isolated HTTP benchmark | Get reproducible numbers without destructive setup or new dependencies |
| `scripts/seed_db.py` | Guarded seeding by environment | Prevent running demo data setup in production |
| `scripts/seed_load_test_db.py` | Guarded load seeding by environment and formatted it for lint | Prevent unintended production use |
| `scripts/setup_dev.py` | Generated a local settings file once with restrictive permissions | Make fresh checkout setup repeatable |
| `tests/conftest.py` | Isolated test settings and shared test data factories | Keep tests independent of developer credentials |
| `tests/integration/conftest.py` | Ran Alembic against disposable services and isolated transactions and rate-limit keys | Exercise the real schema without resetting unrelated services |
| `tests/integration/test_api/test_auth.py` | Checked account-scoped refresh revocation and digested recovery | Verify new auth behavior |
| `tests/integration/test_api/test_persistence.py` | Added independent-session, concurrent refresh, cache and request validation regressions | Catch audit defects through real HTTP entry points |
| `tests/integration/test_base_repository.py` | Moved the real repository CRUD test into the integration suite | Keep unit tests independent of PostgreSQL |
| `tests/unit/test_auth_service.py` | Verified post-commit dispatch, locking and session invalidation | Match and check revised auth contracts |
| `tests/unit/test_base_repository.py` | Moved the test unchanged in purpose to integration | Keep PostgreSQL-backed tests with service fixtures |
| `tests/unit/test_cache.py` | Tested cache fallback, lock ownership and corrupt entries | Cover the revised Redis behavior |
| `tests/unit/test_category_service.py` | Asserted ownership-aware category updates | Verify scoped transaction reassignments |
| `tests/unit/test_config.py` | Added production debug and key rejection checks | Prevent insecure startup settings |
| `tests/unit/test_deps.py` | Asserted successful session commits and set request methods explicitly | Verify session and cookie selection behavior |
| `tests/unit/test_logging.py` | Checked that production setup retains the JSON renderer | Catch logging resets |
| `tests/unit/test_security_headers.py` | Enabled debug explicitly for docs cases and isolated rate limits | Verify headers without depending on local environment or Redis |
| `tests/unit/test_transaction_service.py` | Used async database mocks for mutation tests | Exercise database-backed cache invalidation |
| `tests/unit/test_user_service.py` | Set up the existing profile record for email changes | Exercise the normalized profile update path |
| `tests/unit/test_worker_tasks.py` | Checked worker delivery and returned export data | Test behavior beyond queue configuration |
| `uv.lock` | Applied approved targeted security upgrades | Clear known advisory results for the locked environment |

Version-specific references used for the changes include [FastAPI dependency teardown](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/), [SQLAlchemy 2.0 session semantics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [Redis lock ownership](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/), [Docker build contexts](https://docs.docker.com/build/concepts/context/), and [structlog 25.5.0 defaults](https://github.com/hynek/structlog/blob/25.5.0/src/structlog/stdlib.py#L61-L104).
