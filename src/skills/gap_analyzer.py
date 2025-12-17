"""Research Gap Detector Skill.

Identify areas needing more research by analyzing source density and coverage.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class ResearchGapDetector:
    """Detect research gaps by analyzing source coverage."""

    def __init__(self, vectordb):
        """Initialize gap detector.

        Args:
            vectordb: Vector database client
        """
        self.vectordb = vectordb

    def identify_gaps(self, chapter_number: Optional[int] = None) -> Dict[str, Any]:
        """Identify research gaps.

        Args:
            chapter_number: Optional chapter to analyze, or None for all chapters

        Returns:
            Dict with gap analysis results
        """
        if chapter_number:
            return self._analyze_chapter_gaps(chapter_number)
        else:
            return self._analyze_manuscript_gaps()

    def _analyze_chapter_gaps(self, chapter_number: int) -> Dict[str, Any]:
        """Analyze research gaps for a specific chapter."""
        # Get all chunks for this chapter
        filters = {"chapter_number": chapter_number}

        zotero_chunks = self.vectordb.search(
            "", filters={**filters, "source_type": "zotero"}, limit=1000
        )

        scrivener_chunks = self.vectordb.search(
            "", filters={**filters, "source_type": "scrivener"}, limit=1000
        )

        # Calculate metrics
        unique_sources = set()
        for chunk in zotero_chunks:
            item_id = chunk.get("metadata", {}).get("item_id")
            if item_id:
                unique_sources.add(item_id)

        # Identify potential gaps
        gaps = []

        # Gap 1: Low source count
        if len(unique_sources) < 5:
            gaps.append(
                {
                    "type": "low_source_count",
                    "severity": "high",
                    "description": f"Only {len(unique_sources)} unique sources found. "
                    "Consider adding more research materials.",
                }
            )

        # Gap 2: Few chunks (sparse coverage)
        if len(zotero_chunks) < 20:
            gaps.append(
                {
                    "type": "sparse_coverage",
                    "severity": "medium",
                    "description": f"Only {len(zotero_chunks)} text chunks indexed. "
                    "May need more detailed sources.",
                }
            )

        # Gap 3: No draft content
        if len(scrivener_chunks) == 0:
            gaps.append(
                {
                    "type": "no_draft",
                    "severity": "low",
                    "description": "No Scrivener draft found for this chapter.",
                }
            )

        return {
            "chapter_number": chapter_number,
            "unique_sources": len(unique_sources),
            "zotero_chunks": len(zotero_chunks),
            "scrivener_chunks": len(scrivener_chunks),
            "gaps": gaps,
            "status": "needs_attention" if gaps else "well_researched",
        }

    def _analyze_manuscript_gaps(self) -> Dict[str, Any]:
        """Analyze research gaps across entire manuscript."""
        # Query all chunks and group by chapter
        all_chunks = self.vectordb.search("", limit=10000)

        chapter_stats = defaultdict(
            lambda: {"zotero": 0, "scrivener": 0, "sources": set()}
        )

        for chunk in all_chunks:
            metadata = chunk.get("metadata", {})
            ch_num = metadata.get("chapter_number")
            source_type = metadata.get("source_type")
            item_id = metadata.get("item_id")

            if ch_num:
                if source_type == "zotero":
                    chapter_stats[ch_num]["zotero"] += 1
                    if item_id:
                        chapter_stats[ch_num]["sources"].add(item_id)
                elif source_type == "scrivener":
                    chapter_stats[ch_num]["scrivener"] += 1

        # Calculate average source density
        chapters = list(chapter_stats.keys())
        if not chapters:
            return {
                "total_chapters": 0,
                "gaps": [],
                "status": "no_data",
            }

        avg_sources = sum(
            len(stats["sources"]) for stats in chapter_stats.values()
        ) / len(chapters)
        avg_chunks = sum(stats["zotero"] for stats in chapter_stats.values()) / len(
            chapters
        )

        # Identify chapters below average
        weak_chapters = []
        for ch_num, stats in chapter_stats.items():
            source_count = len(stats["sources"])
            chunk_count = stats["zotero"]

            if source_count < avg_sources * 0.5:  # Less than 50% of average
                weak_chapters.append(
                    {
                        "chapter": ch_num,
                        "sources": source_count,
                        "avg_sources": round(avg_sources, 1),
                        "severity": "high",
                        "reason": "significantly below average source count",
                    }
                )
            elif chunk_count < avg_chunks * 0.5:
                weak_chapters.append(
                    {
                        "chapter": ch_num,
                        "chunks": chunk_count,
                        "avg_chunks": round(avg_chunks, 1),
                        "severity": "medium",
                        "reason": "below average research coverage",
                    }
                )

        return {
            "total_chapters": len(chapters),
            "average_sources_per_chapter": round(avg_sources, 1),
            "average_chunks_per_chapter": round(avg_chunks, 1),
            "weak_chapters": sorted(weak_chapters, key=lambda x: x["chapter"]),
            "gaps_found": len(weak_chapters),
            "status": "has_gaps" if weak_chapters else "well_balanced",
        }

    def suggest_search_terms(self, chapter_number: int) -> List[str]:
        """Suggest search terms based on chapter content gaps.

        Args:
            chapter_number: Chapter to analyze

        Returns:
            List of suggested search terms
        """
        # Get existing content
        filters = {"chapter_number": chapter_number, "source_type": "scrivener"}
        draft_chunks = self.vectordb.search("", filters=filters, limit=50)

        if not draft_chunks:
            return ["No draft content to analyze"]

        # Extract key terms from draft (simple word frequency)
        # This is a simplified version - could use NLP for better results
        text = " ".join(chunk["text"] for chunk in draft_chunks[:10])

        # Simple keyword extraction (could be enhanced)
        words = text.lower().split()
        common_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
        }

        word_freq = defaultdict(int)
        for word in words:
            if len(word) > 3 and word not in common_words:
                word_freq[word] += 1

        # Get top terms
        top_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        return [term for term, _ in top_terms]
