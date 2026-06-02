# docker/Dockerfile
# Production multi-stage build

# ── Stage 1: Builder — install dependencies ──────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install only production dependencies (no dev extras)
# --no-install-project: don't install the project itself yet (source not copied)
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: Production — minimal runtime image ───────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Create a non-root user for security
# Running as root in a container is a security vulnerability
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# Copy the installed virtual environment from builder
# This is the key multi-stage trick — builder has build tools, production does not
COPY --from=builder /app/.venv /app/.venv

# Copy application source with correct ownership
COPY --chown=appuser:appgroup ./app ./app
COPY --chown=appuser:appgroup ./alembic ./alembic
COPY --chown=appuser:appgroup alembic.ini .
COPY --chown=appuser:appgroup docker/entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

# Prevent Python from writing .pyc files (no point in a container)
ENV PYTHONDONTWRITEBYTECODE=1

# Prevent Python from buffering stdout/stderr
# Without this, log output may be lost if the container crashes
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Health check — Docker will restart the container if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

# Worker count formula: (2 × CPU cores) + 1
# For a 2-core container: 5 workers
# Adjust --workers based on your deployment target
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "app.main:app"]
