"""RAG module for book research using Qdrant."""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .scrivener_parser import ScrivenerParser
from .vectordb.client import VectorDBClient

logger = structlog.get_logger()


class BookRAG:
    """RAG system for book research using Qdrant vector database."""

    def __init__(self, qdrant_url: Optional[str] = None):
        """Initialize BookRAG system.

        Args:
            qdrant_url: URL to Qdrant server (defaults to env variable)
        """
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")

        # Initialize vector DB client
        self.vectordb = VectorDBClient(
            qdrant_url=self.qdrant_url,
            collection_name="book_research",
            embedding_model="all-MiniLM-L6-v2",
            vector_size=384,
        )

        # Zotero database path
        self.zotero_path = os.getenv(
            "ZOTERO_PATH", "/Users/anthonytownsend/Zotero"
        )
        self.zotero_db = Path(self.zotero_path) / "zotero.sqlite"

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Semantic search through research materials.

        Args:
            query: Search query text
            filters: Optional filters (e.g., {'chapter_number': 9, 'source_type': 'zotero'})
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of search results with text, score, and metadata
        """
        return self.vectordb.search(
            query=query, filters=filters, limit=limit, score_threshold=score_threshold
        )

    def get_context_for_query(
        self, query: str, chapter: Optional[int] = None, n_results: int = 10
    ) -> str:
        """Get formatted context string for a research query.

        Args:
            query: User's research question
            chapter: Optional chapter number to filter by
            n_results: Maximum number of chunks to include

        Returns:
            Formatted context string for LLM
        """
        filters = {"chapter_number": chapter} if chapter else None
        results = self.search(
            query=query, filters=filters, limit=n_results, score_threshold=0.6
        )

        if not results:
            return ""

        # Format as context
        context_parts = ["## Relevant Information from Your Research\n"]

        for r in results:
            meta = r["metadata"]
            source_info = f"**Source:** {meta.get('title', 'Unknown')}"
            if meta.get("chapter_number"):
                source_info += f" (Chapter {meta['chapter_number']})"
            if meta.get("page"):
                source_info += f", Page {meta['page']}"

            context_parts.append(
                f"{source_info}\n"
                f"**Relevance:** {r['score']:.0%}\n\n"
                f"{r['text']}\n\n"
                f"---\n"
            )

        return "\n".join(context_parts)

    def get_annotations(self, chapter: Optional[int] = None) -> Dict[str, Any]:
        """Retrieve Zotero annotations for a chapter.

        Args:
            chapter: Chapter number (if None, gets all annotations)

        Returns:
            Dict with annotations organized by source
        """
        if not self.zotero_db.exists():
            logger.warning(f"Zotero database not found: {self.zotero_db}")
            return {"error": "Zotero database not found"}

        try:
            conn = sqlite3.connect(self.zotero_db)
            cursor = conn.cursor()

            # Query for annotations (highlights, notes)
            # This is a simplified query - real implementation would be more complex
            query = """
                SELECT
                    items.itemID,
                    itemDataValues.value as content,
                    items.key
                FROM items
                JOIN itemData ON items.itemID = itemData.itemID
                JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
                WHERE items.itemTypeID IN (13, 14)  # Note and attachment types
                LIMIT 100
            """

            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            annotations = {
                "chapter": chapter,
                "count": len(rows),
                "items": [
                    {"id": row[0], "content": row[1][:200], "key": row[2]}
                    for row in rows
                ],
            }

            return annotations

        except Exception as e:
            logger.error(f"Error querying Zotero annotations: {e}")
            return {"error": str(e)}

    def analyze_gaps(self, chapters: Optional[List[int]] = None) -> Dict[str, Any]:
        """Analyze research gaps across chapters.

        Args:
            chapters: List of chapter numbers to analyze (if None, analyzes all)

        Returns:
            Dict with gap analysis results
        """
        # Get collection info
        info = self.vectordb.get_collection_info()
        total_points = info["points_count"]

        # Simple gap analysis - count points per chapter
        gaps = {"total_indexed": total_points, "chapters": {}}

        # In a real implementation, would query by chapter and analyze density
        # For now, return placeholder structure
        if chapters:
            for chapter_num in chapters:
                results = self.search(
                    query="chapter content",
                    filters={"chapter_number": chapter_num},
                    limit=1000,
                    score_threshold=0.0,
                )
                gaps["chapters"][chapter_num] = {
                    "chunk_count": len(results),
                    "status": "adequate" if len(results) > 10 else "needs_research",
                }

        return gaps

    def find_similar(
        self, text: str, threshold: float = 0.85, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find similar or duplicate content.

        Args:
            text: Text to check for similarity
            threshold: Similarity threshold (0-1), higher = more similar
            limit: Max results to return

        Returns:
            List of similar chunks
        """
        return self.search(
            query=text, filters=None, limit=limit, score_threshold=threshold
        )

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about indexed data including freshness.

        Returns:
            Dict with collection stats and timestamps
        """
        info = self.vectordb.get_collection_info()
        timestamps = self.vectordb.get_index_timestamps()

        # Format timestamps for display
        formatted_timestamps = {}
        for source_type, ts in timestamps.items():
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    age = datetime.now() - dt
                    if age.days > 0:
                        formatted = f"{age.days} day{'s' if age.days > 1 else ''} ago"
                    elif age.seconds > 3600:
                        hours = age.seconds // 3600
                        formatted = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    elif age.seconds > 60:
                        minutes = age.seconds // 60
                        formatted = (
                            f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                        )
                    else:
                        formatted = "just now"
                    formatted_timestamps[source_type] = formatted
                except Exception:
                    formatted_timestamps[source_type] = "unknown"
            else:
                formatted_timestamps[source_type] = "never"

        return {
            "points_count": info["points_count"],
            "status": info["status"],
            "last_indexed": formatted_timestamps,
            "raw_timestamps": timestamps,
        }

    def get_chapter_info(self, chapter_number: int) -> Dict[str, Any]:
        """Get comprehensive information about a chapter.

        Args:
            chapter_number: Chapter number

        Returns:
            Dict with chapter metadata, source counts, and content stats
        """
        info = {
            "chapter_number": chapter_number,
            "zotero": {},
            "scrivener": {},
            "indexed_chunks": 0,
        }

        # Get indexed chunk count
        results = self.search(
            query="chapter content",
            filters={"chapter_number": chapter_number},
            limit=1000,
            score_threshold=0.0,
        )
        info["indexed_chunks"] = len(results)

        # Get Zotero info from indexed data
        zotero_results = [r for r in results if r["metadata"].get("source_type") == "zotero"]
        if zotero_results:
            # Extract unique sources
            sources = set()
            for r in zotero_results:
                title = r["metadata"].get("title")
                if title:
                    sources.add(title)
            info["zotero"] = {
                "source_count": len(sources),
                "chunk_count": len(zotero_results),
                "sources": list(sources)[:10],  # Limit to 10 for display
            }

        # Get Scrivener info from indexed data
        scrivener_results = [
            r for r in results if r["metadata"].get("source_type") == "scrivener"
        ]
        if scrivener_results:
            word_count = sum(len(r["text"].split()) for r in scrivener_results)
            info["scrivener"] = {
                "chunk_count": len(scrivener_results),
                "estimated_words": word_count,
            }

        return info

    def check_sync(self) -> Dict[str, Any]:
        """Check sync status between outline.txt, Zotero, and Scrivener.

        Returns:
            Dict with sync status, mismatches, and recommendations
        """
        # Get chapters from outline.txt
        outline_chapters = self._extract_chapters_from_outline()

        # Get chapters from indexed data
        zotero_chapters = self._get_indexed_chapters("zotero")
        scrivener_chapters = self._get_indexed_chapters("scrivener")

        # Find mismatches
        all_chapters = (
            set(outline_chapters.keys())
            | set(zotero_chapters.keys())
            | set(scrivener_chapters.keys())
        )
        mismatches = []

        for chapter_num in sorted(all_chapters):
            in_outline = chapter_num in outline_chapters
            in_zotero = chapter_num in zotero_chapters
            in_scrivener = chapter_num in scrivener_chapters

            if in_scrivener and not in_zotero:
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_zotero",
                        "severity": "medium",
                        "message": f"Chapter {chapter_num} exists in Scrivener but has no Zotero collection",
                    }
                )
            elif in_scrivener and not in_outline:
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_outline",
                        "severity": "low",
                        "message": f"Chapter {chapter_num} exists in Scrivener but not in outline.txt",
                    }
                )
            elif not in_scrivener and (in_zotero or in_outline):
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_scrivener",
                        "severity": "high",
                        "message": f"Chapter {chapter_num} exists in outline/Zotero but not in Scrivener",
                    }
                )

        # Generate recommendations
        recommendations = []
        if any(m["type"] == "missing_from_zotero" for m in mismatches):
            chapters_list = [
                str(m["chapter"])
                for m in mismatches
                if m["type"] == "missing_from_zotero"
            ]
            recommendations.append(
                f"Create Zotero collections for chapters: {', '.join(chapters_list)}"
            )
        if any(m["type"] == "missing_from_outline" for m in mismatches):
            recommendations.append(
                "Update data/outline.txt to match your current Scrivener chapter structure"
            )
        if any(m["type"] == "missing_from_scrivener" for m in mismatches):
            chapters_list = [
                str(m["chapter"])
                for m in mismatches
                if m["type"] == "missing_from_scrivener"
            ]
            recommendations.append(
                f"Chapters {', '.join(chapters_list)} may have been removed or renumbered in Scrivener. "
                "Update Zotero/outline to match."
            )

        if not mismatches:
            recommendations.append("All sources are in sync")
        else:
            recommendations.append(
                "Remember: Scrivener is your definitive chapter structure. "
                "Organize Zotero and outline.txt to match it."
            )

        return {
            "in_sync": len(mismatches) == 0,
            "outline_chapters": outline_chapters,
            "zotero_chapters": zotero_chapters,
            "scrivener_chapters": scrivener_chapters,
            "mismatches": mismatches,
            "recommendations": recommendations,
        }

    def list_chapters(self) -> Dict[str, Any]:
        """List all chapters from Scrivener structure.

        Returns:
            Dict with chapter list from Scrivener
        """
        scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
        if not scrivener_path or not Path(scrivener_path).exists():
            return {"error": "Scrivener project path not configured or doesn't exist"}

        try:
            parser = ScrivenerParser(scrivener_path)
            structure = parser.get_chapter_structure()
            return {
                "project_name": structure["project_name"],
                "chapter_count": len(structure["chapters"]),
                "chapters": structure["chapters"],
            }
        except Exception as e:
            logger.error(f"Error listing chapters: {e}")
            return {"error": str(e)}

    def _extract_chapters_from_outline(self) -> Dict[int, str]:
        """Extract chapter numbers and titles from outline.txt."""
        outline_path = Path("data/outline.txt")
        if not outline_path.exists():
            return {}

        content = outline_path.read_text()
        chapters = {}

        patterns = [
            r"[Cc]hapter\s+(\d+)[:\.]?\s*[:-]?\s*(.+)",
            r"^\s*(\d+)\.\s+(.+)",
        ]

        for line in content.split("\n"):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    num = int(match.group(1))
                    title = match.group(2).strip()
                    title = re.sub(r"\s*-\s*.+$", "", title).strip()
                    chapters[num] = title
                    break

        return chapters

    def _get_indexed_chapters(self, source_type: str) -> Dict[int, Dict]:
        """Get chapters from indexed data for given source type."""
        try:
            # Query all indexed data for this source type
            results = self.search(
                query="chapter content",
                filters={"source_type": source_type},
                limit=1000,
                score_threshold=0.0,
            )

            chapters = {}
            for result in results:
                meta = result["metadata"]
                chapter_num = meta.get("chapter_number")
                if chapter_num:
                    if chapter_num not in chapters:
                        chapters[chapter_num] = {
                            "title": meta.get("chapter_title", "Unknown"),
                            "chunk_count": 0,
                        }
                    chapters[chapter_num]["chunk_count"] += 1

            return chapters
        except Exception as e:
            logger.error(f"Error getting indexed chapters for {source_type}: {e}")
            return {}
