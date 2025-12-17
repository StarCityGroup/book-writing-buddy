#!/usr/bin/env python3
"""Run initial indexing of Zotero and Scrivener content."""

import json
import os
import sys
from pathlib import Path

import structlog

from ..vectordb.client import VectorDBClient
from .zotero_indexer import ZoteroIndexer
from .scrivener_indexer import ScrivenerIndexer

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
    logger.info("Starting initial indexing")

    # Load config
    config = load_config()

    # Get paths from environment
    zotero_path = os.getenv("ZOTERO_PATH", "/mnt/zotero")
    scrivener_path = os.getenv("SCRIVENER_PATH", "/mnt/scrivener")
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")

    logger.info(f"Zotero path: {zotero_path}")
    logger.info(f"Scrivener path: {scrivener_path}")
    logger.info(f"Qdrant URL: {qdrant_url}")

    # Initialize vector DB client
    vectordb = VectorDBClient(
        qdrant_url=qdrant_url,
        collection_name=config["vectordb"]["collection_name"],
        embedding_model=config["embedding"]["model"],
        vector_size=config["embedding"]["vector_size"]
    )

    # Check if already indexed
    info = vectordb.get_collection_info()
    if info["points_count"] > 0:
        logger.info(f"Collection already has {info['points_count']} points, skipping initial index")
        return

    # Index Zotero
    logger.info("Indexing Zotero library...")
    zotero_indexer = ZoteroIndexer(
        zotero_path=zotero_path,
        vectordb=vectordb,
        config=config
    )

    try:
        zotero_count = zotero_indexer.index_all()
        logger.info(f"Indexed {zotero_count} Zotero chunks")
    except Exception as e:
        logger.error(f"Zotero indexing failed: {e}")

    # Index Scrivener
    logger.info("Indexing Scrivener project...")
    scrivener_indexer = ScrivenerIndexer(
        scrivener_path=scrivener_path,
        vectordb=vectordb,
        config=config
    )

    try:
        scrivener_count = scrivener_indexer.index_all()
        logger.info(f"Indexed {scrivener_count} Scrivener chunks")
    except Exception as e:
        logger.error(f"Scrivener indexing failed: {e}")

    logger.info("Initial indexing complete")


if __name__ == "__main__":
    main()
