# ──────────────────────────────────────────────────────────────────
# ThermaSense Dockerfile
# Multi-stage build: builder installs deps, runtime runs the app.
# ──────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

# System deps required for psycopg2, rasterio, shapely
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first (layer caching)
COPY pyproject.toml .
COPY uv.lock* ./

# Install dependencies into /build/.venv
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    libgdal36 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Make the venv's binaries and packages available
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application source
COPY app/ ./app/
COPY alembic.ini ./
COPY .env* ./

EXPOSE 8000

# Default: run the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
