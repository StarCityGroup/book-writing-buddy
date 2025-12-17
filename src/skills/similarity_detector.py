"""Similarity & Duplication Detector Skill.

Find duplicate or highly similar content across indexed materials.
"""

from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class SimilarityDetector:
    """Detect similar and duplicate content using vector search."""

    def __init__(self, vectordb):
        """Initialize similarity detector.

        Args:
            vectordb: Vector database client
        """
        self.vectordb = vectordb

    def find_similar_content(
        self, text: str, threshold: float = 0.85, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find content similar to given text.

        Args:
            text: Text to find similarities for
            threshold: Similarity threshold (0-1), default 0.85
            limit: Maximum number of results

        Returns:
            List of similar chunks with scores
        """
        results = self.vectordb.search(text, limit=limit, score_threshold=threshold)

        similar_items = []
        for result in results:
            similar_items.append(
                {
                    "text": result["text"],
                    "similarity_score": result["score"],
                    "metadata": result["metadata"],
                }
            )

        return similar_items

    def detect_duplicates_in_chapter(
        self, chapter_number: int, threshold: float = 0.9
    ) -> Dict[str, Any]:
        """Detect near-duplicate content within a chapter.

        Args:
            chapter_number: Chapter number to analyze
            threshold: Similarity threshold for considering duplicates (0.9 = 90% similar)

        Returns:
            Dict with duplicate groups and statistics
        """
        # Get all chunks for this chapter
        filters = {"chapter_number": chapter_number}
        chunks = self.vectordb.search("", filters=filters, limit=500)

        if len(chunks) < 2:
            return {
                "chapter_number": chapter_number,
                "duplicate_groups": [],
                "total_duplicates": 0,
                "status": "insufficient_content",
            }

        # Find duplicates by comparing each chunk
        duplicate_groups = []
        processed = set()

        for i, chunk in enumerate(chunks):
            if i in processed:
                continue

            # Search for similar chunks
            similar = self.vectordb.search(
                chunk["text"], limit=10, score_threshold=threshold
            )

            # Filter to same chapter and not self
            similar_in_chapter = [
                s
                for s in similar
                if s.get("metadata", {}).get("chapter_number") == chapter_number
                and s["text"] != chunk["text"]
            ]

            if similar_in_chapter:
                group = {
                    "original": {
                        "text": chunk["text"][:200],
                        "metadata": chunk["metadata"],
                    },
                    "duplicates": [
                        {
                            "text": s["text"][:200],
                            "similarity": s["score"],
                            "metadata": s["metadata"],
                        }
                        for s in similar_in_chapter
                    ],
                    "count": len(similar_in_chapter) + 1,
                }

                duplicate_groups.append(group)
                processed.add(i)

        return {
            "chapter_number": chapter_number,
            "duplicate_groups": duplicate_groups,
            "total_duplicates": sum(g["count"] - 1 for g in duplicate_groups),
            "duplicate_group_count": len(duplicate_groups),
            "status": "has_duplicates" if duplicate_groups else "no_duplicates",
        }

    def find_redundant_sources(
        self, chapter_number: Optional[int] = None, threshold: float = 0.85
    ) -> Dict[str, Any]:
        """Identify sources with redundant/overlapping information.

        Args:
            chapter_number: Optional chapter to analyze
            threshold: Similarity threshold

        Returns:
            Dict with redundant source pairs
        """
        filters = {}
        if chapter_number:
            filters["chapter_number"] = chapter_number

        filters["source_type"] = "zotero"

        chunks = self.vectordb.search("", filters=filters, limit=1000)

        # Group chunks by source
        by_source = {}
        for chunk in chunks:
            item_id = chunk.get("metadata", {}).get("item_id")
            if item_id:
                if item_id not in by_source:
                    by_source[item_id] = []
                by_source[item_id].append(chunk)

        # Compare sources
        source_ids = list(by_source.keys())
        redundant_pairs = []

        for i, source_a in enumerate(source_ids):
            for source_b in source_ids[i + 1 :]:
                # Compare chunks from both sources
                similarity_scores = []

                for chunk_a in by_source[source_a][:5]:  # Sample first 5 chunks
                    similar = self.vectordb.search(
                        chunk_a["text"], limit=5, score_threshold=threshold
                    )

                    for result in similar:
                        if result.get("metadata", {}).get("item_id") == source_b:
                            similarity_scores.append(result["score"])

                # If many high-similarity matches, sources may be redundant
                if len(similarity_scores) >= 3:
                    avg_similarity = sum(similarity_scores) / len(similarity_scores)

                    redundant_pairs.append(
                        {
                            "source_a": {
                                "item_id": source_a,
                                "title": by_source[source_a][0]
                                .get("metadata", {})
                                .get("title", "Unknown"),
                            },
                            "source_b": {
                                "item_id": source_b,
                                "title": by_source[source_b][0]
                                .get("metadata", {})
                                .get("title", "Unknown"),
                            },
                            "similarity_score": avg_similarity,
                            "match_count": len(similarity_scores),
                        }
                    )

        return {
            "chapter_number": chapter_number,
            "total_sources": len(source_ids),
            "redundant_pairs": sorted(
                redundant_pairs, key=lambda x: x["similarity_score"], reverse=True
            ),
            "status": "has_redundancy" if redundant_pairs else "no_redundancy",
        }

    def detect_potential_plagiarism(
        self, draft_text: str, threshold: float = 0.92
    ) -> List[Dict[str, Any]]:
        """Check if draft text is too similar to source materials.

        Args:
            draft_text: Text from Scrivener draft
            threshold: High threshold for plagiarism detection (default 0.92)

        Returns:
            List of suspiciously similar source chunks
        """
        # Search for very similar content in Zotero sources
        results = self.vectordb.search(
            draft_text,
            filters={"source_type": "zotero"},
            limit=10,
            score_threshold=threshold,
        )

        matches = []
        for result in results:
            matches.append(
                {
                    "source_text": result["text"][:300],
                    "similarity_score": result["score"],
                    "source_title": result.get("metadata", {}).get("title", "Unknown"),
                    "item_id": result.get("metadata", {}).get("item_id"),
                    "warning": "Very high similarity - verify proper citation or paraphrasing",
                }
            )

        return matches
