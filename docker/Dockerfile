# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: Builder
# Installs build tools and Python dependencies into an isolated virtualenv.
# This stage is discarded in the final image, so compilers/headers never
# ship to production.
# =============================================================================
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files and buffering stdout/stderr —
# buffering can delay log output in containers, which hurts debuggability.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System build dependencies:
# - build-essential: gcc/make, needed to compile C extensions (e.g. psycopg2, some SQLAlchemy deps)
# - libpq-dev: Postgres client headers, required to build psycopg2 from source
# These are ONLY in the builder stage and never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtualenv rather than installing into system Python.
# This lets us copy just /opt/venv into the runtime stage — a clean,
# self-contained dependency set with no build tool residue.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy only dependency manifests first (not the whole app) so Docker's layer
# cache is reused whenever app code changes but dependencies don't —
# this is the single biggest lever for fast rebuilds.
COPY pyproject.toml README.md ./

# Install production dependencies only (no dev/test tooling) directly from
# pyproject.toml. We create an empty app/ package stub so pip's build
# backend (hatchling) can resolve the project metadata without the full source.
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir .

# =============================================================================
# Stage 2: Runtime
# Minimal image that only contains the Python interpreter, the pre-built
# virtualenv, and application source — no compilers, no package indexes.
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Runtime-only system dependency:
# - libpq5: the Postgres client *library* (not the -dev headers) needed at
#   runtime by psycopg2, without pulling in build-essential.
# - curl: used by the container HEALTHCHECK to hit our /health endpoint.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user. Running containers as root is a well-known
# security anti-pattern (a container breakout as root is far worse than
# one as an unprivileged user).
RUN groupadd --gid 1000 phoenix && \
    useradd --uid 1000 --gid phoenix --shell /bin/bash --create-home phoenix

# Bring in the pre-built virtualenv from the builder stage — no pip install
# happens in this stage at all.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application source last, since this changes most frequently — keeping
# it as the final layer maximizes cache reuse for everything above it.
COPY --chown=phoenix:phoenix app ./app
COPY --chown=phoenix:phoenix alembic ./alembic
COPY --chown=phoenix:phoenix alembic.ini ./alembic.ini

# Directory for rotating log files (mounted as a volume in docker-compose).
# Created and owned by the app user ahead of time so the app doesn't need
# root privileges to write to it at runtime.
RUN mkdir -p /app/logs && chown -R phoenix:phoenix /app/logs

USER phoenix

EXPOSE 8000

# Docker/Compose-level health check hitting our own /health endpoint (Step 8).
# --start-period gives the app time to boot and connect to Postgres/Redis/Qdrant
# before failed checks count against it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# No shell form, no reload flag (reload is a dev-only feature and adds
# overhead + file-watching that has no place in a production image).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
