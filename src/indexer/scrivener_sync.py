"""
Scrivener sync detector - identifies changes between filesystem and vector DB.

Handles document additions, modifications, deletions, and moves.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import structlog

from ..scrivener_parser import ScrivenerParser
from ..vectordb.client import VectorDBClient
from .scrivener_indexer import ScrivenerIndexer

logger = structlog.get_logger()


@dataclass
class DocumentInfo:
    """Information about a Scrivener document"""

    scrivener_id: str
    file_path: str
    chapter_number: Optional[int]
    chapter_title: Optional[str]
    content_hash: Optional[str] = None
    file_mtime: Optional[float] = None
    doc_type: Optional[str] = None


@dataclass
class DocumentChange:
    """Represents a single document change"""

    scrivener_id: str
    change_type: str  # 'new', 'modified', 'deleted', 'moved'
    file_path: str
    old_chapter: Optional[int] = None
    new_chapter: Optional[int] = None
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None


@dataclass
class ChangeSet:
    """Collection of all detected changes"""

    new: List[DocumentChange] = field(default_factory=list)
    modified: List[DocumentChange] = field(default_factory=list)
    deleted: List[DocumentChange] = field(default_factory=list)
    moved: List[DocumentChange] = field(default_factory=list)

    def total(self) -> int:
        """Total number of changes"""
        return len(self.new) + len(self.modified) + len(self.deleted) + len(self.moved)

    def is_empty(self) -> bool:
        """Check if there are no changes"""
        return self.total() == 0


class ScrivenerSyncDetector:
    """Detects and applies changes between Scrivener project and vector DB"""

    def __init__(
        self,
        indexer: ScrivenerIndexer,
        vectordb: VectorDBClient,
        scrivener_path: str,
        manuscript_folder: Optional[str] = None,
    ):
        """
        Initialize sync detector.

        Args:
            indexer: ScrivenerIndexer instance for re-indexing documents
            vectordb: VectorDBClient instance for querying/updating DB
            scrivener_path: Path to .scriv project
            manuscript_folder: Optional manuscript folder to filter by
        """
        self.indexer = indexer
        self.vectordb = vectordb
        self.scrivener_path = Path(scrivener_path)
        self.manuscript_folder = manuscript_folder

    def get_filesystem_state(self) -> Dict[str, DocumentInfo]:
        """
        Get current state of documents in filesystem.

        Returns:
            Dict mapping scrivener_id to DocumentInfo
        """
        filesystem_state = {}

        # Parse .scrivx to get structure and chapter assignments
        parser = ScrivenerParser(
            str(self.scrivener_path), manuscript_folder=self.manuscript_folder
        )
        structure = parser.get_chapter_structure()

        # Build mapping of UUID to chapter info
        uuid_to_chapter = {}
        self._build_uuid_mapping(structure.get("structure", []), uuid_to_chapter)

        # Scan all RTF files in Files/Data
        files_path = self.scrivener_path / "Files" / "Data"
        if not files_path.exists():
            logger.warning(f"Scrivener Files/Data not found: {files_path}")
            return filesystem_state

        for rtf_file in files_path.rglob("*.rtf"):
            # Extract UUID from path
            if rtf_file.parent.name == "Data":
                scrivener_id = rtf_file.stem
            else:
                scrivener_id = rtf_file.parent.name

            # If manuscript_folder filter is active and UUID not in mapping, skip
            if self.manuscript_folder and scrivener_id not in uuid_to_chapter:
                continue

            # Get chapter info
            chapter_info = uuid_to_chapter.get(scrivener_id, {})
            chapter_number = chapter_info.get("chapter_number")
            chapter_title = chapter_info.get("chapter_title")

            # Get file stats
            try:
                stat = rtf_file.stat()
                file_mtime = stat.st_mtime
            except Exception as e:
                logger.warning(f"Could not stat {rtf_file}: {e}")
                file_mtime = None

            filesystem_state[scrivener_id] = DocumentInfo(
                scrivener_id=scrivener_id,
                file_path=str(rtf_file),
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                file_mtime=file_mtime,
            )

        logger.info(f"Found {len(filesystem_state)} documents in Scrivener project")
        return filesystem_state

    def get_indexed_state(self) -> Dict[str, DocumentInfo]:
        """
        Get current state of documents in vector DB.

        Returns:
            Dict mapping scrivener_id to DocumentInfo
        """
        indexed_state = {}

        # Query all Scrivener documents from vector DB
        results = self.vectordb.query_by_metadata(
            {"source_type": "scrivener"}, limit=None
        )

        # Group by scrivener_id (multiple chunks per document)
        for result in results:
            metadata = result["metadata"]
            scrivener_id = metadata.get("scrivener_id")

            if not scrivener_id:
                continue

            # Use first occurrence of each document (all chunks have same metadata)
            if scrivener_id not in indexed_state:
                indexed_state[scrivener_id] = DocumentInfo(
                    scrivener_id=scrivener_id,
                    file_path=metadata.get("file_path", ""),
                    chapter_number=metadata.get("chapter_number"),
                    chapter_title=metadata.get("chapter_title"),
                    content_hash=metadata.get("content_hash"),
                    file_mtime=metadata.get("file_mtime"),
                    doc_type=metadata.get("doc_type"),
                )

        logger.info(f"Found {len(indexed_state)} documents indexed in vector DB")
        return indexed_state

    def detect_changes(self) -> ChangeSet:
        """
        Compare filesystem state vs vector DB state and detect changes.

        Returns:
            ChangeSet with all detected changes
        """
        logger.info("Detecting changes between filesystem and vector DB...")

        filesystem = self.get_filesystem_state()
        indexed = self.get_indexed_state()

        changes = ChangeSet()

        # Get ID sets for comparison
        filesystem_ids = set(filesystem.keys())
        indexed_ids = set(indexed.keys())

        # Detect new documents (in filesystem, not in DB)
        new_ids = filesystem_ids - indexed_ids
        for scrivener_id in new_ids:
            doc = filesystem[scrivener_id]
            changes.new.append(
                DocumentChange(
                    scrivener_id=scrivener_id,
                    change_type="new",
                    file_path=doc.file_path,
                    new_chapter=doc.chapter_number,
                )
            )

        # Detect deleted documents (in DB, not in filesystem)
        deleted_ids = indexed_ids - filesystem_ids
        for scrivener_id in deleted_ids:
            doc = indexed[scrivener_id]
            changes.deleted.append(
                DocumentChange(
                    scrivener_id=scrivener_id,
                    change_type="deleted",
                    file_path=doc.file_path,
                    old_chapter=doc.chapter_number,
                )
            )

        # Detect modifications and moves (in both filesystem and DB)
        common_ids = filesystem_ids & indexed_ids
        for scrivener_id in common_ids:
            fs_doc = filesystem[scrivener_id]
            idx_doc = indexed[scrivener_id]

            # Check if chapter changed (moved)
            if fs_doc.chapter_number != idx_doc.chapter_number:
                changes.moved.append(
                    DocumentChange(
                        scrivener_id=scrivener_id,
                        change_type="moved",
                        file_path=fs_doc.file_path,
                        old_chapter=idx_doc.chapter_number,
                        new_chapter=fs_doc.chapter_number,
                    )
                )

            # Check if content modified (based on mtime)
            # Note: We can't check content_hash here without reading the file
            # So we'll check mtime as a proxy
            elif fs_doc.file_mtime and idx_doc.file_mtime:
                if fs_doc.file_mtime > idx_doc.file_mtime:
                    changes.modified.append(
                        DocumentChange(
                            scrivener_id=scrivener_id,
                            change_type="modified",
                            file_path=fs_doc.file_path,
                            old_hash=idx_doc.content_hash,
                        )
                    )

        logger.info(
            f"Changes detected: {len(changes.new)} new, {len(changes.modified)} modified, "
            f"{len(changes.deleted)} deleted, {len(changes.moved)} moved"
        )

        return changes

    def apply_changes(self, changes: ChangeSet) -> Dict[str, int]:
        """
        Apply detected changes to vector DB.

        Args:
            changes: ChangeSet to apply

        Returns:
            Dict with statistics (new_indexed, modified_indexed, deleted, moved_updated)
        """
        stats = {
            "new_indexed": 0,
            "modified_indexed": 0,
            "deleted": 0,
            "moved_updated": 0,
        }

        if changes.is_empty():
            logger.info("No changes to apply")
            return stats

        logger.info(f"Applying {changes.total()} changes...")

        # Apply deletions
        for change in changes.deleted:
            try:
                self.vectordb.delete_by_scrivener_id(change.scrivener_id)
                stats["deleted"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to delete {change.scrivener_id}: {e}", exc_info=True
                )

        # Apply moves (delete old + re-index with new chapter)
        for change in changes.moved:
            try:
                # Delete old chunks
                self.vectordb.delete_by_scrivener_id(change.scrivener_id)
                # Re-index with new chapter metadata
                self.indexer._index_document(Path(change.file_path))
                stats["moved_updated"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to move {change.scrivener_id}: {e}", exc_info=True
                )

        # Apply modifications (re-index)
        for change in changes.modified:
            try:
                self.indexer._index_document(Path(change.file_path))
                stats["modified_indexed"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to re-index {change.scrivener_id}: {e}", exc_info=True
                )

        # Apply new documents (index)
        for change in changes.new:
            try:
                self.indexer._index_document(Path(change.file_path))
                stats["new_indexed"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to index new {change.scrivener_id}: {e}", exc_info=True
                )

        logger.info(
            f"Sync complete: {stats['new_indexed']} new, {stats['modified_indexed']} modified, "
            f"{stats['deleted']} deleted, {stats['moved_updated']} moved"
        )

        return stats

    def sync(self) -> Dict[str, int]:
        """
        Perform full sync: detect and apply all changes.

        Returns:
            Dict with statistics
        """
        logger.info("Starting full Scrivener sync...")

        changes = self.detect_changes()
        stats = self.apply_changes(changes)

        logger.info("Sync complete")
        return stats

    def _build_uuid_mapping(self, items: List[Dict], mapping: Dict, parent_info=None):
        """
        Recursively build UUID to chapter metadata mapping.

        Args:
            items: List of binder items from ScrivenerParser
            mapping: Dict to populate with UUID -> chapter info
            parent_info: Parent chapter info (for nested documents)
        """
        for item in items:
            uuid = item.get("uuid")
            chapter_num = item.get("chapter_number")
            title = item.get("title", "Untitled")
            is_folder = item.get("is_folder", False)

            if uuid:
                # Determine chapter title
                if chapter_num is not None and is_folder:
                    chapter_title = title
                elif chapter_num is not None and not is_folder:
                    if parent_info and parent_info.get("is_folder"):
                        chapter_title = parent_info.get("chapter_title", title)
                    else:
                        chapter_title = title
                elif parent_info:
                    chapter_title = parent_info.get("chapter_title", title)
                    if chapter_num is None:
                        chapter_num = parent_info.get("chapter_number")
                else:
                    chapter_title = title

                # Store metadata for this UUID
                mapping[uuid] = {
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "parent": parent_info.get("chapter_title") if parent_info else None,
                    "is_folder": is_folder,
                }

                # Recurse into children
                if "children" in item:
                    current_info = mapping[uuid]
                    self._build_uuid_mapping(item["children"], mapping, current_info)
