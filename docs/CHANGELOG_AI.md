# AI change log
Every change made by an AI agent: file, what, why. Newest session first.

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
