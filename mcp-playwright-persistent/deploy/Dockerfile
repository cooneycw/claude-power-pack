# Playwright Persistent MCP Server - Dockerfile
# Multi-stage build using uv for dependency management

FROM python:3.11.15-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.17@sha256:03bdc89bb9798628846e60c3a9ad19006c8c3c724ccd2985a33145c039a0577b /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Final stage
FROM python:3.11.15-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install Playwright system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
        libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        libwayland-client0 fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app && \
    chown -R mcpuser:mcpuser /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Install Playwright browsers as mcpuser
USER mcpuser
RUN playwright install chromium

# Drop system package-management tooling from the runtime layer; app
# dependencies are prebuilt into /app/.venv.
USER root
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel
USER mcpuser

# Copy application code
COPY --chown=mcpuser:mcpuser src/server.py ./

# Expose SSE port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/')" || exit 1

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
