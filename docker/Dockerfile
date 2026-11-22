FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS production
WORKDIR /app
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser \
    && install -d -o appuser -g appgroup /var/lib/spendwise
COPY --from=builder /app/.venv /app/.venv
COPY app app
COPY alembic alembic
COPY alembic.ini .
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:8000' + os.getenv('API_V1_PREFIX', '/api/v1') + '/health/live', timeout=3)"
EXPOSE 8000
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "app.main:app"]
