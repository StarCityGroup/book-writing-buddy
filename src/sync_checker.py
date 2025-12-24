"""Utility to check sync status between outline, Zotero, and Scrivener."""

import re
from pathlib import Path
from typing import Dict, List, Optional

from .vectordb.client import QdrantClient


class SyncChecker:
    """Check consistency between outline.txt, Zotero collections, and Scrivener structure."""

    def __init__(self, qdrant_client: Optional[QdrantClient] = None):
        """Initialize sync checker.

        Args:
            qdrant_client: Optional Qdrant client for querying indexed data
        """
        self.qdrant = qdrant_client or QdrantClient()
        self.outline_path = Path(__file__).parent.parent / "data" / "outline.txt"

    def check_sync_status(self) -> Dict:
        """Check sync status across all sources.

        Returns:
            Dict with sync status, mismatches, and recommendations
        """
        # Get chapter info from each source
        outline_chapters = self._extract_chapters_from_outline()
        zotero_chapters = self._get_zotero_chapters()
        scrivener_chapters = self._get_scrivener_chapters()

        # Compare
        mismatches = self._find_mismatches(
            outline_chapters, zotero_chapters, scrivener_chapters
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(mismatches)

        return {
            "in_sync": len(mismatches) == 0,
            "outline_chapters": outline_chapters,
            "zotero_chapters": zotero_chapters,
            "scrivener_chapters": scrivener_chapters,
            "mismatches": mismatches,
            "recommendations": recommendations,
        }

    def _extract_chapters_from_outline(self) -> Dict[int, str]:
        """Extract chapter numbers and titles from outline.txt.

        Returns:
            Dict mapping chapter number to title
        """
        if not self.outline_path.exists():
            return {}

        content = self.outline_path.read_text()
        chapters = {}

        # Match patterns like:
        # - Chapter 1: Title
        # - 1. Title
        # - Chapter 1. Title
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
                    # Clean up title (remove trailing dashes, extra info)
                    title = re.sub(r"\s*-\s*.+$", "", title).strip()
                    chapters[num] = title
                    break

        return chapters

    def _get_zotero_chapters(self) -> Dict[int, Dict]:
        """Get chapter info from Zotero collections via Qdrant metadata.

        Returns:
            Dict mapping chapter number to metadata
        """
        try:
            # Query Qdrant for ALL indexed Zotero content (no limit)
            results = self.qdrant.query_by_metadata(
                filter_dict={"source_type": "zotero"}, limit=None
            )

            chapters = {}
            for result in results:
                meta = result.get("metadata", {})
                chapter_num = meta.get("chapter_number")
                if chapter_num:
                    if chapter_num not in chapters:
                        chapters[chapter_num] = {
                            "title": meta.get("chapter_title", "Unknown"),
                            "source_count": 0,
                            "chunk_count": 0,
                        }
                    chapters[chapter_num]["chunk_count"] += 1

            return chapters
        except Exception:
            return {}

    def _get_scrivener_chapters(self) -> Dict[int, Dict]:
        """Get chapter info from Scrivener via Qdrant metadata.

        Returns:
            Dict mapping chapter number to metadata
        """
        try:
            # Query Qdrant for ALL indexed Scrivener content (no limit)
            results = self.qdrant.query_by_metadata(
                filter_dict={"source_type": "scrivener"}, limit=None
            )

            chapters = {}
            for result in results:
                meta = result.get("metadata", {})
                chapter_num = meta.get("chapter_number")
                if chapter_num:
                    if chapter_num not in chapters:
                        chapters[chapter_num] = {
                            "title": meta.get("title", "Unknown"),
                            "word_count": 0,
                            "chunk_count": 0,
                        }
                    chapters[chapter_num]["chunk_count"] += 1

            return chapters
        except Exception:
            return {}

    def _find_mismatches(
        self,
        outline_chapters: Dict[int, str],
        zotero_chapters: Dict[int, Dict],
        scrivener_chapters: Dict[int, Dict],
    ) -> List[Dict]:
        """Find mismatches between sources.

        Args:
            outline_chapters: Chapters from outline.txt
            zotero_chapters: Chapters from Zotero
            scrivener_chapters: Chapters from Scrivener (definitive source)

        Returns:
            List of mismatch descriptions
        """
        mismatches = []

        # Scrivener is the source of truth
        all_chapters = set(scrivener_chapters.keys())
        all_chapters.update(outline_chapters.keys())
        all_chapters.update(zotero_chapters.keys())

        for chapter_num in sorted(all_chapters):
            in_scrivener = chapter_num in scrivener_chapters
            in_zotero = chapter_num in zotero_chapters
            in_outline = chapter_num in outline_chapters

            # Missing from Scrivener (but exists elsewhere)
            if not in_scrivener and (in_zotero or in_outline):
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_scrivener",
                        "severity": "high",
                        "message": f"Chapter {chapter_num} exists in outline/Zotero but not in Scrivener",
                    }
                )

            # In Scrivener but missing from Zotero
            elif in_scrivener and not in_zotero:
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_zotero",
                        "severity": "medium",
                        "message": f"Chapter {chapter_num} exists in Scrivener but has no Zotero collection",
                    }
                )

            # In Scrivener but missing from outline
            elif in_scrivener and not in_outline:
                mismatches.append(
                    {
                        "chapter": chapter_num,
                        "type": "missing_from_outline",
                        "severity": "low",
                        "message": f"Chapter {chapter_num} exists in Scrivener but not in outline.txt",
                    }
                )

            # Title mismatches (if we could detect them reliably)
            # This is tricky because titles may be abbreviated differently

        return mismatches

    def _generate_recommendations(self, mismatches: List[Dict]) -> List[str]:
        """Generate recommendations based on mismatches.

        Args:
            mismatches: List of detected mismatches

        Returns:
            List of actionable recommendations
        """
        if not mismatches:
            return ["✓ All sources are in sync"]

        recommendations = []

        # Count by type
        by_type = {}
        for m in mismatches:
            by_type.setdefault(m["type"], []).append(m["chapter"])

        # Generate specific recommendations
        if "missing_from_zotero" in by_type:
            chapters = by_type["missing_from_zotero"]
            recommendations.append(
                f"Create Zotero collections for chapters: {', '.join(map(str, chapters))}"
            )

        if "missing_from_outline" in by_type:
            recommendations.append(
                "Update data/outline.txt to match your current Scrivener chapter structure"
            )

        if "missing_from_scrivener" in by_type:
            chapters = by_type["missing_from_scrivener"]
            recommendations.append(
                f"Chapters {', '.join(map(str, chapters))} may have been removed or renumbered in Scrivener. "
                "Consider removing/reorganizing corresponding Zotero collections."
            )

        # General advice
        recommendations.append(
            "\n💡 Remember: Scrivener is your definitive chapter structure. "
            "Organize Zotero and outline.txt to match it."
        )

        return recommendations

    def format_sync_report(self, status: Dict) -> str:
        """Format sync status as readable text.

        Args:
            status: Result from check_sync_status()

        Returns:
            Formatted report string
        """
        lines = ["# Sync Status Report\n"]

        if status["in_sync"]:
            lines.append("✓ **All sources are in sync**\n")
        else:
            lines.append("⚠️  **Sources are out of sync**\n")

        # Chapter counts
        lines.append("## Chapter Counts")
        lines.append(f"- Scrivener: {len(status['scrivener_chapters'])} chapters")
        lines.append(f"- Zotero: {len(status['zotero_chapters'])} chapters")
        lines.append(f"- Outline: {len(status['outline_chapters'])} chapters\n")

        # Mismatches
        if status["mismatches"]:
            lines.append("## Mismatches\n")
            for mismatch in status["mismatches"]:
                severity_emoji = {
                    "high": "🔴",
                    "medium": "🟡",
                    "low": "🔵",
                }
                emoji = severity_emoji.get(mismatch["severity"], "•")
                lines.append(f"{emoji} {mismatch['message']}")
            lines.append("")

        # Recommendations
        if status["recommendations"]:
            lines.append("## Recommendations\n")
            for rec in status["recommendations"]:
                lines.append(f"- {rec}")

        return "\n".join(lines)
