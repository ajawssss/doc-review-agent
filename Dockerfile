FROM public.ecr.aws/docker/library/python:3.11-slim

# AgentCore requires the container to listen on port 8080
EXPOSE 8080

WORKDIR /app

# Install system deps for PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# AgentCore health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping')"

# AgentCore expects the container to start an HTTP server on 8080
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
