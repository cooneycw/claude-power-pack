# Second Opinion MCP Server - Dockerfile
# Multi-stage build for optimized image size

FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY environment.yml* requirements.txt* ./

# Install Python dependencies
# If requirements.txt doesn't exist, create it from environment.yml
RUN if [ -f environment.yml ]; then \
    pip install --no-cache-dir \
        'mcp[cli]>=1.2.0' \
        'fastmcp>=1.0' \
        'google-generativeai>=0.3.0' \
        'tenacity>=8.0.0' \
        'pydantic>=2.0.0' \
        'httpx>=0.24.0'; \
    elif [ -f requirements.txt ]; then \
    pip install --no-cache-dir -r requirements.txt; \
    fi

# Final stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app && \
    chown -R mcpuser:mcpuser /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code (from src/ directory)
COPY --chown=mcpuser:mcpuser src/config.py src/prompts.py src/server.py ./

# Switch to non-root user
USER mcpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from config import Config; sys.exit(0 if Config.GEMINI_API_KEY else 1)"

# Expose MCP server (stdio mode, no port needed)
# MCP servers communicate via stdin/stdout

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
