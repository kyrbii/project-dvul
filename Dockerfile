FROM python:3.11-slim

WORKDIR /app

# Tell uv to put the virtualenv outside the source directory
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv seamlessly
COPY --from=ghcr.io/astral-sh/uv:0.11.0 /uv /bin/

# Copy config and sync dependencies (avoids building a local package)
COPY pyproject.toml .
# Also copy uv.lock if it was created locally
COPY uv.lock* . 
RUN uv sync --no-install-project

# Copy application
COPY . .
