# Quick Start Guide

Get started analyzing your book chapters in 5 minutes.

## Prerequisites Check

- [ ] Python 3.8+ installed
- [ ] Node.js installed (`node --version`)
- [ ] Zotero installed with collections organized by chapter
- [ ] Scrivener project accessible
- [ ] Claude Code CLI installed

## Setup Steps

### 1. Install Python Dependencies

```bash
cd /Users/anthonytownsend/code/_dev/book-chapter-planner
uv sync
```

This installs the `pick` package for the interactive TUI.

### 2. Verify MCP Configuration

The project already has MCP configured in `.claude/mcp.json` with:
- **Zotero MCP**: Access to `/Users/anthonytownsend/Zotero`
- **Filesystem MCP**: Access to your Scrivener project and this directory

**No additional MCP setup needed** - it's project-specific!

### 3. Prepare Your Materials

#### Zotero Collections
Organize sources into collections named:
- `1. Title of Chapter One`
- `2. Title of Chapter Two`
- etc.

**Important:** Close Zotero before running analysis (database lock issue)

#### Scrivener Project
Ensure your project at `/Users/anthonytownsend/Dropbox/Apps/Scrivener/FIREWALL.scriv` is accessible.

### 4. Test the Script

Run the standalone version (uses mock data):

```bash
uv run python analyze_chapter.py
```

This will show you the TUI pickers and generate a sample analysis.

### 5. Run Real Analysis with Claude Code

In a Claude Code session (this conversation!), ask:

```
Analyze chapter 1 for my book using the materials from Zotero and Scrivener
```

Claude Code will:
1. Use MCP to list your actual Zotero collections
2. Present TUI picker for collection selection
3. Use MCP to explore your Scrivener structure
4. Present TUI picker for chapter folder
5. Read all materials
6. Perform deep analysis
7. Generate structured markdown output

## Usage Examples

### Analyze a Specific Chapter

```
Analyze chapter 3 for my FIREWALL book
```

### Batch Process Multiple Chapters

```
Analyze chapters 1 through 5, one at a time
```

### Custom Analysis Focus

```
Analyze chapter 2 but focus specifically on technical details and engineering decisions
```

## Output Location

Generated analyses are saved to:
```
output/chapter-{number}-analysis-{timestamp}.md
```

Example: `output/chapter-01-analysis-20241214-183045.md`

## Troubleshooting

### "Zotero database locked"
**Solution:** Close the Zotero application before running analysis.

### "Scrivener project not found"
**Solution:** Verify the path in `config.json` is correct and the .scriv bundle exists.

### "MCP server not responding"
**Solution:**
1. Make sure you're in a Claude Code session in this project directory
2. The MCP servers are loaded from `.claude/mcp.json` automatically
3. Restart Claude Code if needed

### "No collections found"
**Solution:**
1. Check your Zotero collections are named with pattern `1. Title`, `2. Title`, etc.
2. Ensure the collections have items in them
3. Close Zotero and try again

## What You Get

Each analysis includes:

### Key Points
Main themes and arguments to emphasize in the chapter

### Great Facts
Compelling data, quotes, and evidence to highlight from your sources

### Narrative Thread
Suggested approach and structure for telling the chapter's story

### Bag of Examples
Concrete cases and illustrations to draw from

### Source Materials Summary
Count of Zotero items, Scrivener files, and manuscript context analyzed

### Notes for Drafting
Research gaps, cross-references, and questions to resolve

## Next Steps

1. Review the generated analysis markdown file
2. Use it as a guide while drafting (NOT as a draft itself)
3. Adjust and iterate based on new research
4. Run analysis again when you add significant new materials

## Tips

- **Close Zotero first** - This is the #1 gotcha
- **Organize before analyzing** - Better organized materials = better analysis
- **Iterate as needed** - Run multiple times as your research evolves
- **Supplement with judgment** - The analysis is a guide, not gospel
- **Use timestamps** - Multiple analyses per chapter are saved with timestamps

## Support

- **Script issues**: Check the logs and error messages
- **MCP issues**: See [MCP_SETUP.md](MCP_SETUP.md)
- **Analysis quality**: Make sure your Zotero annotations are detailed
- **General questions**: Ask in your Claude Code session

## Advanced Usage

### Modify Analysis Sections

Edit `config.json` to change what sections are included:

```json
{
  "analysis_sections": [
    "key_points",
    "great_facts",
    "narrative_thread",
    "bag_of_examples",
    "counterarguments",
    "transitions"
  ]
}
```

### Change Output Format

The `generate_markdown()` function in `analyze_chapter.py` can be customized for different output styles.

### Add Custom Analysis Logic

Modify the `analyze_materials()` function to add custom processing or different analysis frameworks.

## Project Structure Reference

```
book-chapter-planner/
├── .claude/
│   ├── claude.md           # Project context for Claude
│   └── mcp.json           # MCP server configuration
├── output/                 # Generated analyses
├── analyze_chapter.py     # Main script
├── config.json            # Project configuration
├── pyproject.toml         # Python dependencies
├── QUICKSTART.md          # This file
├── README.md              # Full documentation
└── MCP_SETUP.md           # Detailed MCP guide
```

---

**Ready to start!** Ask Claude Code to analyze your first chapter.
