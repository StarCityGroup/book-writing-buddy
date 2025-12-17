"""
Semantic chunking strategies for book research materials.

This module implements intelligent text chunking that preserves context
and meaning, optimized for semantic search over book-length content.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Chunk:
    """A text chunk with metadata"""

    text: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any]


class SemanticChunker:
    """
    Chunks text based on semantic boundaries (paragraphs, sections)
    rather than arbitrary token counts.
    """

    def __init__(
        self,
        target_size: int = 500,
        min_size: int = 200,
        max_size: int = 800,
        overlap: int = 100,
    ):
        """
        Args:
            target_size: Target chunk size in characters
            min_size: Minimum chunk size (avoid tiny fragments)
            max_size: Maximum chunk size (force split if exceeded)
            overlap: Characters to overlap between chunks
        """
        self.target_size = target_size
        self.min_size = min_size
        self.max_size = max_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Chunk]:
        """
        Chunk text semantically, preserving paragraph and section boundaries.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of Chunk objects
        """
        if not text or len(text.strip()) == 0:
            return []

        metadata = metadata or {}

        # Split into paragraphs first
        paragraphs = self._split_paragraphs(text)

        chunks = []
        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            # Skip empty paragraphs
            if not para.strip():
                continue

            # If adding this paragraph would exceed max_size, create a chunk
            if len(current_chunk) + len(para) > self.max_size and current_chunk:
                chunks.append(
                    self._create_chunk(current_chunk, current_start, metadata)
                )

                # Start new chunk with overlap
                overlap_text = self._get_overlap(current_chunk)
                current_chunk = overlap_text + para
                current_start = current_start + len(current_chunk) - len(overlap_text)
            else:
                current_chunk += para

        # Add final chunk
        if current_chunk.strip():
            chunks.append(self._create_chunk(current_chunk, current_start, metadata))

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs, preserving meaningful boundaries.

        Handles:
        - Double newlines (standard paragraphs)
        - Section headers
        - List items
        """
        # Replace various paragraph separators with consistent marker
        text = re.sub(r"\n\s*\n", "\n\n", text)

        # Split on double newlines
        paragraphs = text.split("\n\n")

        return [p + "\n\n" for p in paragraphs if p.strip()]

    def _get_overlap(self, text: str) -> str:
        """Get the last N characters as overlap for next chunk"""
        if len(text) <= self.overlap:
            return text

        # Try to break at sentence boundary
        overlap_text = text[-self.overlap :]

        # Find last sentence end in overlap
        sentence_end = max(
            overlap_text.rfind(". "), overlap_text.rfind("! "), overlap_text.rfind("? ")
        )

        if sentence_end > 0:
            return overlap_text[sentence_end + 2 :]

        return overlap_text

    def _create_chunk(
        self, text: str, start_pos: int, metadata: Dict[str, Any]
    ) -> Chunk:
        """Create a Chunk object with metadata"""
        text = text.strip()
        return Chunk(
            text=text,
            start_pos=start_pos,
            end_pos=start_pos + len(text),
            metadata=metadata.copy(),
        )


class PDFChunker(SemanticChunker):
    """
    Specialized chunker for PDF documents that respects page boundaries
    and extracts section headers.
    """

    def chunk_with_pages(
        self, pages: List[Dict[str, Any]], global_metadata: Dict[str, Any] = None
    ) -> List[Chunk]:
        """
        Chunk PDF with page-aware metadata.

        Args:
            pages: List of dicts with 'text' and 'page_num' keys
            global_metadata: Metadata for entire document

        Returns:
            List of chunks with page numbers in metadata
        """
        global_metadata = global_metadata or {}
        all_chunks = []

        for page_data in pages:
            page_text = page_data["text"]
            page_num = page_data["page_num"]

            # Add page number to metadata
            page_metadata = global_metadata.copy()
            page_metadata["page_number"] = page_num

            # Chunk this page
            page_chunks = self.chunk(page_text, page_metadata)
            all_chunks.extend(page_chunks)

        return all_chunks


class ScrivenerChunker(SemanticChunker):
    """
    Specialized chunker for Scrivener documents that preserves
    document hierarchy (folders, files, synopses).
    """

    def chunk_scrivener_doc(
        self,
        content: str,
        doc_type: str,  # 'draft', 'note', 'synopsis'
        path: str,
        metadata: Dict[str, Any] = None,
    ) -> List[Chunk]:
        """
        Chunk Scrivener document with type-specific handling.

        Args:
            content: Document text
            doc_type: Type of document
            path: Path within Scrivener project
            metadata: Additional metadata

        Returns:
            List of chunks with Scrivener-specific metadata
        """
        metadata = metadata or {}
        metadata.update(
            {"source_type": "scrivener", "doc_type": doc_type, "scrivener_path": path}
        )

        # Synopses are usually short, don't chunk
        if doc_type == "synopsis" and len(content) < self.max_size:
            return [
                Chunk(
                    text=content, start_pos=0, end_pos=len(content), metadata=metadata
                )
            ]

        return self.chunk(content, metadata)


def create_chunker(strategy: str = "semantic", **kwargs) -> SemanticChunker:
    """
    Factory function to create appropriate chunker.

    Args:
        strategy: Chunking strategy ('semantic', 'pdf', 'scrivener')
        **kwargs: Arguments passed to chunker constructor

    Returns:
        Chunker instance
    """
    chunkers = {
        "semantic": SemanticChunker,
        "pdf": PDFChunker,
        "scrivener": ScrivenerChunker,
    }

    chunker_class = chunkers.get(strategy, SemanticChunker)
    return chunker_class(**kwargs)
