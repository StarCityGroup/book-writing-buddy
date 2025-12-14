#!/usr/bin/env python3
"""
Chapter Analysis Tool for Book Writing

Analyzes materials from Zotero and Scrivener to prepare chapter drafting:
- Extracts key points and themes
- Highlights compelling facts and quotes
- Suggests narrative threads
- Collects example cases

Uses MCP servers for Zotero and filesystem access with TUI pickers.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from pick import pick


def load_config():
    """Load project configuration."""
    config_path = Path(__file__).parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


def pick_zotero_collection():
    """
    Present TUI picker for Zotero chapter collections.

    Navigates nested structure: FIREWALL -> Part X -> Chapter collections
    In actual use, this would call Zotero MCP to traverse the hierarchy.
    For now, returns mock data structure.
    """
    print("\n" + "=" * 60)
    print("SELECT ZOTERO COLLECTION")
    print("=" * 60)
    print("\nFetching collections from Zotero...\n")
    print("Collection structure: FIREWALL/Part X/Chapter\n")

    # TODO: Replace with actual MCP call to traverse:
    # 1. Find "FIREWALL" root collection
    # 2. Get subcollections (Part 1, Part 2, Part 3)
    # 3. Get chapter subcollections from all parts
    # 4. Flatten into selectable list

    # Mock data showing nested structure
    # Actual structure: FIREWALL/Part I. Title/23. Chapter Title
    collections = [
        "Part I. Origins → 23. The Early Days",
        "Part I. Origins → 24. DEC and Packet Filters",
        "Part I. Origins → 25. Building Firewalls",
        "Part II. Behind the Firewall → 26. Corporate Adoption",
        "Part II. Behind the Firewall → 27. Internet Security",
        "Part II. Behind the Firewall → 28. Commercial Solutions",
        "Part III. Modern Era → 29. Cloud Security",
        "Part III. Modern Era → 30. Future Threats",
    ]

    if not collections:
        print("No chapter collections found in FIREWALL.")
        print("Please organize your research into the nested structure.")
        return None

    title = "Select the chapter collection to analyze:"
    selected, index = pick(collections, title, indicator="=>")

    # Extract part and chapter info from "Part X → 23. Title" format
    parts = selected.split(" → ")
    part_name = parts[0]
    chapter_info = parts[1]
    chapter_num = int(chapter_info.split(".")[0])

    return {
        "index": index,
        "chapter_num": chapter_num,
        "part_name": part_name,
        "collection_name": chapter_info,
        "full_path": f"FIREWALL/{part_name}/{chapter_info}",
    }


def pick_scrivener_folder(config):
    """
    Present TUI picker for Scrivener chapter folders.

    In actual use, this would explore the Scrivener .scriv bundle structure.
    For now, returns mock data.
    """
    print("\n" + "=" * 60)
    print("SELECT SCRIVENER CHAPTER FOLDER")
    print("=" * 60)
    print(f"\nExploring Scrivener project: {config['scrivener_project']}\n")

    scriv_path = Path(config["scrivener_project"])

    if not scriv_path.exists():
        print(f"ERROR: Scrivener project not found at {scriv_path}")
        return None

    # TODO: Replace with actual filesystem exploration via MCP
    # This would:
    # 1. Use Filesystem MCP to read the .scriv bundle
    # 2. Parse Files/Data/ directory structure
    # 3. Read folder metadata to get names
    folders = [
        "Introduction",
        "Chapter 1: Origins",
        "Chapter 2: The Packet Filter",
        "Chapter 3: Commercial Firewalls",
        "Chapter 4: Enterprise Security",
        "Chapter 5: Modern Era",
        "Conclusion",
    ]

    if not folders:
        print("No chapter folders found in Scrivener project.")
        return None

    title = "Select the chapter folder to analyze:"
    selected, index = pick(folders, title, indicator="=>")

    return {
        "index": index,
        "folder_name": selected,
        "folder_path": f"[Scrivener structure index: {index}]",
    }


def analyze_materials(zotero_selection, scrivener_selection, config):
    """
    Main analysis function using MCP servers.

    This would:
    1. Use Zotero MCP to fetch collection items, notes, annotations
    2. Include General Reference materials
    3. Use Filesystem MCP to read Scrivener folder contents
    4. Read entire manuscript for context
    5. Process with Claude for deep analysis
    6. Return structured findings
    """

    print("\n" + "=" * 60)
    print("ANALYZING MATERIALS")
    print("=" * 60)

    chapter_num = zotero_selection["chapter_num"]
    collection_name = zotero_selection["collection_name"]
    part_name = zotero_selection.get("part_name", "")
    folder_name = scrivener_selection["folder_name"]

    print(f"\nChapter: {chapter_num}")
    print(f"Part: {part_name}")
    print(f"Zotero Collection: {collection_name}")
    print(f"Scrivener Folder: {folder_name}")
    print("\nThis is where Claude would:")
    print("  1. Fetch chapter-specific Zotero items, notes, and annotations")
    print("  2. Include General Reference materials from FIREWALL/General Reference")
    print("  3. Read Scrivener chapter drafts and notes")
    print("  4. Load entire manuscript for context")
    print("  5. Analyze all materials for key insights")
    print("  6. Generate structured analysis")

    # Placeholder structure - would be filled by actual MCP + Claude analysis
    analysis = {
        "chapter": chapter_num,
        "part_name": part_name,
        "collection_name": collection_name,
        "full_path": zotero_selection.get("full_path", ""),
        "folder_name": folder_name,
        "timestamp": datetime.now().isoformat(),
        "key_points": [
            "Early packet filtering concepts emerged from telecom background",
            "Technical innovation driven by practical security needs",
            "Resistance from network performance concerns",
        ],
        "great_facts": [
            '"We weren\'t building security, we were building visibility" - Early engineer quote',
            "DEC's packet filter processed 10,000 packets/sec in 1988",
            "First commercial firewall sold for $50,000 in 1991",
        ],
        "narrative_thread": (
            "Begin with the technical problem: how do you inspect network traffic "
            "without slowing it down? Introduce the engineers who faced this challenge "
            "at DEC. Show the evolution from simple packet filtering to stateful inspection. "
            "End with the realization that technical solutions require organizational change."
        ),
        "bag_of_examples": [
            "DEC packet filter case study (1988-1990)",
            "Bill Cheswick's 'Evening with Berferd' analysis",
            "Early Cisco PIX development story",
            "AT&T deployment challenges and solutions",
        ],
        "source_materials": {
            "zotero_items": 15,  # Would be actual count
            "scrivener_files": 8,  # Would be actual count
            "manuscript_words": 45000,  # Context from other chapters
        },
    }

    return analysis


def generate_markdown(analysis, config):
    """Generate markdown output from analysis."""
    chapter_num = analysis["chapter"]
    collection_name = analysis.get("collection_name", "Unknown")
    folder_name = analysis.get("folder_name", "Unknown")
    part_name = analysis.get("part_name", "")
    full_path = analysis.get("full_path", "")

    md = f"""# Chapter {chapter_num} Analysis

**Generated:** {analysis["timestamp"]}
**Zotero Collection:** {full_path if full_path else collection_name}
**Scrivener Folder:** {folder_name}

---

## Key Points

*Main themes and ideas to emphasize in this chapter*

"""

    if analysis["key_points"]:
        for point in analysis["key_points"]:
            md += f"- {point}\n"
    else:
        md += "*To be identified from materials*\n"

    md += """
## Great Facts

*Compelling data, quotes, and evidence to highlight*

"""

    if analysis["great_facts"]:
        for fact in analysis["great_facts"]:
            md += f"- {fact}\n"
    else:
        md += "*To be extracted from sources*\n"

    md += """
## Narrative Thread

*Suggested approach and structure for the chapter*

"""

    if analysis["narrative_thread"]:
        md += analysis["narrative_thread"] + "\n"
    else:
        md += "*To be developed from materials*\n"

    md += """
## Bag of Examples

*Concrete cases and illustrations to draw from*

"""

    if analysis["bag_of_examples"]:
        for example in analysis["bag_of_examples"]:
            md += f"- {example}\n"
    else:
        md += "*To be collected from research*\n"

    md += """
---

## Source Materials Summary

"""

    if "source_materials" in analysis:
        sm = analysis["source_materials"]
        md += f"- **Zotero items analyzed:** {sm.get('zotero_items', 0)}\n"
        md += f"- **Scrivener files read:** {sm.get('scrivener_files', 0)}\n"
        md += (
            f"- **Manuscript context:** {sm.get('manuscript_words', 0):,} words\n"
        )
    else:
        md += "*Source material counts not available*\n"

    md += """
---

## Notes for Drafting

### Research Gaps
*Areas that need additional sources or verification*

- [To be identified during analysis]

### Cross-References
*Connections to other chapters*

- [To be identified from manuscript context]

### Questions to Resolve
*Open questions for consideration while drafting*

- [To be noted during material review]
"""

    return md


def save_output(markdown, chapter_num, config):
    """Save analysis to markdown file."""
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(exist_ok=True)

    # Use timestamp to avoid overwriting previous analyses
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"chapter-{chapter_num:02d}-analysis-{timestamp}.md"
    output_path = output_dir / filename

    with open(output_path, "w") as f:
        f.write(markdown)

    return output_path


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("BOOK CHAPTER ANALYSIS TOOL")
    print("=" * 60)
    print("\nPrepare for chapter drafting by analyzing research materials")
    print("from Zotero and Scrivener.\n")

    config = load_config()

    # Check Scrivener path exists
    scriv_path = Path(config["scrivener_project"])
    if not scriv_path.exists():
        print(f"\n⚠️  WARNING: Scrivener project not found at:")
        print(f"   {scriv_path}\n")
        print("Please update config.json with the correct path.")
        input("\nPress Enter to continue anyway, or Ctrl+C to exit...")

    try:
        # Step 1: Pick Zotero collection
        zotero_selection = pick_zotero_collection()
        if not zotero_selection:
            print("\nNo collection selected. Exiting.")
            return

        # Step 2: Pick Scrivener folder
        scrivener_selection = pick_scrivener_folder(config)
        if not scrivener_selection:
            print("\nNo folder selected. Exiting.")
            return

        # Step 3: Analyze materials
        analysis = analyze_materials(zotero_selection, scrivener_selection, config)

        # Step 4: Generate and save output
        markdown = generate_markdown(analysis, config)
        output_path = save_output(
            markdown, zotero_selection["chapter_num"], config
        )

        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"\n✅ Output saved to:")
        print(f"   {output_path}\n")
        print("Next steps:")
        print("  1. Review the generated analysis")
        print("  2. Use it as a guide for drafting your chapter")
        print("  3. Run again for other chapters as needed\n")

    except KeyboardInterrupt:
        print("\n\nAnalysis cancelled by user.")
        return


if __name__ == "__main__":
    main()
