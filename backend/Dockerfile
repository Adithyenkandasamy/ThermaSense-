FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY alembic.ini ./

EXPOSE 8000

# Default: run the API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
