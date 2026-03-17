"""
Scheduled reindexing daemon.

Runs scheduled reindexing of Zotero and Scrivener on fixed intervals:
- Zotero: Once per day
- Scrivener: Once per hour

Missed runs are skipped (no catch-up).
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import structlog

from ..indexer import ScrivenerIndexer, ZoteroIndexer

logger = structlog.get_logger()


class FileWatcherDaemon:
    """
    Scheduled reindexing daemon.

    Runs on fixed schedules:
    - Zotero: Once per day (24 hours)
    - Scrivener: Once per hour

    Missed runs are skipped (no catch-up).
    """

    # Reindexing intervals
    ZOTERO_INTERVAL = timedelta(hours=24)  # Once per day
    SCRIVENER_INTERVAL = timedelta(hours=1)  # Once per hour
    CHECK_INTERVAL = 300  # Check every 5 minutes (in seconds)

    def __init__(
        self,
        zotero_indexer: ZoteroIndexer,
        scrivener_indexer: ScrivenerIndexer,
        config: Dict[str, Any],
    ):
        """
        Initialize scheduled reindexing daemon.

        Args:
            zotero_indexer: Zotero indexer instance
            scrivener_indexer: Scrivener indexer instance
            config: Configuration dict
        """
        self.zotero_indexer = zotero_indexer
        self.scrivener_indexer = scrivener_indexer
        self.config = config

        # Track last successful run times
        self.last_zotero_reindex: Optional[datetime] = None
        self.last_scrivener_reindex: Optional[datetime] = None

    def start(self):
        """Start scheduled reindexing loop"""
        logger.info("Starting scheduled reindexing daemon")
        logger.info(f"Zotero: reindex every {self.ZOTERO_INTERVAL}")
        logger.info(f"Scrivener: reindex every {self.SCRIVENER_INTERVAL}")
        logger.info(f"Checking every {self.CHECK_INTERVAL} seconds")

        try:
            while True:
                now = datetime.now()

                # Check if it's time to reindex Zotero
                if self._should_reindex_zotero(now):
                    self._reindex_zotero()
                    self.last_zotero_reindex = now

                # Check if it's time to reindex Scrivener
                if self._should_reindex_scrivener(now):
                    self._reindex_scrivener()
                    self.last_scrivener_reindex = now

                # Sleep until next check
                time.sleep(self.CHECK_INTERVAL)

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the daemon"""
        logger.info("Stopping scheduled reindexing daemon")

    def _should_reindex_zotero(self, now: datetime) -> bool:
        """Check if it's time to reindex Zotero"""
        if self.last_zotero_reindex is None:
            return True  # Never run before

        elapsed = now - self.last_zotero_reindex
        return elapsed >= self.ZOTERO_INTERVAL

    def _should_reindex_scrivener(self, now: datetime) -> bool:
        """Check if it's time to reindex Scrivener"""
        if self.last_scrivener_reindex is None:
            return True  # Never run before

        elapsed = now - self.last_scrivener_reindex
        return elapsed >= self.SCRIVENER_INTERVAL

    def _reindex_zotero(self):
        """Reindex Zotero collections"""
        logger.info("Starting scheduled Zotero reindex")

        try:
            self.zotero_indexer.index_all()
            logger.info("Zotero reindex complete")
        except Exception as e:
            logger.error(f"Zotero reindex failed: {e}", exc_info=True)

    def _reindex_scrivener(self):
        """Reindex Scrivener documents"""
        logger.info("Starting scheduled Scrivener reindex")

        try:
            # Use sync if available (more efficient)
            if hasattr(self.scrivener_indexer, "sync"):
                self.scrivener_indexer.sync()
            else:
                self.scrivener_indexer.index_all()

            logger.info("Scrivener reindex complete")
        except Exception as e:
            logger.error(f"Scrivener reindex failed: {e}", exc_info=True)
