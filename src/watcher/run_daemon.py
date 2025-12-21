#!/usr/bin/env python3
"""Run the file watcher daemon."""

import json
import os
from pathlib import Path

import structlog

from ..indexer.scrivener_indexer import ScrivenerIndexer
from ..indexer.zotero_indexer import ZoteroIndexer
from ..vectordb.client import VectorDBClient
from .file_watcher import FileWatcherDaemon

logger = structlog.get_logger()


def load_config():
    """Load configuration from config files."""
    config_path = Path(__file__).parent.parent.parent / "config" / "default.json"
    with open(config_path) as f:
        config = json.load(f)

    # Try to load local config if it exists
    local_config_path = Path(__file__).parent.parent.parent / "config.local.json"
    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = json.load(f)
            config.update(local_config)

    return config


def main():
    """Main entry point."""
    logger.info("Starting file watcher daemon")

    # Load config
    config = load_config()

    # Get paths from environment
    zotero_path = os.getenv("ZOTERO_PATH", "/mnt/zotero")
    scrivener_path = os.getenv("SCRIVENER_PATH", "/mnt/scrivener")
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")

    # Initialize vector DB client
    vectordb = VectorDBClient(
        qdrant_url=qdrant_url,
        collection_name=config["vectordb"]["collection_name"],
        embedding_model=config["embedding"]["model"],
        vector_size=config["embedding"]["vector_size"],
    )

    # Initialize indexers
    zotero_indexer = ZoteroIndexer(
        zotero_path=zotero_path, vectordb=vectordb, config=config
    )

    scrivener_indexer = ScrivenerIndexer(
        scrivener_path=scrivener_path, vectordb=vectordb, config=config
    )

    # Create and start watcher
    watcher = FileWatcherDaemon(
        zotero_indexer=zotero_indexer,
        scrivener_indexer=scrivener_indexer,
        config=config,
    )

    watcher.start()


if __name__ == "__main__":
    main()
