FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install uv and dependencies
RUN pip install uv
RUN uv sync

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create entry point script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Data directory for logs
RUN mkdir -p /data/logs

ENTRYPOINT ["/app/docker-entrypoint.sh"]
