# Project Structure Guide

## Your FIREWALL Book Organization

### Zotero Collection Hierarchy

```
FIREWALL/                          (root collection)
├── General Reference/             ← Important context included in ALL analyses
├── __incoming/                    ← Unsorted documents to be filed later
├── Part I. [Title]/
│   ├── 23. [Chapter Title]
│   ├── 24. [Chapter Title]
│   └── ...
├── Part II. Behind the Firewall/
│   ├── 26. [Chapter Title]
│   ├── 27. [Chapter Title]
│   └── ...
└── Part III. [Title]/
    ├── 29. [Chapter Title]
    ├── 30. [Chapter Title]
    └── ...
```

**Key Points:**
- Chapters numbered starting from 23
- Parts use Roman numerals (I, II, III) with titles
- General Reference contains cross-chapter context materials
- __incoming holds unsorted documents

### Scrivener Project Structure

```
FIREWALL.scriv/
└── [Nested folder structure]
    ├── [Various chapter folders]
    └── [Notes and drafts]
```

**Key Points:**
- Folder structure is NOT consistently named
- Use TUI picker to select correct chapter folder
- Contains drafts, notes, research, outlines

### How Analysis Works

When you analyze a chapter, the tool will:

1. **Fetch from Zotero:**
   - Selected chapter collection (e.g., "23. Chapter Title")
   - "General Reference" collection (for context)
   - All items, notes, annotations, and attachments

2. **Read from Scrivener:**
   - Selected chapter folder contents
   - Entire manuscript for cross-chapter context

3. **Generate Analysis with:**
   - Key Points (themes to emphasize)
   - Great Facts (compelling quotes and data)
   - Narrative Thread (structural suggestions)
   - Bag of Examples (concrete cases)

## Quick Reference

### Config File Settings

Location: `config.json`

```json
{
  "zotero_root_collection": "FIREWALL",
  "zotero_general_reference": "General Reference",
  "zotero_incoming": "__incoming",
  "include_general_reference": true
}
```

### MCP Configuration

Location: `.claude/mcp.json`

- **Zotero MCP**: Access to `/Users/anthonytownsend/Zotero`
- **Filesystem MCP**: Access to Scrivener project and output directory

### Output Location

Generated analyses saved to:
```
output/chapter-{number}-analysis-{timestamp}.md
```

Example: `output/chapter-23-analysis-20241214-183045.md`

## Usage Example

**In Claude Code session:**
```
Analyze chapter 26 for my FIREWALL book
```

**Claude will:**
1. Show TUI picker with all chapters from all parts
2. You select: "Part II. Behind the Firewall → 26. Corporate Security"
3. Show Scrivener folder picker
4. You select the matching chapter folder
5. Claude analyzes:
   - Chapter 26 collection items
   - General Reference items
   - Scrivener chapter materials
   - Entire manuscript context
6. Generates structured markdown analysis

## Important Notes

### Before Running Analysis
- **Close Zotero** (database lock issue)
- Ensure Scrivener project is accessible
- Chapter collections should have research items

### General Reference Collection
- Contains important context for ALL chapters
- Always included in every analysis
- Add sources here that apply across multiple chapters

### __incoming Collection
- For unsorted documents not yet filed
- Not automatically included in analysis
- Move items to appropriate chapter collections when ready

## Tips

1. **Organize before analyzing**: Better organized collections = better analysis
2. **Use General Reference liberally**: Cross-cutting themes, definitions, key sources
3. **Annotate in Zotero**: Your notes and highlights are analyzed
4. **Keep Scrivener synced**: Analysis reads current state of files
5. **Review output**: The analysis guides your writing, doesn't replace it

## Troubleshooting

### "No collections found"
- Check that FIREWALL root collection exists
- Verify chapter collections are nested under Part folders
- Make sure collections have items in them

### "General Reference not found"
- Create "General Reference" as subcollection under FIREWALL
- Or set `include_general_reference: false` in config.json

### "Database locked"
- Close Zotero application completely
- Wait a moment, then try again

## File Locations

All paths configured in `config.json`:
- Zotero: `/Users/anthonytownsend/Zotero`
- Scrivener: `/Users/anthonytownsend/Dropbox/Apps/Scrivener/FIREWALL.scriv`
- Output: `./output/`

---

For more details, see:
- [README.md](README.md) - Full documentation
- [QUICKSTART.md](QUICKSTART.md) - 5-minute setup
- [MCP_SETUP.md](MCP_SETUP.md) - MCP server details
- `.claude/claude.md` - Project context for Claude
