"""
File watching daemon.

Monitors Zotero and Scrivener directories for changes and
triggers re-indexing automatically.
"""

import time
from pathlib import Path
from typing import Any, Dict, Set

import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

from ..indexer import ScrivenerIndexer, ZoteroIndexer

logger = structlog.get_logger()


class DebounceHandler(FileSystemEventHandler):
    """
    File system event handler with debouncing.

    Waits for file changes to settle before triggering indexing.
    """

    def __init__(self, callback, debounce_seconds: int = 5, patterns: Set[str] = None):
        """
        Initialize debounce handler.

        Args:
            callback: Function to call when files change
            debounce_seconds: Seconds to wait after last change
            patterns: File patterns to watch (e.g., {'*.pdf', '*.rtf'})
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.patterns = patterns or {"*"}
        self.pending_changes = {}
        self.last_change_time = {}

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification"""
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Check if file matches patterns
        if not self._matches_pattern(path):
            return

        # Record change
        self.pending_changes[path] = time.time()
        self.last_change_time[path] = time.time()

        logger.debug(f"File changed: {path}")

    def on_created(self, event: FileSystemEvent):
        """Handle file creation"""
        self.on_modified(event)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion"""
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Check if file matches patterns
        if not self._matches_pattern(path):
            return

        # Record deletion
        self.pending_changes[path] = time.time()
        self.last_change_time[path] = time.time()

        logger.debug(f"File deleted: {path}")

    def check_and_process(self):
        """Check for settled changes and process them"""
        current_time = time.time()
        to_process = []

        for path, last_change in list(self.pending_changes.items()):
            if current_time - last_change >= self.debounce_seconds:
                to_process.append(path)
                del self.pending_changes[path]
                if path in self.last_change_time:
                    del self.last_change_time[path]

        if to_process:
            logger.info(f"Processing {len(to_process)} changed files")
            self.callback(to_process)

    def _matches_pattern(self, path: Path) -> bool:
        """Check if path matches any watch pattern"""
        if "*" in self.patterns:
            return True

        for pattern in self.patterns:
            if path.match(pattern):
                return True

        return False


class FileWatcherDaemon:
    """
    Main file watching daemon.

    Monitors both Zotero and Scrivener directories and triggers
    re-indexing when files change.
    """

    def __init__(
        self,
        zotero_indexer: ZoteroIndexer,
        scrivener_indexer: ScrivenerIndexer,
        config: Dict[str, Any],
    ):
        """
        Initialize file watcher daemon.

        Args:
            zotero_indexer: Zotero indexer instance
            scrivener_indexer: Scrivener indexer instance
            config: Configuration dict
        """
        self.zotero_indexer = zotero_indexer
        self.scrivener_indexer = scrivener_indexer
        self.config = config

        self.observers = []

        # Setup handlers
        self.zotero_handler = DebounceHandler(
            callback=self._handle_zotero_changes,
            debounce_seconds=config["indexing"]["debounce_seconds"],
            patterns={"*.pdf", "*.html", "*.htm", "*.txt", "zotero.sqlite"},
        )

        self.scrivener_handler = DebounceHandler(
            callback=self._handle_scrivener_changes,
            debounce_seconds=config["indexing"]["debounce_seconds"],
            patterns={"*.rtf", "*.txt", "*.scrivx"},
        )

    def start(self):
        """Start watching directories"""
        logger.info("Starting file watcher daemon")

        # Watch Zotero storage directory
        zotero_storage = self.zotero_indexer.storage_path
        if zotero_storage.exists():
            observer = Observer()
            observer.schedule(self.zotero_handler, str(zotero_storage), recursive=True)
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching Zotero storage: {zotero_storage}")
        else:
            logger.warning(f"Zotero storage not found: {zotero_storage}")

        # Watch Scrivener Files/Data directory (content files)
        scrivener_data = self.scrivener_indexer.files_path
        if scrivener_data.exists():
            observer = Observer()
            observer.schedule(
                self.scrivener_handler, str(scrivener_data), recursive=True
            )
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching Scrivener data: {scrivener_data}")
        else:
            logger.warning(f"Scrivener data not found: {scrivener_data}")

        # Watch Scrivener root directory (for .scrivx structure file changes)
        scrivener_root = self.scrivener_indexer.scrivener_path
        if scrivener_root.exists():
            observer = Observer()
            observer.schedule(
                self.scrivener_handler, str(scrivener_root), recursive=False
            )
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching Scrivener root: {scrivener_root}")
        else:
            logger.warning(f"Scrivener root not found: {scrivener_root}")

        # Run debounce check loop
        try:
            while True:
                time.sleep(1)
                self.zotero_handler.check_and_process()
                self.scrivener_handler.check_and_process()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop watching directories"""
        logger.info("Stopping file watcher daemon")
        for observer in self.observers:
            observer.stop()
            observer.join()

    def _handle_zotero_changes(self, changed_paths: list):
        """Handle Zotero file changes"""
        logger.info(f"Re-indexing {len(changed_paths)} Zotero files")

        # For simplicity, re-index all collections
        # A more sophisticated approach would map files to collections
        try:
            self.zotero_indexer.index_all()
            logger.info("Zotero re-indexing complete")
        except Exception as e:
            logger.error(f"Zotero re-indexing failed: {e}")

    def _handle_scrivener_changes(self, changed_paths: list):
        """Handle Scrivener file changes"""
        logger.info(f"Processing {len(changed_paths)} Scrivener file changes")

        # Check if .scrivx structure file changed
        scrivx_changed = any(str(path).endswith(".scrivx") for path in changed_paths)

        # Check if any files were deleted (they won't exist anymore)
        has_deletions = any(not Path(path).exists() for path in changed_paths)

        if scrivx_changed or has_deletions:
            # Structure changed or files deleted - run full sync to detect moves/deletions
            if scrivx_changed:
                logger.info(
                    "Scrivener structure file (.scrivx) changed, running full sync"
                )
            if has_deletions:
                logger.info(
                    f"Detected {sum(1 for p in changed_paths if not Path(p).exists())} deleted files, running sync"
                )

            try:
                # Check if sync method exists (added in Phase 5)
                if hasattr(self.scrivener_indexer, "sync"):
                    self.scrivener_indexer.sync()
                else:
                    # Fallback to re-indexing all (less efficient)
                    logger.warning(
                        "Sync method not available, falling back to full re-index"
                    )
                    self.scrivener_indexer.index_all()
            except Exception as e:
                logger.error(f"Failed to sync Scrivener: {e}", exc_info=True)
        else:
            # Only content files changed - reload structure and do fast incremental re-indexing
            logger.info(f"Re-indexing {len(changed_paths)} Scrivener content files")

            # Reload structure to pick up any new documents
            try:
                self.scrivener_indexer.reload_structure()
            except Exception as e:
                logger.warning(f"Failed to reload structure: {e}")

            # Re-index changed files
            for path in changed_paths:
                try:
                    self.scrivener_indexer._index_document(Path(path))
                except Exception as e:
                    logger.error(f"Failed to re-index {path}: {e}")

        logger.info("Scrivener change handling complete")
