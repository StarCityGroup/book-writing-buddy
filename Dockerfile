FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    sqlite3 \
    antiword \
    unrtf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model (cache in image layer)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"

# Copy application code
COPY src/ ./src/
COPY config/default.json ./config/

# Create data directories
RUN mkdir -p /data/vectordb /data/logs

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /data

USER appuser

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app

# Run the MCP server as a module
CMD ["python", "-m", "src.mcp_server"]
