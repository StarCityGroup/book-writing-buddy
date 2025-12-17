"""Annotation & Note Aggregator Skill.

Collect and organize Zotero annotations and notes.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class AnnotationAggregator:
    """Extract and aggregate annotations from Zotero."""

    def __init__(self, zotero_db_path: str):
        """Initialize annotation aggregator.

        Args:
            zotero_db_path: Path to Zotero SQLite database
        """
        self.db_path = Path(zotero_db_path)

    def get_annotations(
        self,
        chapter_number: Optional[int] = None,
        source_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get annotations from Zotero database.

        Args:
            chapter_number: Optional chapter number to filter by
            source_id: Optional Zotero item ID to filter by

        Returns:
            List of annotation dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Query annotations (highlights and notes)
        # Zotero stores annotations in itemAnnotations table
        query = """
            SELECT
                ia.annotationText,
                ia.annotationComment,
                ia.annotationColor,
                ia.annotationType,
                i.itemID,
                pi.itemID as parentItemID,
                COALESCE(title_val.value, 'Untitled') as parent_title
            FROM itemAnnotations ia
            JOIN items i ON ia.itemID = i.itemID
            JOIN items pi ON ia.parentItemID = pi.itemID
            LEFT JOIN itemData title_data ON pi.itemID = title_data.itemID AND title_data.fieldID = 1
            LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
        """

        params = []
        if source_id:
            query += " WHERE ia.parentItemID = ?"
            params.append(source_id)

        cursor.execute(query, params)

        annotations = []
        for row in cursor.fetchall():
            (
                text,
                comment,
                color,
                ann_type,
                item_id,
                parent_id,
                parent_title,
            ) = row

            annotations.append(
                {
                    "annotation_id": item_id,
                    "source_id": parent_id,
                    "source_title": parent_title,
                    "text": text,
                    "comment": comment,
                    "color": color,
                    "type": ann_type,
                }
            )

        # Also get standalone notes
        query = """
            SELECT
                n.note,
                i.itemID,
                pi.itemID as parentItemID,
                COALESCE(title_val.value, 'Untitled') as parent_title
            FROM itemNotes n
            JOIN items i ON n.itemID = i.itemID
            LEFT JOIN items pi ON n.parentItemID = pi.itemID
            LEFT JOIN itemData title_data ON pi.itemID = title_data.itemID AND title_data.fieldID = 1
            LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
            WHERE n.note IS NOT NULL AND n.note != ''
        """

        params = []
        if source_id:
            query += " AND n.parentItemID = ?"
            params.append(source_id)

        cursor.execute(query, params)

        for row in cursor.fetchall():
            note_html, item_id, parent_id, parent_title = row

            # Strip HTML tags for plain text (simple approach)
            import re

            note_text = re.sub(r"<[^>]+>", "", note_html)

            annotations.append(
                {
                    "annotation_id": item_id,
                    "source_id": parent_id,
                    "source_title": parent_title if parent_id else "Standalone Note",
                    "text": note_text,
                    "comment": None,
                    "color": None,
                    "type": "note",
                }
            )

        conn.close()

        # Filter by chapter if requested
        if chapter_number:
            annotations = self._filter_by_chapter(annotations, chapter_number)

        return annotations

    def _filter_by_chapter(
        self, annotations: List[Dict[str, Any]], chapter_number: int
    ) -> List[Dict[str, Any]]:
        """Filter annotations by chapter using collection membership.

        Args:
            annotations: List of annotation dicts
            chapter_number: Chapter number to filter by

        Returns:
            Filtered list of annotations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all items in collections matching chapter number
        query = """
            SELECT DISTINCT i.itemID
            FROM collectionItems ci
            JOIN items i ON ci.itemID = i.itemID
            JOIN collections c ON ci.collectionID = c.collectionID
            WHERE c.collectionName LIKE ?
        """

        cursor.execute(query, (f"{chapter_number}.%",))
        chapter_item_ids = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Filter annotations
        filtered = [ann for ann in annotations if ann["source_id"] in chapter_item_ids]

        return filtered

    def get_annotations_summary(
        self, chapter_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for annotations.

        Args:
            chapter_number: Optional chapter number

        Returns:
            Dict with annotation statistics
        """
        annotations = self.get_annotations(chapter_number=chapter_number)

        # Count by type
        by_type = {}
        for ann in annotations:
            ann_type = ann["type"]
            by_type[ann_type] = by_type.get(ann_type, 0) + 1

        # Count by source
        by_source = {}
        for ann in annotations:
            source_title = ann["source_title"]
            by_source[source_title] = by_source.get(source_title, 0) + 1

        return {
            "total_annotations": len(annotations),
            "by_type": by_type,
            "by_source": by_source,
            "sources_with_annotations": len(by_source),
        }

    def create_research_notes_digest(self, chapter_number: int) -> str:
        """Create a formatted digest of research notes for a chapter.

        Args:
            chapter_number: Chapter number

        Returns:
            Formatted markdown string with all annotations
        """
        annotations = self.get_annotations(chapter_number=chapter_number)

        if not annotations:
            return (
                f"# Research Notes - Chapter {chapter_number}\n\nNo annotations found."
            )

        digest = [f"# Research Notes - Chapter {chapter_number}\n"]

        # Group by source
        by_source = {}
        for ann in annotations:
            source = ann["source_title"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(ann)

        # Format each source
        for source_title in sorted(by_source.keys()):
            anns = by_source[source_title]
            digest.append(f"\n## {source_title}\n")

            for ann in anns:
                if ann["type"] == "note":
                    digest.append(f"**Note:**\n{ann['text']}\n")
                else:
                    if ann["text"]:
                        digest.append(f"> {ann['text']}\n")
                    if ann["comment"]:
                        digest.append(f"**Comment:** {ann['comment']}\n")

                digest.append("")  # Blank line

        return "\n".join(digest)
