FROM python:3.11-slim

WORKDIR /app

# Install system dependencies + Node.js for Claude CLI
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install uv and dependencies
RUN pip install uv
RUN uv sync

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY main.py ./
COPY data/outline.txt ./data/outline.txt

# Copy CLI runner script
COPY run-cli.sh /app/run-cli.sh
RUN chmod +x /app/run-cli.sh

# Create entry point script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Data directory for logs and output
RUN mkdir -p /data/logs /app/output

ENTRYPOINT ["/app/docker-entrypoint.sh"]
