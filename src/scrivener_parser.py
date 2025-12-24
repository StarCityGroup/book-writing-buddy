"""Parse Scrivener project structure from .scrivx file."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


class ScrivenerParser:
    """Parse chapter structure from Scrivener .scrivx project file."""

    def __init__(self, scrivener_path: str, manuscript_folder: Optional[str] = None):
        """Initialize parser with path to .scriv project.

        Args:
            scrivener_path: Path to .scriv project directory
            manuscript_folder: Optional name of manuscript folder to filter by (e.g., "FIREWALL", "Manuscript")
        """
        self.scriv_path = Path(scrivener_path)
        self.manuscript_folder = manuscript_folder

        # Find the .scrivx file dynamically (there should only be one)
        scrivx_files = list(self.scriv_path.glob("*.scrivx"))

        if not scrivx_files:
            raise FileNotFoundError(
                f"No .scrivx file found in Scrivener project directory: {self.scriv_path}"
            )

        if len(scrivx_files) > 1:
            raise ValueError(
                f"Multiple .scrivx files found in {self.scriv_path}. Expected exactly one."
            )

        self.scrivx_file = scrivx_files[0]

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

        # Filter by manuscript folder if specified
        if self.manuscript_folder:
            structure = self._filter_by_manuscript_folder(structure, self.manuscript_folder)
            # After filtering, assign sequential chapter numbers
            structure = self._assign_sequential_chapters(structure)

        return {
            "project_name": self.scriv_path.stem,
            "structure": structure,
            "chapters": self._flatten_chapters(structure),
        }

    def _parse_binder_item(
        self, element, level: int = 0, chapter_counter: int = 0
    ) -> List[Dict]:
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
                item["children"] = self._parse_binder_item(
                    children, level + 1, chapter_counter
                )

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

    def _assign_sequential_chapters(self, structure: List[Dict]) -> List[Dict]:
        """Assign sequential chapter numbers to folders after filtering.

        After filtering to manuscript folder, chapter folders don't have numbers.
        This assigns them sequentially and propagates to all nested children.

        Args:
            structure: Filtered structure (contents of manuscript folder)

        Returns:
            Structure with chapter numbers assigned
        """
        chapter_counter = 0

        def propagate_chapter_number(item, chapter_num):
            """Recursively assign chapter number to item and all its children."""
            item["chapter_number"] = chapter_num
            if "children" in item:
                for child in item["children"]:
                    propagate_chapter_number(child, chapter_num)

        # Track chapter 0 items (Preface, Introduction, etc.)
        chapter_zero_items = []
        chapter_zero_names = ["preface", "introduction"]

        # Process top-level items in the manuscript folder
        for item in structure:
            title = item.get("title", "").lower()

            # Check if this is a "Part" folder
            if item.get("is_folder") and title.startswith("part "):
                # Process chapter folders inside the Part
                if "children" in item:
                    for chapter in item["children"]:
                        if chapter.get("is_folder"):
                            chapter_counter += 1
                            propagate_chapter_number(chapter, chapter_counter)
            # Or if it's a standalone item at level 0 (like Preface or Introduction)
            elif title and title not in ["untitled", ""]:
                # Check if this is a chapter 0 item
                if title in chapter_zero_names:
                    chapter_zero_items.append(item)
                else:
                    chapter_counter += 1
                    propagate_chapter_number(item, chapter_counter)

        # Assign chapter 0 numbers (0, or 0A, 0B if multiple)
        if len(chapter_zero_items) == 1:
            propagate_chapter_number(chapter_zero_items[0], 0)
        elif len(chapter_zero_items) > 1:
            # Multiple chapter 0 items - use 0A, 0B, etc.
            for idx, item in enumerate(chapter_zero_items):
                chapter_num = f"0{chr(65 + idx)}"  # 0A, 0B, 0C...
                propagate_chapter_number(item, chapter_num)

        return structure

    def _filter_by_manuscript_folder(
        self, structure: List[Dict], manuscript_folder: str
    ) -> List[Dict]:
        """Filter structure to only include items under the manuscript folder.

        Args:
            structure: Full parsed structure
            manuscript_folder: Name of manuscript folder to filter by

        Returns:
            Filtered structure containing only items under manuscript folder
        """

        def find_manuscript_folder(items):
            """Recursively search for manuscript folder."""
            for item in items:
                if item.get("title") == manuscript_folder:
                    # Return children of this folder
                    return item.get("children", [])
                # Search in children
                if "children" in item:
                    result = find_manuscript_folder(item["children"])
                    if result is not None:
                        return result
            return None

        filtered = find_manuscript_folder(structure)
        if filtered is None:
            import structlog

            logger = structlog.get_logger()
            logger.warning(
                f"Manuscript folder '{manuscript_folder}' not found in Scrivener structure"
            )
            return []

        return filtered

    def _flatten_chapters(self, structure: List[Dict]) -> List[Dict]:
        """Flatten hierarchical structure to list of chapters.

        Args:
            structure: Nested structure from _parse_binder_item

        Returns:
            Flat list of chapters with metadata (only chapter folders, not nested docs)
        """
        chapters = []

        def recurse(items, parent_title=None, parent_is_part=False):
            for item in items:
                has_chapter_num = "chapter_number" in item
                title = item.get("title", "")
                is_part = title.lower().startswith("part ")

                # Include in chapters list if:
                # 1. Has chapter number AND is at top level (parent_title is None) - e.g., Preface
                # 2. Has chapter number AND parent is a Part folder
                if has_chapter_num and (parent_title is None or parent_is_part):
                    chapters.append(
                        {
                            "number": item["chapter_number"],
                            "title": title,
                            "parent": parent_title,
                            "level": item["level"],
                        }
                    )

                # Recurse into children
                if "children" in item:
                    recurse(item["children"], parent_title=title, parent_is_part=is_part)

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
