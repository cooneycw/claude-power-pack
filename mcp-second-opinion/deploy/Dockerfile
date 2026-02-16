# Second Opinion MCP Server - Dockerfile
# Multi-stage build using uv for dependency management

FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev --no-install-project

# Final stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app && \
    chown -R mcpuser:mcpuser /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=mcpuser:mcpuser src/config.py src/prompts.py src/server.py ./

# Switch to non-root user
USER mcpuser

# Use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from config import Config; sys.exit(0 if Config.GEMINI_API_KEY else 1)"

# Expose MCP server (stdio mode, no port needed)
# MCP servers communicate via stdin/stdout

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
