"""Citation Extraction & Management Skill.

Extract and format citations from Zotero items for use in manuscript.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()


class CitationManager:
    """Extract and format citations from Zotero database."""

    def __init__(self, zotero_db_path: str):
        """Initialize citation manager.

        Args:
            zotero_db_path: Path to Zotero SQLite database
        """
        self.db_path = Path(zotero_db_path)

    def get_item_metadata(self, item_id: int) -> Dict[str, Any]:
        """Get full bibliographic metadata for Zotero item.

        Args:
            item_id: Zotero item ID

        Returns:
            Dict with all item metadata (title, authors, date, etc.)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Query item fields (title, date, publication, etc.)
        query = """
            SELECT f.fieldName, v.value
            FROM itemData id
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues v ON id.valueID = v.valueID
            WHERE id.itemID = ?
        """
        cursor.execute(query, (item_id,))

        metadata = dict(cursor.fetchall())

        # Get item type
        query = """
            SELECT it.typeName
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE i.itemID = ?
        """
        cursor.execute(query, (item_id,))
        result = cursor.fetchone()
        if result:
            metadata["itemType"] = result[0]

        # Get creators (authors, editors, etc.)
        query = """
            SELECT ct.creatorType, c.firstName, c.lastName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
        """
        cursor.execute(query, (item_id,))
        metadata["creators"] = [
            {"type": ctype, "firstName": fname, "lastName": lname}
            for ctype, fname, lname in cursor.fetchall()
        ]

        # Get tags
        query = """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON it.tagID = t.tagID
            WHERE it.itemID = ?
        """
        cursor.execute(query, (item_id,))
        metadata["tags"] = [row[0] for row in cursor.fetchall()]

        conn.close()
        return metadata

    def get_citations_for_chapter(
        self, collection_id: int, style: str = "chicago"
    ) -> List[Dict[str, Any]]:
        """Get all citations for items in a chapter collection.

        Args:
            collection_id: Zotero collection ID
            style: Citation style ('chicago', 'apa', 'mla')

        Returns:
            List of formatted citations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all items in collection
        query = """
            SELECT DISTINCT i.itemID
            FROM collectionItems ci
            JOIN items i ON ci.itemID = i.itemID
            WHERE ci.collectionID = ?
        """
        cursor.execute(query, (collection_id,))
        item_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        citations = []
        for item_id in item_ids:
            metadata = self.get_item_metadata(item_id)
            citation = self._format_citation(metadata, style)
            citations.append(
                {"item_id": item_id, "citation": citation, "metadata": metadata}
            )

        return citations

    def _format_citation(self, metadata: Dict[str, Any], style: str) -> str:
        """Format a citation in the specified style.

        Args:
            metadata: Item metadata from get_item_metadata
            style: Citation style ('chicago', 'apa', 'mla')

        Returns:
            Formatted citation string
        """
        if style == "chicago":
            return self._format_chicago(metadata)
        elif style == "apa":
            return self._format_apa(metadata)
        elif style == "mla":
            return self._format_mla(metadata)
        else:
            return self._format_chicago(metadata)  # Default to Chicago

    def _format_chicago(self, metadata: Dict[str, Any]) -> str:
        """Format citation in Chicago style."""
        parts = []

        # Authors
        creators = metadata.get("creators", [])
        authors = [c for c in creators if c["type"] == "author"]

        if authors:
            if len(authors) == 1:
                parts.append(f"{authors[0]['lastName']}, {authors[0]['firstName']}")
            elif len(authors) == 2:
                parts.append(
                    f"{authors[0]['lastName']}, {authors[0]['firstName']} and "
                    f"{authors[1]['firstName']} {authors[1]['lastName']}"
                )
            else:
                parts.append(
                    f"{authors[0]['lastName']}, {authors[0]['firstName']}, et al."
                )

        # Title
        title = metadata.get("title", "")
        if title:
            # Italicize book/journal titles, quote article titles
            item_type = metadata.get("itemType", "")
            if item_type in ["book", "report", "thesis"]:
                parts.append(f"*{title}*")
            else:
                parts.append(f'"{title}"')

        # Publication info
        pub = metadata.get("publicationTitle")
        if pub:
            parts.append(f"*{pub}*")

        # Volume/Issue
        volume = metadata.get("volume")
        issue = metadata.get("issue")
        if volume:
            vol_str = f"{volume}"
            if issue:
                vol_str += f", no. {issue}"
            parts.append(vol_str)

        # Date
        date = metadata.get("date")
        if date:
            parts.append(f"({date})")

        # Pages
        pages = metadata.get("pages")
        if pages:
            parts.append(pages)

        return ". ".join(parts) + "."

    def _format_apa(self, metadata: Dict[str, Any]) -> str:
        """Format citation in APA style."""
        parts = []

        # Authors (Last, F. M.)
        creators = metadata.get("creators", [])
        authors = [c for c in creators if c["type"] == "author"]

        if authors:
            author_strs = []
            for author in authors[:7]:  # APA limits to 7 authors
                first_initial = author["firstName"][0] if author["firstName"] else ""
                author_strs.append(f"{author['lastName']}, {first_initial}.")

            if len(authors) > 7:
                author_strs.append("... ")
                author_strs.append(
                    f"{authors[-1]['lastName']}, {authors[-1]['firstName'][0]}."
                )

            parts.append(", ".join(author_strs))

        # Date
        date = metadata.get("date", "n.d.")
        parts.append(f"({date})")

        # Title
        title = metadata.get("title", "")
        if title:
            parts.append(title)

        # Journal/Book
        pub = metadata.get("publicationTitle")
        volume = metadata.get("volume")
        if pub:
            pub_str = f"*{pub}*"
            if volume:
                pub_str += f", *{volume}*"
            parts.append(pub_str)

        # Pages
        pages = metadata.get("pages")
        if pages:
            parts.append(pages)

        return ". ".join(parts) + "."

    def _format_mla(self, metadata: Dict[str, Any]) -> str:
        """Format citation in MLA style."""
        parts = []

        # Authors
        creators = metadata.get("creators", [])
        authors = [c for c in creators if c["type"] == "author"]

        if authors:
            if len(authors) == 1:
                parts.append(f"{authors[0]['lastName']}, {authors[0]['firstName']}")
            else:
                parts.append(
                    f"{authors[0]['lastName']}, {authors[0]['firstName']}, et al."
                )

        # Title
        title = metadata.get("title", "")
        if title:
            parts.append(f'"{title}"')

        # Container (journal/book)
        pub = metadata.get("publicationTitle")
        if pub:
            parts.append(f"*{pub}*")

        # Volume
        volume = metadata.get("volume")
        if volume:
            parts.append(f"vol. {volume}")

        # Issue
        issue = metadata.get("issue")
        if issue:
            parts.append(f"no. {issue}")

        # Date
        date = metadata.get("date")
        if date:
            parts.append(date)

        # Pages
        pages = metadata.get("pages")
        if pages:
            parts.append(f"pp. {pages}")

        return ", ".join(parts) + "."

    def get_bibliography(
        self, chapter_numbers: List[int], style: str = "chicago"
    ) -> str:
        """Generate a bibliography for multiple chapters.

        Args:
            chapter_numbers: List of chapter numbers
            style: Citation style

        Returns:
            Formatted bibliography as string
        """
        # This would need chapter->collection mapping
        # For now, return placeholder
        return "Bibliography generation not yet implemented for multiple chapters."
