#!/bin/bash
set -e

echo "Starting Book Research Indexer..."
echo "Qdrant URL: ${QDRANT_URL}"
echo "Zotero Path: ${ZOTERO_PATH}"
echo "Scrivener Path: ${SCRIVENER_PATH}"

# Wait for Qdrant to be ready
echo "Waiting for Qdrant..."
until curl -s "${QDRANT_URL}/healthz" > /dev/null; do
    echo "Qdrant not ready, waiting..."
    sleep 2
done
echo "Qdrant is ready!"

# Run initial indexing
echo "Running initial indexing..."
uv run python -m src.indexer.run_initial_index

# Start file watcher daemon
echo "Starting file watcher daemon..."
exec uv run python -m src.watcher.run_daemon
