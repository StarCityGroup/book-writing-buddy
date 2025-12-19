"""Parse Scrivener project structure from .scrivx file."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


class ScrivenerParser:
    """Parse chapter structure from Scrivener .scrivx project file."""

    def __init__(self, scrivener_path: str):
        """Initialize parser with path to .scriv project.

        Args:
            scrivener_path: Path to .scriv project directory
        """
        self.scriv_path = Path(scrivener_path)
        self.scrivx_file = self.scriv_path / f"{self.scriv_path.stem}.scrivx"

        if not self.scrivx_file.exists():
            raise FileNotFoundError(f"Scrivener project file not found: {self.scrivx_file}")

    def get_chapter_structure(self) -> Dict:
        """Extract chapter structure from Scrivener project.

        Returns:
            Dict with structure info including parts and chapters
        """
        tree = ET.parse(self.scrivx_file)
        root = tree.getroot()

        # Find the Binder (document structure)
        binder = root.find(".//Binder")
        if binder is None:
            return {"error": "No Binder found in Scrivener project"}

        # Parse the structure
        structure = self._parse_binder_item(binder, level=0)

        return {
            "project_name": self.scriv_path.stem,
            "structure": structure,
            "chapters": self._flatten_chapters(structure),
        }

    def _parse_binder_item(self, element, level: int = 0, chapter_counter: int = 0) -> List[Dict]:
        """Recursively parse binder items.

        Args:
            element: XML element to parse
            level: Nesting level
            chapter_counter: Running count of chapters

        Returns:
            List of parsed items
        """
        items = []

        for binder_item in element.findall("BinderItem"):
            title_elem = binder_item.find("Title")
            title = title_elem.text if title_elem is not None else "Untitled"

            item_type = binder_item.get("Type", "Text")
            uuid = binder_item.get("UUID", "")

            # Detect if this is a chapter/folder
            children = binder_item.find("Children")
            has_children = children is not None and len(children) > 0

            item = {
                "title": title,
                "type": item_type,
                "uuid": uuid,
                "level": level,
                "is_folder": has_children or item_type == "Folder",
            }

            # Try to extract chapter number from title
            chapter_num = self._extract_chapter_number(title)
            if chapter_num:
                chapter_counter += 1
                item["chapter_number"] = chapter_num
                item["inferred_number"] = chapter_counter

            # Recursively parse children
            if has_children:
                item["children"] = self._parse_binder_item(children, level + 1, chapter_counter)

            items.append(item)

        return items

    def _extract_chapter_number(self, title: str) -> Optional[int]:
        """Extract chapter number from title.

        Args:
            title: Title string

        Returns:
            Chapter number if found, else None
        """
        import re

        # Match patterns like:
        # "1. Title", "Chapter 1", "1 - Title", "Ch 1", etc.
        patterns = [
            r"^(\d+)\.",  # "1. Title"
            r"^[Cc]hapter\s+(\d+)",  # "Chapter 1"
            r"^[Cc]h\.?\s+(\d+)",  # "Ch 1" or "Ch. 1"
            r"^(\d+)\s*[-–—]",  # "1 - Title" or "1 — Title"
        ]

        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return int(match.group(1))

        return None

    def _flatten_chapters(self, structure: List[Dict]) -> List[Dict]:
        """Flatten hierarchical structure to list of chapters.

        Args:
            structure: Nested structure from _parse_binder_item

        Returns:
            Flat list of chapters with metadata
        """
        chapters = []

        def recurse(items, parent_title=None):
            for item in items:
                # If it has a chapter number, add it
                if "chapter_number" in item:
                    chapters.append(
                        {
                            "number": item["chapter_number"],
                            "title": item["title"],
                            "parent": parent_title,
                            "level": item["level"],
                        }
                    )

                # Recurse into children
                if "children" in item:
                    recurse(item["children"], parent_title=item["title"])

        recurse(structure)

        # Sort by chapter number
        chapters.sort(key=lambda x: x["number"])

        return chapters

    def format_structure_as_text(self) -> str:
        """Format chapter structure as readable text for system prompt.

        Returns:
            Formatted text structure
        """
        try:
            data = self.get_chapter_structure()
        except Exception as e:
            return f"Error parsing Scrivener structure: {e}"

        if "error" in data:
            return data["error"]

        lines = [f"# {data['project_name']} - Scrivener Structure\n"]

        chapters = data.get("chapters", [])
        if not chapters:
            lines.append("No chapters found in Scrivener project.\n")
            return "\n".join(lines)

        # Group by parent (Parts)
        by_parent = {}
        for chapter in chapters:
            parent = chapter.get("parent", "Chapters")
            by_parent.setdefault(parent, []).append(chapter)

        # Format
        for parent, chaps in by_parent.items():
            lines.append(f"## {parent}")
            for ch in chaps:
                lines.append(f"- Chapter {ch['number']}: {ch['title']}")
            lines.append("")

        return "\n".join(lines)
