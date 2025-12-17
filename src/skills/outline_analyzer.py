"""Outline Generation & Structure Analysis Skill.

Analyze manuscript structure and generate chapter outlines.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()


class OutlineAnalyzer:
    """Analyze Scrivener project structure and generate outlines."""

    def __init__(self, scrivener_path: str, vectordb):
        """Initialize outline analyzer.

        Args:
            scrivener_path: Path to Scrivener project
            vectordb: Vector database client
        """
        self.scrivener_path = Path(scrivener_path)
        self.scrivx_path = self.scrivener_path / "project.scrivx"
        self.vectordb = vectordb

    def get_chapter_outline(self, chapter_number: int) -> Dict[str, Any]:
        """Generate outline for a specific chapter.

        Args:
            chapter_number: Chapter number

        Returns:
            Dict with chapter structure and outline
        """
        # Get Scrivener content for this chapter
        filters = {"chapter_number": chapter_number, "source_type": "scrivener"}
        chunks = self.vectordb.search("", filters=filters, limit=100)

        if not chunks:
            return {
                "chapter_number": chapter_number,
                "sections": [],
                "status": "no_content",
            }

        # Group chunks by file/section
        sections = defaultdict(lambda: {"chunks": [], "word_count": 0})

        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            file_path = metadata.get("file_path", "unknown")
            text = chunk.get("text", "")

            sections[file_path]["chunks"].append(text)
            sections[file_path]["word_count"] += len(text.split())

        # Create outline structure
        outline_sections = []
        for file_path, data in sections.items():
            # Extract section title from file path
            path_obj = Path(file_path)
            section_title = path_obj.stem if path_obj.stem else "Untitled Section"

            # Get first chunk as preview
            preview = data["chunks"][0][:200] if data["chunks"] else ""

            outline_sections.append(
                {
                    "title": section_title,
                    "word_count": data["word_count"],
                    "chunk_count": len(data["chunks"]),
                    "preview": preview,
                    "file_path": file_path,
                }
            )

        # Sort by file path to maintain order
        outline_sections.sort(key=lambda x: x["file_path"])

        total_words = sum(s["word_count"] for s in outline_sections)

        return {
            "chapter_number": chapter_number,
            "sections": outline_sections,
            "total_sections": len(outline_sections),
            "total_words": total_words,
            "status": "has_content",
        }

    def analyze_manuscript_structure(self) -> Dict[str, Any]:
        """Analyze structure across entire manuscript.

        Returns:
            Dict with manuscript-level structure analysis
        """
        # Get all Scrivener chunks
        all_chunks = self.vectordb.search(
            "", filters={"source_type": "scrivener"}, limit=10000
        )

        # Group by chapter
        chapter_stats = defaultdict(lambda: {"sections": set(), "word_count": 0})

        for chunk in all_chunks:
            metadata = chunk.get("metadata", {})
            ch_num = metadata.get("chapter_number")
            file_path = metadata.get("file_path")
            text = chunk.get("text", "")

            if ch_num:
                if file_path:
                    chapter_stats[ch_num]["sections"].add(file_path)
                chapter_stats[ch_num]["word_count"] += len(text.split())

        # Create structure report
        chapters = []
        for ch_num in sorted(chapter_stats.keys()):
            stats = chapter_stats[ch_num]
            chapters.append(
                {
                    "chapter": ch_num,
                    "sections": len(stats["sections"]),
                    "word_count": stats["word_count"],
                }
            )

        # Identify structural issues
        issues = []

        if not chapters:
            issues.append(
                {
                    "type": "no_content",
                    "severity": "high",
                    "description": "No Scrivener content found",
                }
            )
        else:
            avg_words = sum(c["word_count"] for c in chapters) / len(chapters)

            # Find chapters with uneven length
            for ch in chapters:
                if ch["word_count"] < avg_words * 0.3:
                    issues.append(
                        {
                            "type": "short_chapter",
                            "chapter": ch["chapter"],
                            "word_count": ch["word_count"],
                            "avg_words": round(avg_words),
                            "severity": "medium",
                        }
                    )
                elif ch["word_count"] > avg_words * 2:
                    issues.append(
                        {
                            "type": "long_chapter",
                            "chapter": ch["chapter"],
                            "word_count": ch["word_count"],
                            "avg_words": round(avg_words),
                            "severity": "low",
                        }
                    )

        return {
            "total_chapters": len(chapters),
            "chapters": chapters,
            "total_words": sum(c["word_count"] for c in chapters),
            "average_words_per_chapter": round(avg_words) if chapters else 0,
            "structural_issues": issues,
            "status": "analyzed",
        }

    def parse_scrivx(self) -> Optional[Dict[str, Any]]:
        """Parse Scrivener's project.scrivx file for detailed structure.

        Returns:
            Dict with project structure from XML, or None if file not found
        """
        if not self.scrivx_path.exists():
            logger.warning(f"Scrivx file not found: {self.scrivx_path}")
            return None

        try:
            tree = ET.parse(self.scrivx_path)
            root = tree.getroot()

            # Extract basic project info
            project_info = {
                "title": root.get("Title", "Unknown"),
                "modified": root.get("Modified", "Unknown"),
                "binder_items": [],
            }

            # Parse binder structure (document hierarchy)
            binder = root.find(".//Binder")
            if binder is not None:
                for item in binder.findall(".//BinderItem"):
                    project_info["binder_items"].append(
                        {
                            "id": item.get("ID"),
                            "type": item.get("Type"),
                            "title": item.findtext("Title", ""),
                        }
                    )

            return project_info

        except Exception as e:
            logger.error(f"Failed to parse scrivx: {e}")
            return None
