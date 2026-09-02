# ==============================================================================
# QR ATTENDANCE ERP SYSTEM V2.0 - DOCKERFILE
# Multi-stage optimized production container
# ==============================================================================

FROM python:3.13-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies for PostgreSQL and ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . /app

# Ensure storage directories exist
RUN mkdir -p /app/instance /app/app/static/uploads

# Environment settings
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

EXPOSE 5000

# Run migrations and start Gunicorn server
CMD ["sh", "-c", "python run.py init-db && gunicorn run:app --workers 4 --bind 0.0.0.0:$PORT --access-logfile - --error-logfile -"]
