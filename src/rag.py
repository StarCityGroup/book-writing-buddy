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
        self.zotero_path = os.getenv("ZOTERO_PATH", "/Users/anthonytownsend/Zotero")
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
            filters: Optional filters
                (e.g., {'chapter_number': 9, 'source_type': 'zotero'})
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
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query with optional chapter filter
            if chapter:
                # Filter by collection matching chapter number
                query = """
                    SELECT DISTINCT
                        ia.annotationType,
                        ia.annotationText,
                        ia.annotationComment,
                        ia.annotationColor,
                        parent.itemID as parentItemID,
                        COALESCE(parentData.value, 'Unknown') as parentTitle,
                        coll.collectionName
                    FROM itemAnnotations ia
                    JOIN items annot ON ia.itemID = annot.itemID
                    JOIN items parent ON ia.parentItemID = parent.itemID
                    LEFT JOIN itemData parentData ON parent.itemID = parentData.itemID
                        AND parentData.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
                    LEFT JOIN itemDataValues ON parentData.valueID = itemDataValues.valueID
                    LEFT JOIN collectionItems ci ON parent.itemID = ci.itemID
                    LEFT JOIN collections coll ON ci.collectionID = coll.collectionID
                    WHERE coll.collectionName LIKE ?
                    ORDER BY parent.itemID, annot.dateAdded
                """
                # Match collections like "1. Chapter Title" or "Chapter 1"
                cursor.execute(query, (f"%{chapter}%",))
            else:
                # Get all annotations
                query = """
                    SELECT DISTINCT
                        ia.annotationType,
                        ia.annotationText,
                        ia.annotationComment,
                        ia.annotationColor,
                        parent.itemID as parentItemID,
                        COALESCE(parentData.value, 'Unknown') as parentTitle,
                        COALESCE(coll.collectionName, 'No Collection') as collectionName
                    FROM itemAnnotations ia
                    JOIN items annot ON ia.itemID = annot.itemID
                    JOIN items parent ON ia.parentItemID = parent.itemID
                    LEFT JOIN itemData parentData ON parent.itemID = parentData.itemID
                        AND parentData.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
                    LEFT JOIN itemDataValues ON parentData.valueID = itemDataValues.valueID
                    LEFT JOIN collectionItems ci ON parent.itemID = ci.itemID
                    LEFT JOIN collections coll ON ci.collectionID = coll.collectionID
                    ORDER BY parent.itemID, annot.dateAdded
                    LIMIT 500
                """
                cursor.execute(query)

            rows = cursor.fetchall()
            conn.close()

            # Organize annotations by source document
            annotations_by_source = {}
            for row in rows:
                parent_id = row["parentItemID"]
                parent_title = row["parentTitle"]

                if parent_id not in annotations_by_source:
                    annotations_by_source[parent_id] = {
                        "title": parent_title,
                        "collection": row["collectionName"],
                        "annotations": [],
                    }

                # Add annotation
                annotation = {
                    "type": row["annotationType"],
                    "text": row["annotationText"] or "",
                    "comment": row["annotationComment"] or "",
                    "color": row["annotationColor"] or "",
                }

                annotations_by_source[parent_id]["annotations"].append(annotation)

            # Convert to list format
            annotations_list = []
            for source_id, source_data in annotations_by_source.items():
                annotations_list.append(
                    {
                        "source_id": source_id,
                        "title": source_data["title"],
                        "collection": source_data["collection"],
                        "annotation_count": len(source_data["annotations"]),
                        "annotations": source_data["annotations"],
                    }
                )

            return {
                "chapter": chapter,
                "source_count": len(annotations_list),
                "total_annotations": sum(
                    s["annotation_count"] for s in annotations_list
                ),
                "sources": annotations_list,
            }

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                return {
                    "error": "Zotero database is locked. Please close Zotero and try again."
                }
            logger.error(f"Error querying Zotero annotations: {e}")
            return {"error": str(e)}
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
                    from datetime import timezone

                    # Parse timestamp (may be timezone-aware or naive)
                    dt = datetime.fromisoformat(ts)

                    # If naive, assume UTC (for backward compatibility)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    # Calculate age using UTC
                    now_utc = datetime.now(timezone.utc)
                    age = now_utc - dt

                    if age.days > 0:
                        formatted = f"{age.days} day{'s' if age.days > 1 else ''} ago"
                    elif age.seconds > 3600:
                        hours = age.seconds // 3600
                        formatted = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    elif age.seconds > 60:
                        minutes = age.seconds // 60
                        formatted = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
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
        zotero_results = [
            r for r in results if r["metadata"].get("source_type") == "zotero"
        ]
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
                        "message": (
                            f"Chapter {chapter_num} exists in Scrivener "
                            "but has no Zotero collection"
                        ),
                    }
                )
            elif in_scrivener and not in_outline:
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_outline",
                        "severity": "low",
                        "message": (
                            f"Chapter {chapter_num} exists in Scrivener "
                            "but not in outline.txt"
                        ),
                    }
                )
            elif not in_scrivener and (in_zotero or in_outline):
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_scrivener",
                        "severity": "high",
                        "message": (
                            f"Chapter {chapter_num} exists in outline/Zotero "
                            "but not in Scrivener"
                        ),
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
                "Update data/outline.txt to match your current "
                "Scrivener chapter structure"
            )
        if any(m["type"] == "missing_from_scrivener" for m in mismatches):
            chapters_list = [
                str(m["chapter"])
                for m in mismatches
                if m["type"] == "missing_from_scrivener"
            ]
            recommendations.append(
                f"Chapters {', '.join(chapters_list)} may have been "
                "removed or renumbered in Scrivener. "
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

    # ========================================================================
    # Cross-Chapter Analysis Methods
    # ========================================================================

    def find_cross_chapter_themes(
        self, keyword: str, min_chapters: int = 2
    ) -> Dict[str, Any]:
        """Track a theme or concept across multiple chapters.

        Args:
            keyword: Theme, concept, or search term to track
            min_chapters: Minimum number of chapters theme must appear in

        Returns:
            Dict with chapters containing the theme and relevant excerpts
        """
        # Search for the keyword across all chapters
        results = self.search(query=keyword, limit=100, score_threshold=0.6)

        # Group results by chapter
        chapters_dict = {}
        for result in results:
            meta = result["metadata"]
            chapter_num = meta.get("chapter_number")
            if not chapter_num:
                continue

            if chapter_num not in chapters_dict:
                chapters_dict[chapter_num] = {
                    "chapter_number": chapter_num,
                    "chapter_title": meta.get("chapter_title", "Unknown"),
                    "mentions": [],
                }

            chapters_dict[chapter_num]["mentions"].append(
                {
                    "text": result["text"][:300],
                    "score": result["score"],
                    "source": meta.get("title", "Unknown"),
                    "source_type": meta.get("source_type", "Unknown"),
                }
            )

        # Filter by minimum chapters threshold
        matching_chapters = [
            ch for ch in chapters_dict.values() if len(ch["mentions"]) > 0
        ]
        matching_chapters.sort(key=lambda x: x["chapter_number"])

        return {
            "keyword": keyword,
            "total_chapters": len(matching_chapters),
            "total_mentions": sum(len(ch["mentions"]) for ch in matching_chapters),
            "meets_threshold": len(matching_chapters) >= min_chapters,
            "chapters": matching_chapters,
        }

    def compare_chapters(self, chapter1: int, chapter2: int) -> Dict[str, Any]:
        """Compare research density and coverage between two chapters.

        Args:
            chapter1: First chapter number
            chapter2: Second chapter number

        Returns:
            Dict with comparison metrics
        """
        # Get info for both chapters
        info1 = self.get_chapter_info(chapter1)
        info2 = self.get_chapter_info(chapter2)

        # Calculate metrics
        chunks1 = info1.get("indexed_chunks", 0)
        chunks2 = info2.get("indexed_chunks", 0)

        zotero1 = info1.get("zotero", {})
        zotero2 = info2.get("zotero", {})

        scrivener1 = info1.get("scrivener", {})
        scrivener2 = info2.get("scrivener", {})

        # Research density (Zotero chunks per Scrivener word)
        words1 = scrivener1.get("estimated_words", 0)
        words2 = scrivener2.get("estimated_words", 0)

        density1 = zotero1.get("chunk_count", 0) / words1 if words1 > 0 else 0
        density2 = zotero2.get("chunk_count", 0) / words2 if words2 > 0 else 0

        return {
            "chapter1": {
                "number": chapter1,
                "total_chunks": chunks1,
                "zotero_sources": zotero1.get("source_count", 0),
                "zotero_chunks": zotero1.get("chunk_count", 0),
                "scrivener_words": words1,
                "research_density": density1,
            },
            "chapter2": {
                "number": chapter2,
                "total_chunks": chunks2,
                "zotero_sources": zotero2.get("source_count", 0),
                "zotero_chunks": zotero2.get("chunk_count", 0),
                "scrivener_words": words2,
                "research_density": density2,
            },
            "comparison": {
                "more_sources": (
                    chapter1
                    if zotero1.get("source_count", 0) > zotero2.get("source_count", 0)
                    else chapter2
                ),
                "more_research_dense": (chapter1 if density1 > density2 else chapter2),
                "density_ratio": (
                    density1 / density2 if density2 > 0 else float("inf")
                ),
            },
        }

    # ========================================================================
    # Source Diversity & Quality Methods
    # ========================================================================

    def analyze_source_diversity(self, chapter: int) -> Dict[str, Any]:
        """Analyze diversity of source types for a chapter.

        Args:
            chapter: Chapter number

        Returns:
            Dict with source type breakdown and diversity metrics
        """
        # Get all Zotero chunks for this chapter
        results = self.search(
            query="chapter content",
            filters={"chapter_number": chapter, "source_type": "zotero"},
            limit=1000,
            score_threshold=0.0,
        )

        if not results:
            return {
                "chapter": chapter,
                "total_sources": 0,
                "source_types": {},
                "diversity_score": 0,
            }

        # Count unique sources by title
        sources = {}
        for result in results:
            meta = result["metadata"]
            title = meta.get("title", "Unknown")
            item_type = meta.get("item_type", "Unknown")

            if title not in sources:
                sources[title] = {"type": item_type, "chunk_count": 0}
            sources[title]["chunk_count"] += 1

        # Group by item type
        type_counts = {}
        for source_info in sources.values():
            item_type = source_info["type"]
            type_counts[item_type] = type_counts.get(item_type, 0) + 1

        # Calculate diversity score (0-1, higher = more diverse)
        # Using Simpson's Diversity Index
        total = len(sources)
        if total <= 1:
            diversity_score = 0
        else:
            sum_squared = sum((count / total) ** 2 for count in type_counts.values())
            diversity_score = 1 - sum_squared

        # Find most and least used sources
        sorted_sources = sorted(
            sources.items(), key=lambda x: x[1]["chunk_count"], reverse=True
        )

        return {
            "chapter": chapter,
            "total_sources": total,
            "source_types": type_counts,
            "diversity_score": round(diversity_score, 2),
            "most_cited": [
                {"title": title, "chunks": info["chunk_count"]}
                for title, info in sorted_sources[:5]
            ],
            "least_cited": [
                {"title": title, "chunks": info["chunk_count"]}
                for title, info in sorted_sources[-5:]
            ],
        }

    def identify_key_sources(
        self, chapter: int, min_mentions: int = 3
    ) -> Dict[str, Any]:
        """Find most-referenced sources in a chapter.

        Args:
            chapter: Chapter number
            min_mentions: Minimum number of chunks to be considered "key"

        Returns:
            Dict with key sources and their usage statistics
        """
        # Get all chunks for this chapter
        results = self.search(
            query="chapter content",
            filters={"chapter_number": chapter},
            limit=1000,
            score_threshold=0.0,
        )

        # Count mentions per source
        sources = {}
        for result in results:
            meta = result["metadata"]
            title = meta.get("title", "Unknown")
            source_type = meta.get("source_type", "Unknown")

            if title not in sources:
                sources[title] = {
                    "title": title,
                    "source_type": source_type,
                    "chunk_count": 0,
                    "item_type": meta.get("item_type", "Unknown"),
                }
            sources[title]["chunk_count"] += 1

        # Filter by minimum mentions
        key_sources = [
            source
            for source in sources.values()
            if source["chunk_count"] >= min_mentions
        ]
        key_sources.sort(key=lambda x: x["chunk_count"], reverse=True)

        return {
            "chapter": chapter,
            "total_sources": len(sources),
            "key_sources_count": len(key_sources),
            "threshold": min_mentions,
            "key_sources": key_sources,
        }

    # ========================================================================
    # Export & Summarization Methods
    # ========================================================================

    def export_chapter_summary(self, chapter: int, format: str = "markdown") -> str:
        """Export formatted summary of research for a chapter.

        Args:
            chapter: Chapter number
            format: Output format ('markdown', 'text', or 'json')

        Returns:
            Formatted summary string
        """
        # Get comprehensive chapter info
        info = self.get_chapter_info(chapter)
        diversity = self.analyze_source_diversity(chapter)
        key_sources = self.identify_key_sources(chapter)

        if format == "json":
            import json

            return json.dumps(
                {
                    "chapter": chapter,
                    "info": info,
                    "diversity": diversity,
                    "key_sources": key_sources,
                },
                indent=2,
            )

        # Build markdown/text summary
        lines = []
        lines.append(f"# Chapter {chapter} Research Summary")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append(f"- Total indexed chunks: {info.get('indexed_chunks', 0)}")

        zotero = info.get("zotero", {})
        if zotero:
            lines.append(
                f"- Zotero sources: {zotero.get('source_count', 0)} "
                f"({zotero.get('chunk_count', 0)} chunks)"
            )

        scrivener = info.get("scrivener", {})
        if scrivener:
            lines.append(
                f"- Draft status: ~{scrivener.get('estimated_words', 0)} words"
            )

        lines.append("")

        # Source diversity
        lines.append("## Source Diversity")
        lines.append(
            f"- Diversity score: {diversity.get('diversity_score', 0):.2f} "
            f"(0=homogeneous, 1=diverse)"
        )
        lines.append(f"- Total unique sources: {diversity.get('total_sources', 0)}")

        source_types = diversity.get("source_types", {})
        if source_types:
            lines.append("- Source types:")
            for item_type, count in sorted(
                source_types.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  - {item_type}: {count}")

        lines.append("")

        # Key sources
        lines.append("## Key Sources")
        key_srcs = key_sources.get("key_sources", [])
        if key_srcs:
            threshold = key_sources.get("threshold", 3)
            lines.append(f"Found {len(key_srcs)} sources with {threshold}+ mentions:")
            for src in key_srcs[:10]:  # Top 10
                lines.append(
                    f"- **{src['title']}** ({src['item_type']}): "
                    f"{src['chunk_count']} chunks"
                )
        else:
            lines.append("No key sources identified.")

        lines.append("")

        # Most cited sources
        most_cited = diversity.get("most_cited", [])
        if most_cited:
            lines.append("## Most Cited Sources")
            for src in most_cited:
                lines.append(f"- {src['title']}: {src['chunks']} chunks")

        lines.append("")
        lines.append("---")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        output = "\n".join(lines)

        if format == "text":
            # Strip markdown formatting for plain text
            output = output.replace("**", "").replace("##", "").replace("#", "")

        return output

    def generate_bibliography(
        self, chapter: Optional[int] = None, style: str = "apa"
    ) -> List[Dict[str, Any]]:
        """Generate formatted bibliography from Zotero sources.

        Args:
            chapter: Chapter number (None for all chapters)
            style: Citation style ('apa', 'mla', 'chicago', or 'raw')

        Returns:
            List of bibliography entries with source info
        """
        # Get all Zotero sources for the chapter(s)
        filters = {"source_type": "zotero"}
        if chapter:
            filters["chapter_number"] = chapter

        results = self.search(
            query="bibliography sources",
            filters=filters,
            limit=1000,
            score_threshold=0.0,
        )

        # Extract unique sources
        sources = {}
        for result in results:
            meta = result["metadata"]
            title = meta.get("title", "Unknown")

            if title not in sources:
                sources[title] = {
                    "title": title,
                    "item_type": meta.get("item_type", "Unknown"),
                    "authors": meta.get("authors", ""),
                    "year": meta.get("year", ""),
                    "publisher": meta.get("publisher", ""),
                    "url": meta.get("url", ""),
                    "doi": meta.get("doi", ""),
                    "chapters": set(),
                }

            chapter_num = meta.get("chapter_number")
            if chapter_num:
                sources[title]["chapters"].add(chapter_num)

        # Convert to list and sort
        bibliography = []
        for source in sources.values():
            source["chapters"] = sorted(list(source["chapters"]))

            # Format citation based on style
            if style == "apa":
                citation = self._format_apa_citation(source)
            elif style == "mla":
                citation = self._format_mla_citation(source)
            elif style == "chicago":
                citation = self._format_chicago_citation(source)
            else:  # raw
                citation = source["title"]

            bibliography.append(
                {
                    "citation": citation,
                    "title": source["title"],
                    "type": source["item_type"],
                    "chapters": source["chapters"],
                    "raw": source,
                }
            )

        # Sort alphabetically by title
        bibliography.sort(key=lambda x: x["title"].lower())

        return bibliography

    def _format_apa_citation(self, source: Dict) -> str:
        """Format a source as APA citation."""
        parts = []

        # Authors
        authors = source.get("authors", "")
        if authors:
            parts.append(authors)

        # Year
        year = source.get("year", "")
        if year:
            parts.append(f"({year}).")
        else:
            parts.append("(n.d.).")

        # Title
        title = source.get("title", "Untitled")
        parts.append(f"*{title}*.")

        # Publisher
        publisher = source.get("publisher", "")
        if publisher:
            parts.append(publisher + ".")

        # DOI or URL
        doi = source.get("doi", "")
        url = source.get("url", "")
        if doi:
            parts.append(f"https://doi.org/{doi}")
        elif url:
            parts.append(url)

        return " ".join(parts)

    def _format_mla_citation(self, source: Dict) -> str:
        """Format a source as MLA citation."""
        parts = []

        # Authors
        authors = source.get("authors", "")
        if authors:
            parts.append(f"{authors}.")

        # Title
        title = source.get("title", "Untitled")
        parts.append(f'"{title}."')

        # Publisher and year
        publisher = source.get("publisher", "")
        year = source.get("year", "")
        if publisher and year:
            parts.append(f"{publisher}, {year}.")
        elif year:
            parts.append(f"{year}.")

        return " ".join(parts)

    def _format_chicago_citation(self, source: Dict) -> str:
        """Format a source as Chicago citation."""
        parts = []

        # Authors
        authors = source.get("authors", "")
        if authors:
            parts.append(f"{authors}.")

        # Title
        title = source.get("title", "Untitled")
        parts.append(f"*{title}*.")

        # Publisher and year
        publisher = source.get("publisher", "")
        year = source.get("year", "")
        if publisher and year:
            parts.append(f"{publisher}, {year}.")

        return " ".join(parts)

    # ========================================================================
    # Research Timeline Methods
    # ========================================================================

    def get_recent_additions(self, days: int = 7) -> Dict[str, Any]:
        """Get recently indexed research materials.

        Args:
            days: Number of days to look back

        Returns:
            Dict with recent additions grouped by source type and chapter
        """
        # Get index timestamps
        stats = self.get_index_stats()
        raw_timestamps = stats.get("raw_timestamps", {})

        # Calculate cutoff time
        cutoff = datetime.now() - __import__("datetime").timedelta(days=days)

        recent = {"cutoff_date": cutoff.isoformat(), "sources": {}}

        for source_type, ts in raw_timestamps.items():
            if ts:
                try:
                    indexed_time = datetime.fromisoformat(ts)
                    if indexed_time >= cutoff:
                        recent["sources"][source_type] = {
                            "indexed_at": ts,
                            "age_hours": int(
                                (datetime.now() - indexed_time).seconds / 3600
                            ),
                            "is_recent": True,
                        }
                except Exception:
                    continue

        return recent

    def get_research_timeline(self, chapter: Optional[int] = None) -> Dict[str, Any]:
        """Get timeline of when research was collected.

        Args:
            chapter: Optional chapter number to filter by

        Returns:
            Dict with timeline information
        """
        # Get all indexed data
        filters = {}
        if chapter:
            filters["chapter_number"] = chapter

        results = self.search(
            query="timeline", filters=filters, limit=1000, score_threshold=0.0
        )

        # Extract dates from metadata
        timeline = {}
        for result in results:
            meta = result["metadata"]

            # Try to get date added (if available in metadata)
            date_added = meta.get("date_added") or meta.get("indexed_at")
            if not date_added:
                continue

            try:
                date_obj = datetime.fromisoformat(date_added.replace("Z", "+00:00"))
                month_key = date_obj.strftime("%Y-%m")

                if month_key not in timeline:
                    timeline[month_key] = {
                        "month": month_key,
                        "count": 0,
                        "chapters": set(),
                        "sources": set(),
                    }

                timeline[month_key]["count"] += 1
                chapter_num = meta.get("chapter_number")
                if chapter_num:
                    timeline[month_key]["chapters"].add(chapter_num)
                title = meta.get("title")
                if title:
                    timeline[month_key]["sources"].add(title)

            except Exception:
                continue

        # Convert sets to sorted lists
        timeline_list = []
        for month_data in sorted(timeline.values(), key=lambda x: x["month"]):
            month_data["chapters"] = sorted(list(month_data["chapters"]))
            month_data["sources"] = list(month_data["sources"])[
                :5
            ]  # Limit to 5 examples
            timeline_list.append(month_data)

        return {
            "chapter": chapter,
            "total_periods": len(timeline_list),
            "timeline": timeline_list,
        }

    # ========================================================================
    # Smart Recommendations
    # ========================================================================

    def get_scrivener_summary(self) -> Dict[str, Any]:
        """Get detailed breakdown of indexed Scrivener documents per chapter.

        Returns:
            Dict with Scrivener indexing statistics per chapter
        """
        # Get all Scrivener results
        results = self.search(
            query="scrivener content",
            filters={"source_type": "scrivener"},
            limit=10000,
            score_threshold=0.0,
        )

        if not results:
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "total_words": 0,
                "chapters": {},
                "message": "No Scrivener documents have been indexed yet",
            }

        # Group by chapter
        chapters = {}
        unassigned_docs = []
        total_words = 0

        for result in results:
            meta = result["metadata"]
            chapter_num = meta.get("chapter_number")
            doc_type = meta.get("doc_type", "unknown")
            word_count = len(result["text"].split())
            total_words += word_count

            if chapter_num:
                if chapter_num not in chapters:
                    chapters[chapter_num] = {
                        "chapter_number": chapter_num,
                        "chapter_title": meta.get("chapter_title", "Unknown"),
                        "total_chunks": 0,
                        "total_words": 0,
                        "doc_types": {},
                        "documents": set(),
                    }

                chapters[chapter_num]["total_chunks"] += 1
                chapters[chapter_num]["total_words"] += word_count

                # Count doc types
                if doc_type not in chapters[chapter_num]["doc_types"]:
                    chapters[chapter_num]["doc_types"][doc_type] = 0
                chapters[chapter_num]["doc_types"][doc_type] += 1

                # Track unique document IDs
                doc_id = meta.get("scrivener_id")
                if doc_id:
                    chapters[chapter_num]["documents"].add(doc_id)
            else:
                # Track unassigned documents
                unassigned_docs.append(
                    {
                        "file_path": meta.get("file_path", "Unknown"),
                        "doc_type": doc_type,
                        "words": word_count,
                    }
                )

        # Convert documents sets to counts
        chapter_list = []
        for ch in sorted(chapters.values(), key=lambda x: x["chapter_number"]):
            ch["document_count"] = len(ch["documents"])
            del ch["documents"]  # Remove the set, just keep the count
            chapter_list.append(ch)

        return {
            "total_chapters": len(chapter_list),
            "total_chunks": len(results),
            "total_words": total_words,
            "total_documents": sum(ch["document_count"] for ch in chapter_list),
            "chapters": chapter_list,
            "unassigned_count": len(unassigned_docs),
            "unassigned_docs": unassigned_docs[:20],  # Limit to first 20
        }

    def suggest_related_research(self, chapter: int, limit: int = 5) -> Dict[str, Any]:
        """Suggest research from other chapters that might be relevant.

        Args:
            chapter: Chapter number to find suggestions for
            limit: Maximum number of suggestions

        Returns:
            Dict with suggested research from other chapters
        """
        # Get a sample of content from the target chapter
        chapter_results = self.search(
            query="chapter content",
            filters={"chapter_number": chapter},
            limit=10,
            score_threshold=0.0,
        )

        if not chapter_results:
            return {
                "chapter": chapter,
                "suggestions": [],
                "message": "No research found for this chapter",
            }

        # Build a representative query from chapter content
        # Use the most representative chunks
        sample_texts = [r["text"][:200] for r in chapter_results[:3]]
        query = " ".join(sample_texts)

        # Search for similar content in OTHER chapters
        all_results = self.search(query=query, limit=50, score_threshold=0.65)

        # Filter out results from the same chapter
        related = []
        for result in all_results:
            meta = result["metadata"]
            other_chapter = meta.get("chapter_number")

            if other_chapter and other_chapter != chapter:
                related.append(
                    {
                        "chapter": other_chapter,
                        "chapter_title": meta.get("chapter_title", "Unknown"),
                        "source": meta.get("title", "Unknown"),
                        "source_type": meta.get("source_type", "Unknown"),
                        "relevance": result["score"],
                        "text_preview": result["text"][:200],
                    }
                )

            if len(related) >= limit:
                break

        # Group by chapter
        by_chapter = {}
        for item in related:
            ch = item["chapter"]
            if ch not in by_chapter:
                by_chapter[ch] = {
                    "chapter": ch,
                    "chapter_title": item["chapter_title"],
                    "items": [],
                }
            by_chapter[ch]["items"].append(item)

        suggestions = sorted(
            by_chapter.values(), key=lambda x: len(x["items"]), reverse=True
        )

        return {
            "chapter": chapter,
            "suggestions_count": len(related),
            "chapters_with_suggestions": len(suggestions),
            "suggestions": suggestions,
        }
