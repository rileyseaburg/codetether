# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r a2a && useradd -r -g a2a a2a
RUN chown -R a2a:a2a /app
USER a2a

# Expose the default port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/.well-known/agent-card.json')" || exit 1

# Default command
CMD ["python", "run_server.py", "run", "--host", "0.0.0.0", "--port", "8000"]