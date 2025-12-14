# Book Chapter Analysis Tool

An AI-powered tool to help prepare for chapter drafting by analyzing research materials from Zotero and Scrivener drafts.

## What It Does

Before you draft each chapter, this tool:

1. **Gathers materials** from:
   - Zotero collections (clippings, notes, annotations)
   - Scrivener chapter folders (drafts, notes)
   - Your manuscript context (other chapters)

2. **Analyzes and identifies**:
   - **Key Points**: Main themes to emphasize
   - **Great Facts**: Compelling data and quotes
   - **Narrative Thread**: Suggested approach and structure
   - **Bag of Examples**: Concrete cases to draw from

3. **Outputs** a structured markdown file for reference while drafting

**Note:** This tool does NOT draft content for you. It prepares analytical guidance to inform your writing.

## Prerequisites

- Python 3.8+
- Node.js (for MCP servers)
- Claude Desktop with Claude Code
- Local Zotero installation with database
- Scrivener project

## Setup

### 1. Install MCP Servers

Follow the detailed setup guide: [MCP_SETUP.md](MCP_SETUP.md)

Quick version:
```bash
npm install -g @modelcontextprotocol/server-zotero
npm install -g @modelcontextprotocol/server-filesystem
```

Then configure Claude Desktop's `claude_desktop_config.json` with your paths.

### 2. Configure Project Paths

Edit `config.json` in this directory to match your setup:

```json
{
  "scrivener_project": "/path/to/your/project.scriv",
  "zotero_data_dir": "/Users/your-username/Zotero",
  "output_dir": "./output",
  "chapter_pattern": "Ch{number}",
  "zotero_collection_pattern": "Chapter {number}"
}
```

**Key settings:**
- `chapter_pattern`: How chapters are named in Scrivener (e.g., "Ch1", "Chapter 1")
- `zotero_collection_pattern`: How Zotero collections are named per chapter

### 3. Organize Your Materials

**Zotero:**
- Create collections named "Chapter 1", "Chapter 2", etc.
- Add all sources for each chapter to its collection
- Tag and annotate freely - all notes will be analyzed

**Scrivener:**
- Use consistent chapter folder naming (Ch1, Ch2, etc.)
- Keep drafts, notes, and research in chapter folders
- The tool reads the entire folder structure

## Usage

### Interactive Mode (Recommended)

Run the script and follow prompts:

```bash
python analyze_chapter.py
```

You'll be asked:
- Which chapter number to analyze
- The tool then processes all materials and generates output

### Using Claude Code (Advanced)

In a Claude Code session:

```
Analyze chapter 3 using the book-chapter-planner tool
```

Claude will:
1. Use MCP to access Zotero and Scrivener
2. Read all relevant materials
3. Perform deep analysis
4. Generate structured markdown output

## Output

Analysis results are saved to: `output/chapter-{number}-analysis.md`

Example structure:

```markdown
# Chapter 3 Analysis

## Key Points
- Main theme: The evolution of firewall technology
- Secondary focus: Corporate security culture shifts
- Critical argument: Technical solutions vs. human factors

## Great Facts
- "In 1988, the Morris worm infected 10% of internet-connected computers" (Source: XYZ paper)
- DEC's pioneering packet filter implementation details
- Industry adoption rates 1990-1995

## Narrative Thread
Start with the Morris worm incident to establish urgency and stakes.
Introduce early firewall concepts through the lens of specific engineers.
Build to the corporate adoption phase with concrete examples.
Connect to broader themes of security culture evolution.

## Bag of Examples
- DEC packet filter case study
- Bill Cheswick's "Evening with Berferd" attack analysis
- Cisco PIX firewall development story
- AT&T deployment challenges
```

## Workflow

Recommended workflow for each chapter:

1. **Gather materials**: Add sources to Zotero collection, draft notes in Scrivener
2. **Run analysis**: `python analyze_chapter.py`
3. **Review output**: Read the generated markdown file
4. **Draft chapter**: Use the analysis as a guide (not a template)
5. **Iterate**: Run again if you add significant new materials

## Customization

### Change Output Sections

Edit `config.json` to modify analysis sections:

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

### Adjust Chapter Naming

If your Scrivener structure differs:

```json
{
  "chapter_pattern": "Chapter {number}",
  "zotero_collection_pattern": "Ch{number} - Title"
}
```

## Troubleshooting

### "Scrivener project not found"

- Verify the path in `config.json` points to your `.scriv` bundle
- Check that you have read permissions
- Ensure the path uses absolute paths or is relative to this directory

### "Zotero collection empty"

- Check collection naming matches `zotero_collection_pattern`
- Ensure Zotero is NOT running (database lock conflict)
- Verify items are actually in the collection

### "No chapter folders found"

- Check your Scrivener project structure
- Verify chapter naming matches `chapter_pattern`
- Scrivener structures can vary - you may need to adjust the script

### MCP Issues

See detailed troubleshooting in [MCP_SETUP.md](MCP_SETUP.md)

## Advanced Usage

### Batch Process All Chapters

Modify the script or ask Claude Code:

```
Analyze all chapters from 1 to 12 in batch mode
```

### Custom Prompts

You can customize the analysis prompts by working with Claude Code:

```
Analyze chapter 5 but focus specifically on technical details and source code examples
```

### Export Formats

Currently outputs markdown. Future options:
- HTML with styled output
- JSON for programmatic use
- Integration with note-taking apps

## Project Structure

```
book-chapter-planner/
├── README.md              # This file
├── MCP_SETUP.md          # MCP server setup guide
├── config.json           # Project configuration
├── analyze_chapter.py    # Main analysis script
└── output/               # Generated analyses
    ├── chapter-01-analysis.md
    ├── chapter-02-analysis.md
    └── ...
```

## How It Works

The tool uses:

1. **MCP Servers** for data access:
   - Zotero MCP reads your local database
   - Filesystem MCP reads Scrivener files

2. **Claude AI** for analysis:
   - Processes all materials in context
   - Identifies patterns and key information
   - Structures findings for writing reference

3. **Local Processing**:
   - All analysis happens on your machine
   - No data sent to external services except Claude API
   - Your research materials stay private

## Best Practices

- **Close Zotero** before running analysis (database lock)
- **Organize first**: Well-organized materials = better analysis
- **Review output**: The analysis is a guide, not gospel
- **Iterate**: Run multiple times as your research evolves
- **Supplement**: Use alongside your own judgment and planning

## Limitations

- Requires organized source materials
- Quality depends on your Zotero annotations
- Cannot access external Zotero groups or web library
- Scrivener structure must be somewhat consistent
- Output quality depends on material quality

## Future Enhancements

Potential additions:
- Web-based dashboard for viewing analyses
- Cross-chapter theme tracking
- Citation management integration
- Automatic outline generation
- Integration with writing progress tracking

## Support

For issues with:
- **MCP setup**: See [MCP_SETUP.md](MCP_SETUP.md)
- **Script bugs**: Check script output and configuration
- **Claude Code**: Refer to Claude Code documentation
- **Zotero integration**: Verify database access and collection naming

## License

This tool is for personal use in your book writing project.

## Acknowledgments

Built with:
- Claude AI by Anthropic
- Model Context Protocol (MCP)
- Zotero for research management
- Scrivener for manuscript drafting
