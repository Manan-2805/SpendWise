# Dependency changes
Every package add, upgrade, or removal: package, version, why, approved by me (date).

## 2026-11-22 — Targeted security upgrades

The user approved upgrading dependencies reported by pip-audit and compatibility dependencies. The first scan reported 99 advisory entries across 17 packages. The post-upgrade scan reported no known vulnerabilities in the installed dependencies. The local SpendWise package is outside the advisory feed.

| Package | Previous | Resolved | Reason |
|---|---|---|---|
| `anyio` | 4.13.0 | 4.14.2, 4.16.0 | Security advisory remediation |
| `authlib` | 1.7.2 | 1.9.10 | Security advisory remediation |
| `certifi` | 2026.5.20 | 2026.11.20 | Security advisory remediation |
| `cryptography` | 48.0.0 | 50.0.2 | Security advisory remediation |
| `distlib` | 0.4.0 | 0.4.4 | Compatibility with approved security upgrades |
| `dnspython` | 2.8.0 | 2.9.2 | Security advisory remediation |
| `filelock` | 3.29.0 | 4.3.0 | Security advisory remediation |
| `joserfc` | 1.6.8 | 1.8.0 | Security advisory remediation |
| `msgpack` | 1.1.2 | 1.2.4 | Security advisory remediation |
| `opentelemetry-api` | 1.42.1 | 1.45.2 | Security advisory remediation |
| `opentelemetry-instrumentation` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-asgi` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-fastapi` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-httpx` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-redis` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-instrumentation-sqlalchemy` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-sdk` | 1.42.1 | 1.45.2 | Compatibility with approved security upgrades |
| `opentelemetry-semantic-conventions` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `opentelemetry-util-http` | 0.63b1 | 0.66b2 | Compatibility with approved security upgrades |
| `packaging` | 26.2 | 26.3 | Compatibility with approved security upgrades |
| `pip` | 26.1.2 | 26.3 | Security advisory remediation |
| `pydantic-settings` | 2.14.1 | 2.16.3 | Security advisory remediation |
| `pyjwt` | 2.13.0 | 2.15.1 | Security advisory remediation |
| `python-discovery` | 1.4.0 | 1.9.6 | Compatibility with approved security upgrades |
| `python-multipart` | 0.0.30 | 0.0.34 | Security advisory remediation |
| `starlette` | 1.2.1 | 1.10.0 | Security advisory remediation |
| `tornado` | 6.5.6 | 6.6.1 | Security advisory remediation |
| `urllib3` | 2.7.0 | 2.8.0 | Security advisory remediation |
| `virtualenv` | 21.4.2 | 21.15.12 | Security advisory remediation |
