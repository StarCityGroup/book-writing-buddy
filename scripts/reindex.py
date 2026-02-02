#!/usr/bin/env python3
"""
CLI tool for reindexing vector database sources.

Usage:
    uv run scripts/reindex.py --source zotero    # Reindex only Zotero
    uv run scripts/reindex.py --source scrivener # Reindex only Scrivener
    uv run scripts/reindex.py --source both      # Reindex both (default)
    uv run scripts/reindex.py --source both --force  # Delete and reindex
"""

import argparse
import json
import os
import sys
from pathlib import Path

import structlog

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexer.scrivener_indexer import ScrivenerIndexer
from src.indexer.zotero_indexer import ZoteroIndexer
from src.vectordb.client import VectorDBClient

logger = structlog.get_logger()


def load_config():
    """Load configuration from config files."""
    config_path = Path(__file__).parent.parent / "config" / "default.json"
    with open(config_path) as f:
        config = json.load(f)

    # Try to load local config if it exists
    local_config_path = Path(__file__).parent.parent / "config.local.json"
    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = json.load(f)
            config.update(local_config)

    return config


def reindex_zotero(vectordb, config, force=False):
    """Reindex Zotero library.

    Args:
        vectordb: VectorDBClient instance
        config: Configuration dict
        force: If True, delete existing Zotero data before reindexing
    """
    logger.info("=" * 60)
    logger.info("Reindexing Zotero")
    logger.info("=" * 60)

    # Get paths from environment
    zotero_path = os.getenv("ZOTERO_PATH")
    if not zotero_path:
        logger.error("ZOTERO_PATH environment variable not set")
        return None

    # Delete existing data if force flag is set
    if force:
        logger.info("Force flag set - deleting existing Zotero data...")
        vectordb.delete_by_source("zotero")
        logger.info("✓ Existing Zotero data deleted")

    # Initialize indexer
    zotero_indexer = ZoteroIndexer(
        zotero_path=zotero_path, vectordb=vectordb, config=config
    )

    # Index all collections
    try:
        stats = zotero_indexer.index_all()
        logger.info("=" * 60)
        logger.info("Zotero Reindexing Complete")
        logger.info(f"  Collections indexed: {stats['collections_indexed']}")
        logger.info(f"  Documents indexed:   {stats['documents_indexed']}")
        logger.info(f"  Chunks indexed:      {stats['chunks_indexed']}")
        logger.info("=" * 60)
        return stats
    except Exception as e:
        logger.error(f"Zotero indexing failed: {e}", exc_info=True)
        return None


def reindex_scrivener(vectordb, config, force=False):
    """Reindex Scrivener project.

    Args:
        vectordb: VectorDBClient instance
        config: Configuration dict
        force: If True, delete existing Scrivener data before reindexing
    """
    logger.info("=" * 60)
    logger.info("Reindexing Scrivener")
    logger.info("=" * 60)

    # Get paths from environment
    scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
    if not scrivener_path:
        logger.error("SCRIVENER_PROJECT_PATH environment variable not set")
        return None

    scrivener_manuscript_folder = os.getenv("SCRIVENER_MANUSCRIPT_FOLDER", "")

    # Delete existing data if force flag is set
    if force:
        logger.info("Force flag set - deleting existing Scrivener data...")
        vectordb.delete_by_source("scrivener")
        logger.info("✓ Existing Scrivener data deleted")

    # Initialize indexer
    scrivener_indexer = ScrivenerIndexer(
        scrivener_path=scrivener_path,
        vectordb=vectordb,
        config=config,
        manuscript_folder=scrivener_manuscript_folder or None,
    )

    # Index all documents
    try:
        stats = scrivener_indexer.index_all(use_sync=False)
        logger.info("=" * 60)
        logger.info("Scrivener Reindexing Complete")
        logger.info(f"  Documents indexed: {stats['documents_indexed']}")
        logger.info(f"  Chunks indexed:    {stats['chunks_indexed']}")
        logger.info("=" * 60)
        return stats
    except Exception as e:
        logger.error(f"Scrivener indexing failed: {e}", exc_info=True)
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reindex vector database sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reindex only Zotero (keeps Scrivener data)
  uv run scripts/reindex.py --source zotero

  # Reindex only Scrivener (keeps Zotero data)
  uv run scripts/reindex.py --source scrivener

  # Reindex both sources
  uv run scripts/reindex.py --source both

  # Force reindex (delete existing data first)
  uv run scripts/reindex.py --source zotero --force
        """,
    )

    parser.add_argument(
        "--source",
        choices=["zotero", "scrivener", "both"],
        default="both",
        help="Which source(s) to reindex (default: both)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing data before reindexing (use with caution!)",
    )

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Get Qdrant URL from environment
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

    logger.info(f"Qdrant URL: {qdrant_url}")
    logger.info(f"Source: {args.source}")
    logger.info(f"Force delete: {args.force}")
    logger.info("")

    # Warn about force flag
    if args.force:
        logger.warning("⚠️  WARNING: Force flag is set!")
        logger.warning(
            f"⚠️  Existing {args.source} data will be DELETED before reindexing"
        )
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            logger.info("Reindexing cancelled")
            return

    # Initialize vector DB client
    vectordb = VectorDBClient(
        qdrant_url=qdrant_url,
        collection_name=config["vectordb"]["collection_name"],
        embedding_model=config["embedding"]["model"],
        vector_size=config["embedding"]["vector_size"],
    )

    # Get current collection info
    info = vectordb.get_collection_info()
    logger.info(f"Current collection: {info['name']}")
    logger.info(f"Current points count: {info['points_count']}")
    logger.info("")

    # Reindex based on source selection
    results = {}

    if args.source in ["zotero", "both"]:
        results["zotero"] = reindex_zotero(vectordb, config, force=args.force)
        if args.source == "both":
            logger.info("")  # Add spacing between sources

    if args.source in ["scrivener", "both"]:
        results["scrivener"] = reindex_scrivener(vectordb, config, force=args.force)

    # Final summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Reindexing Summary")
    logger.info("=" * 60)

    total_chunks = 0
    for source_name, stats in results.items():
        if stats:
            chunks = stats.get("chunks_indexed", 0)
            total_chunks += chunks
            logger.info(f"{source_name.capitalize()}: {chunks} chunks indexed")
        else:
            logger.warning(f"{source_name.capitalize()}: Failed (see errors above)")

    # Get updated collection info
    final_info = vectordb.get_collection_info()
    logger.info("")
    logger.info(f"Total chunks in collection: {final_info['points_count']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
