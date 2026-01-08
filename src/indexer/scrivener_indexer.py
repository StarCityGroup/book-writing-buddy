"""
Scrivener project indexer.

Parses .scriv bundle structure and indexes documents for semantic search.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from striprtf.striprtf import rtf_to_text

from ..scrivener_parser import ScrivenerParser
from ..vectordb.client import VectorDBClient
from .chunking import ScrivenerChunker

logger = structlog.get_logger()


class ScrivenerIndexer:
    """Index Scrivener project documents"""

    def __init__(
        self,
        scrivener_path: str,
        vectordb: VectorDBClient,
        config: Dict[str, Any],
        manuscript_folder: Optional[str] = None,
    ):
        """
        Initialize Scrivener indexer.

        Args:
            scrivener_path: Path to .scriv bundle
            vectordb: Vector database client
            config: Configuration dict
            manuscript_folder: Optional name of manuscript folder to filter by
        """
        self.scrivener_path = Path(scrivener_path)
        self.files_path = self.scrivener_path / "Files" / "Data"
        self.vectordb = vectordb
        self.config = config
        self.manuscript_folder = manuscript_folder

        # Initialize chunker
        self.chunker = ScrivenerChunker(
            target_size=config["embedding"]["chunk_size"],
            min_size=config["chunking"]["min_chunk_size"],
            max_size=config["chunking"]["max_chunk_size"],
            overlap=config["embedding"]["chunk_overlap"],
        )

        # Get project-specific paths
        self.draft_folder = (
            config.get("project", {})
            .get("scrivener", {})
            .get("draft_folder", "Manuscript")
        )
        self.research_folder = (
            config.get("project", {})
            .get("scrivener", {})
            .get("research_folder", "Research")
        )

        # Parse Scrivener structure to get accurate chapter mapping
        self.uuid_to_chapter = {}
        try:
            parser = ScrivenerParser(
                str(scrivener_path), manuscript_folder=manuscript_folder
            )
            structure = parser.get_chapter_structure()
            self._build_uuid_mapping(structure.get("structure", []))
            logger.info(
                f"Loaded Scrivener structure: {len(self.uuid_to_chapter)} documents mapped"
            )
        except Exception as e:
            logger.warning(f"Could not parse Scrivener structure: {e}")
            logger.warning("Will fall back to guessing chapter numbers from content")

    def reload_structure(self):
        """Reload Scrivener structure to pick up new/moved documents."""
        try:
            parser = ScrivenerParser(
                str(self.scrivener_path), manuscript_folder=self.manuscript_folder
            )
            structure = parser.get_chapter_structure()
            self.uuid_to_chapter = {}
            self._build_uuid_mapping(structure.get("structure", []))
            logger.info(
                f"Reloaded Scrivener structure: {len(self.uuid_to_chapter)} documents mapped"
            )
        except Exception as e:
            logger.warning(f"Could not reload Scrivener structure: {e}")

    def _build_uuid_mapping(self, items, parent_info=None):
        """Recursively build UUID to chapter metadata mapping.

        Args:
            items: List of binder items from ScrivenerParser
            parent_info: Parent chapter info (for nested documents)
        """
        for item in items:
            uuid = item.get("uuid")
            chapter_num = item.get("chapter_number")
            title = item.get("title", "Untitled")
            is_folder = item.get("is_folder", False)

            if uuid:
                # Determine chapter title
                # Note: Check "is not None" because chapter_num can be 0 (Preface)
                if chapter_num is not None and is_folder:
                    # Chapter folder - use its title
                    chapter_title = title
                elif chapter_num is not None and not is_folder:
                    # Document with chapter number
                    if parent_info and parent_info.get("is_folder"):
                        # Nested doc inside chapter folder - inherit folder's title
                        chapter_title = parent_info.get("chapter_title", title)
                    else:
                        # Standalone chapter doc (like Preface) - use its own title
                        chapter_title = title
                elif parent_info:
                    # No chapter number - inherit from parent
                    chapter_title = parent_info.get("chapter_title", title)
                    if chapter_num is None:
                        chapter_num = parent_info.get("chapter_number")
                else:
                    chapter_title = title

                # Store metadata for this UUID
                self.uuid_to_chapter[uuid] = {
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "parent": parent_info.get("chapter_title") if parent_info else None,
                    "is_folder": is_folder,
                }

                # Recurse into children, passing chapter info down
                if "children" in item:
                    # Use this item's chapter info as parent for children
                    current_info = self.uuid_to_chapter[uuid]
                    self._build_uuid_mapping(item["children"], parent_info=current_info)

    def index_all(self, use_sync: bool = False) -> Dict[str, int]:
        """
        Index entire Scrivener project.

        Args:
            use_sync: If True, use smart sync to detect changes instead of blind re-indexing

        Returns:
            Dict with stats (documents_indexed, chunks_indexed)
        """
        if use_sync:
            # Use sync mode (detects and applies only changes)
            return self.sync()

        stats = {"documents_indexed": 0, "chunks_indexed": 0}

        # Index all RTF files in Files/Data
        if not self.files_path.exists():
            logger.error(f"Scrivener Files/Data not found: {self.files_path}")
            return stats

        for rtf_file in self.files_path.rglob("*.rtf"):
            try:
                chunks = self._index_document(rtf_file)
                if chunks > 0:
                    stats["documents_indexed"] += 1
                    stats["chunks_indexed"] += chunks
            except Exception as e:
                logger.error(f"Failed to index {rtf_file}: {e}")
                continue

        logger.info(
            f"Indexed {stats['documents_indexed']} Scrivener documents, {stats['chunks_indexed']} chunks"
        )

        # Update index timestamp (use UTC)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.vectordb.set_index_timestamp("scrivener", timestamp)

        return stats

    def sync(self) -> Dict[str, int]:
        """
        Sync Scrivener project with vector DB using smart change detection.

        Detects and applies only changes (new, modified, deleted, moved documents).
        More efficient than full re-indexing.

        Returns:
            Dict with stats (new_indexed, modified_indexed, deleted, moved_updated)
        """
        # Import here to avoid circular dependency
        from .scrivener_sync import ScrivenerSyncDetector

        logger.info("Starting Scrivener sync (smart change detection)...")

        # Create sync detector
        detector = ScrivenerSyncDetector(
            indexer=self,
            vectordb=self.vectordb,
            scrivener_path=str(self.scrivener_path),
            manuscript_folder=self.manuscript_folder,
        )

        # Run sync
        stats = detector.sync()

        # Update index timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        self.vectordb.set_index_timestamp("scrivener", timestamp)

        return stats

    def index_folder(self, folder_name: str) -> int:
        """
        Index documents in a specific folder.

        Args:
            folder_name: Folder name to index

        Returns:
            Number of chunks indexed
        """
        # This is simplified - real implementation would parse .scrivx
        # to map folder structure
        logger.warning("Folder-specific indexing not yet implemented")
        return 0

    def _compute_content_hash(self, text: str) -> str:
        """
        Compute MD5 hash of content for change detection.

        Args:
            text: Plain text content

        Returns:
            MD5 hash as hex string
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _index_document(self, rtf_path: Path) -> int:
        """Index a single Scrivener document"""
        try:
            # Read RTF file
            with open(rtf_path, "r", encoding="utf-8") as f:
                rtf_content = f.read()

            # Convert RTF to plain text
            text = rtf_to_text(rtf_content)

            if not text.strip():
                return 0

            # Determine document type
            doc_type = self._determine_doc_type(rtf_path, text)

            # Extract UUID from parent directory (Scrivener structure is UUID/content.rtf)
            # If file is directly in Data (not in a subdirectory), use the filename
            if rtf_path.parent.name == "Data":
                scrivener_uuid = rtf_path.stem
            else:
                scrivener_uuid = rtf_path.parent.name

            # If manuscript_folder is set and this UUID isn't in our mapping, skip it
            if self.manuscript_folder and scrivener_uuid not in self.uuid_to_chapter:
                return 0

            # Get file stats for change tracking
            file_stat = rtf_path.stat()
            file_mtime = file_stat.st_mtime
            content_hash = self._compute_content_hash(text)
            indexed_at = datetime.now(timezone.utc).isoformat()

            # Build metadata
            metadata = {
                "source_type": "scrivener",
                "file_path": str(rtf_path),
                "doc_type": doc_type,
                "scrivener_id": scrivener_uuid,
                "content_hash": content_hash,
                "file_mtime": file_mtime,
                "indexed_at": indexed_at,
            }

            # Get chapter info from UUID mapping (preferred) or fall back to guessing
            if scrivener_uuid in self.uuid_to_chapter:
                chapter_info = self.uuid_to_chapter[scrivener_uuid]
                # Use "is not None" because chapter_number can be 0 (Preface)
                if chapter_info.get("chapter_number") is not None:
                    metadata["chapter_number"] = chapter_info["chapter_number"]
                    metadata["chapter_title"] = chapter_info.get("chapter_title", "")
                if chapter_info.get("parent"):
                    metadata["parent_title"] = chapter_info["parent"]
            else:
                # Fallback: try to extract chapter number from path or content
                chapter_num = self._extract_chapter_number(rtf_path, text)
                if chapter_num:
                    metadata["chapter_number"] = chapter_num

            # Chunk document
            chunks = self.chunker.chunk_scrivener_doc(
                content=text,
                doc_type=doc_type,
                path=str(rtf_path.relative_to(self.scrivener_path)),
                metadata=metadata,
            )

            # Convert to format expected by vectordb
            chunk_dicts = [
                {"text": chunk.text, "metadata": chunk.metadata} for chunk in chunks
            ]

            # Index with error handling for embedding issues
            try:
                return self.vectordb.index_chunks(chunk_dicts)
            except Exception as embed_error:
                # Encoding/embedding errors - skip this document
                logger.warning(
                    f"Skipping {rtf_path.name} due to embedding error: {embed_error}"
                )
                return 0

        except Exception as e:
            logger.error(f"Failed to process {rtf_path}: {e}")
            return 0

    def _determine_doc_type(self, path: Path, text: str) -> str:
        """Determine document type based on text structure.

        - draft: Documents with complete paragraphs and prose
        - notes: Fragmented text, bullet points, short lines
        """
        if not text.strip():
            return "notes"

        # Split into lines and paragraphs
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        if len(lines) == 0:
            return "notes"

        # Calculate text structure metrics
        total_chars = len(text.strip())
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        avg_para_length = (
            sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0
        )

        # Count indicators of fragmentary text
        fragment_indicators = 0

        # 1. Short average line length (< 60 chars suggests bullet points or fragments)
        if avg_line_length < 60:
            fragment_indicators += 1

        # 2. Many short lines (< 40 chars)
        short_lines = sum(1 for line in lines if len(line) < 40)
        if short_lines / len(lines) > 0.4:  # More than 40% short lines
            fragment_indicators += 1

        # 3. Bullet point indicators (-, *, •, numbers)
        bullet_pattern = r"^\s*[-*•]\s+|^\s*\d+[\.)]\s+"
        import re

        bullet_lines = sum(1 for line in lines if re.match(bullet_pattern, line))
        if bullet_lines / len(lines) > 0.2:  # More than 20% bullets
            fragment_indicators += 1

        # 4. URLs present (research/reference material)
        url_pattern = r"https?://|www\.|\.com|\.org|\.edu|\.gov"
        url_matches = re.findall(url_pattern, text, re.IGNORECASE)
        if len(url_matches) >= 3:  # 3+ URLs suggests notes/references
            fragment_indicators += 1

        # 5. Very short paragraphs (avg < 100 chars suggests notes)
        if avg_para_length < 100:
            fragment_indicators += 1

        # 6. Many single-line paragraphs (each line is its own paragraph)
        if len(paragraphs) > len(lines) * 0.7:
            fragment_indicators += 1

        # Decision: If 2+ fragment indicators, it's notes
        if fragment_indicators >= 2:
            return "notes"
        else:
            return "draft"

    def _extract_chapter_number(self, path: Path, text: str) -> Optional[int]:
        """Try to extract chapter number from path or content"""
        import re

        # Try path first
        path_match = re.search(r"chapter[_\s-]?(\d+)", str(path), re.IGNORECASE)
        if path_match:
            return int(path_match.group(1))

        # Try document title/heading
        lines = text.split("\n")[:5]  # Check first 5 lines
        for line in lines:
            title_match = re.search(r"chapter\s+(\d+)", line, re.IGNORECASE)
            if title_match:
                return int(title_match.group(1))

        return None

    def get_chapter_text(self, chapter_number: int) -> Optional[str]:
        """
        Get the current draft text for a chapter.

        Args:
            chapter_number: Chapter number

        Returns:
            Combined text of all draft documents for that chapter
        """
        # Search for documents with this chapter number
        chapter_texts = []

        for rtf_file in self.files_path.rglob("*.rtf"):
            try:
                with open(rtf_file, "r", encoding="utf-8") as f:
                    rtf_content = f.read()

                text = rtf_to_text(rtf_content)
                chapter_num = self._extract_chapter_number(rtf_file, text)

                if chapter_num == chapter_number:
                    doc_type = self._determine_doc_type(rtf_file, text)
                    if doc_type == "draft":
                        chapter_texts.append(text)

            except Exception as e:
                logger.error(f"Failed to read {rtf_file}: {e}")
                continue

        if chapter_texts:
            return "\n\n---\n\n".join(chapter_texts)

        return None
