FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Playwright and psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (hatch needs to see the package directory)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir -e .

# Install Playwright browsers
RUN python -m playwright install chromium --with-deps

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
