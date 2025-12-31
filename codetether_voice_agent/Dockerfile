FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (much smaller than full PyTorch with CUDA)
# CPU-only torch is ~200MB vs ~2GB with CUDA
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Clean up build dependencies to reduce image size
RUN apt-get purge -y gcc g++ build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /root/.cache/pip

ENV PYTHONUNBUFFERED=1
ENV LIVEKIT_LOG_LEVEL=info
ENV PYTHONPATH=/app

EXPOSE 8080

# Run the agent directly
CMD ["python", "agent.py"]
