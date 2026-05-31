# Second Opinion MCP Server - Dockerfile
# Multi-stage build using uv for dependency management

FROM python:3.11.15-slim@sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0 AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.17@sha256:03bdc89bb9798628846e60c3a9ad19006c8c3c724ccd2985a33145c039a0577b /uv /usr/local/bin/uv

# Set working directory
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

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app && \
    chown -R mcpuser:mcpuser /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=mcpuser:mcpuser src/config.py src/prompts.py src/sessions.py src/server.py ./
COPY --chown=mcpuser:mcpuser src/tools/ ./tools/
COPY --chown=mcpuser:mcpuser deploy/fetch-secrets.sh ./fetch-secrets.sh
RUN chmod 755 /app/fetch-secrets.sh

# Drop system package-management tooling from the runtime layer; app
# dependencies are prebuilt into /app/.venv.
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel

# Switch to non-root user
USER mcpuser

# Use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/')" || exit 1

# Expose SSE port
EXPOSE 8080

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
