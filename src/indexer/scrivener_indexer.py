"""
Scrivener project indexer.

Parses .scriv bundle structure and indexes documents for semantic search.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from striprtf.striprtf import rtf_to_text

from ..vectordb.client import VectorDBClient
from .chunking import ScrivenerChunker

logger = structlog.get_logger()


class ScrivenerIndexer:
    """Index Scrivener project documents"""

    def __init__(
        self, scrivener_path: str, vectordb: VectorDBClient, config: Dict[str, Any]
    ):
        """
        Initialize Scrivener indexer.

        Args:
            scrivener_path: Path to .scriv bundle
            vectordb: Vector database client
            config: Configuration dict
        """
        self.scrivener_path = Path(scrivener_path)
        self.files_path = self.scrivener_path / "Files" / "Data"
        self.vectordb = vectordb
        self.config = config

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

    def index_all(self) -> Dict[str, int]:
        """
        Index entire Scrivener project.

        Returns:
            Dict with stats (documents_indexed, chunks_indexed)
        """
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

        # Update index timestamp
        from datetime import datetime
        timestamp = datetime.now().isoformat()
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

            # Build metadata
            metadata = {
                "source_type": "scrivener",
                "file_path": str(rtf_path),
                "doc_type": doc_type,
                "scrivener_id": rtf_path.stem,  # Document ID
            }

            # Try to extract chapter number from path or content
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

            # Index
            return self.vectordb.index_chunks(chunk_dicts)

        except Exception as e:
            logger.error(f"Failed to process {rtf_path}: {e}")
            return 0

    def _determine_doc_type(self, path: Path, text: str) -> str:
        """Determine if document is draft, note, or synopsis"""
        # Check path for common Scrivener folders
        path_str = str(path).lower()

        if "draft" in path_str or "manuscript" in path_str:
            return "draft"
        elif "research" in path_str or "notes" in path_str:
            return "note"
        elif len(text) < 500:  # Short text likely a synopsis
            return "synopsis"
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
