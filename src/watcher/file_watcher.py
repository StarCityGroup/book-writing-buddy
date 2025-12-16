"""
File watching daemon.

Monitors Zotero and Scrivener directories for changes and
triggers re-indexing automatically.
"""

import time
from pathlib import Path
from typing import Dict, Any, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import structlog

from ..indexer import ZoteroIndexer, ScrivenerIndexer
from ..vectordb.client import VectorDBClient

logger = structlog.get_logger()


class DebounceHandler(FileSystemEventHandler):
    """
    File system event handler with debouncing.

    Waits for file changes to settle before triggering indexing.
    """

    def __init__(
        self,
        callback,
        debounce_seconds: int = 5,
        patterns: Set[str] = None
    ):
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
        self.patterns = patterns or {'*'}
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
        if '*' in self.patterns:
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
        config: Dict[str, Any]
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
            debounce_seconds=config['indexing']['debounce_seconds'],
            patterns={
                '*.pdf',
                '*.html',
                '*.htm',
                '*.txt',
                'zotero.sqlite'
            }
        )

        self.scrivener_handler = DebounceHandler(
            callback=self._handle_scrivener_changes,
            debounce_seconds=config['indexing']['debounce_seconds'],
            patterns={'*.rtf', '*.txt'}
        )

    def start(self):
        """Start watching directories"""
        logger.info("Starting file watcher daemon")

        # Watch Zotero storage directory
        zotero_storage = self.zotero_indexer.storage_path
        if zotero_storage.exists():
            observer = Observer()
            observer.schedule(
                self.zotero_handler,
                str(zotero_storage),
                recursive=True
            )
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching Zotero storage: {zotero_storage}")
        else:
            logger.warning(f"Zotero storage not found: {zotero_storage}")

        # Watch Scrivener Files/Data directory
        scrivener_data = self.scrivener_indexer.files_path
        if scrivener_data.exists():
            observer = Observer()
            observer.schedule(
                self.scrivener_handler,
                str(scrivener_data),
                recursive=True
            )
            observer.start()
            self.observers.append(observer)
            logger.info(f"Watching Scrivener data: {scrivener_data}")
        else:
            logger.warning(f"Scrivener data not found: {scrivener_data}")

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
        logger.info(f"Re-indexing {len(changed_paths)} Scrivener files")

        # Re-index changed documents
        for path in changed_paths:
            try:
                self.scrivener_indexer._index_document(Path(path))
            except Exception as e:
                logger.error(f"Failed to re-index {path}: {e}")

        logger.info("Scrivener re-indexing complete")
