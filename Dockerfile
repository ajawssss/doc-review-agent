# -----------------------------------------------------------------------------
# What's in this file:
#   Container definition for the Nathan Webb Doc Review Agent. Produces a
#   minimal Python 3.11 image that runs the FastAPI server on port 8080 —
#   the port Amazon Bedrock AgentCore requires for all agent containers.
#
# Technologies used:
#   - Docker / Amazon ECR base image (python:3.11-slim from ECR Public Gallery)
#   - Uvicorn — ASGI server started at container launch via CMD
#   - gcc — system build dep needed by some Python packages (e.g. uvloop)
#   - AgentCore HEALTHCHECK — Docker polls /ping every 30s; AgentCore will
#     not route traffic until the check passes
#
# Example of what this file does:
#   `docker build -t nathan-webb .` produces a ~200 MB image.
#   `docker run -p 8080:8080 -e AWS_REGION=us-east-1 nathan-webb` starts
#   the server locally. Hitting POST localhost:8080/invocations with a JSON
#   body returns Nathan Webb's document review, identical to the AgentCore
#   hosted version.
# -----------------------------------------------------------------------------

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
