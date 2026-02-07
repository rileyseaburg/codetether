# Multi-stage build: Builder stage
# NOTE: Distroless `python3-debian12` currently ships Python 3.11 (see image entrypoint).
# Build deps with the same Python minor version so compiled wheels (e.g. pydantic_core) match.
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# Copy application code
COPY . .

# ============================================
# Production stage: Distroless
# ============================================
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /app/deps /app/deps

# Copy application code
COPY --from=builder /app/a2a_server /app/a2a_server
COPY --from=builder /app/run_server.py /app/run_server.py
# NOTE: agent_worker/ (legacy Python worker) is no longer shipped.
# Workers now use the codetether Rust binary in SSE mode (codetether a2a).

# Expose the default port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app:/app/deps
ENV PYTHONUNBUFFERED=1

# Distroless doesn't support HEALTHCHECK - use k8s probes instead

# Default command - distroless uses exec form only
CMD ["run_server.py", "run", "--host", "0.0.0.0", "--port", "8000"]
