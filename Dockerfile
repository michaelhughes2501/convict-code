# Multi-stage Dockerfile for Python Flask app (ConvictCode)
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy app code
COPY --chown=appuser:appuser . .

# Create non-root user
RUN useradd -m -u 1001 appuser

USER appuser

# Environment variables
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    FLASK_DEBUG=0

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/resources', timeout=2)"

EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "sync", "--timeout", "60", "app:app"]
