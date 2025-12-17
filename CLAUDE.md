# Book Chapter Analysis Tool - Project Context

This project helps analyze research materials from Zotero and Scrivener to prepare for chapter drafting.

## Project Purpose

Before drafting each chapter, this tool:
1. Gathers materials from Zotero collections and Scrivener folders
2. Analyzes the entire manuscript context
3. Identifies key points, compelling facts, narrative threads, and examples
4. Outputs structured markdown for reference while writing

**Important**: This tool does NOT draft content. It prepares analytical guidance.

## Project Structure

- `analyze_chapter.py` - Main interactive script with TUI pickers
- `config.json` - Project configuration (paths, patterns)
- `output/` - Generated markdown analyses
- `.claude/mcp.json` - **MCP server configuration (project-specific for Claude Code)**
- `CLAUDE.md` - This file (project context and instructions)

## Data Sources

### Zotero Collections
- **Structure**: Nested hierarchy under root collection "FIREWALL"
  ```
  FIREWALL/
  ├── General Reference/        (important context for all chapters)
  ├── __incoming/               (unsorted documents)
  ├── Part I. Adaptation Shock/
  │   ├── 1. the mangrove and the space mirror
  │   ├── 2. adaptation shock
  │   ├── 3. gaps and traps
  │   └── 4. adaptive intelligence
  ├── Part II. Behind the Firewall/
  │   ├── 5. early warning
  │   ├── 9. underground cables
  │   └── ... (chapters 5-23)
  └── Part III. Transformation/
      ├── 24. intelligence for adaptation (ai agenda)
      └── ... (chapters 24-27)
  ```
- **Pattern**: Chapters numbered 1-27, with lowercase titles
- **Location**: Local Zotero database at `/Users/anthonytownsend/Zotero`
- **Access**: Via Zotero MCP server (must close Zotero before running)
- **Content**: Research sources, clippings, annotations, notes
- **General Reference**: Always included in analysis for cross-chapter context

### Scrivener Project
- **Location**: `/Users/anthonytownsend/Dropbox/Apps/Scrivener/FIREWALL.scriv`
- **Structure**: Nested folder structure (not consistently named)
- **Access**: Via Filesystem MCP server
- **Content**: Chapter drafts, research notes, outlines

### Manuscript Context
- **Purpose**: Entire manuscript provides context for thread analysis
- **Use**: Drawing connections between chapters, maintaining consistency

## Key Design Decisions

### TUI Pickers
The tool uses interactive terminal pickers (not command-line arguments):
- **Zotero Collection Picker**: Lists all collections, user selects which chapter
- **Scrivener Folder Picker**: Lists nested folders, user selects chapter folder
- **Rationale**: Collections and folders aren't consistently named/numbered

### MCP Server Usage
- **Zotero MCP**: Read-only access to local database
- **Filesystem MCP**: Read access to Scrivener project and this project directory
- **Claude Analysis**: All materials are processed by Claude for deep analysis

### Output Format
Generated markdown includes:
- **Key Points**: Main themes to emphasize
- **Great Facts**: Compelling data, quotes, evidence to highlight
- **Narrative Thread**: Suggested approach and structure
- **Bag of Examples**: Concrete cases and illustrations

## Workflow Instructions

When the user asks to analyze a chapter:

### Step 1: Gather Zotero Materials
1. Query Zotero database to find the chapter collection
2. Get all items in that chapter collection
3. **Read the actual content** of each document:
   - For PDFs: Extract and read full text or key sections
   - For webpages: Fetch and read the saved content
   - For articles: Read abstracts, key findings, methodology
4. **Extract annotations and notes** if they exist
5. **General Reference collection**: Only use as fallback if chapter has insufficient materials (very large documents)

### Step 2: Analyze Scrivener Manuscript
1. Navigate to Scrivener project: `/Users/anthonytownsend/Dropbox/Apps/Scrivener/FIREWALL.scriv`
2. Explore the Files/Data/ structure to find chapter folders
3. **Read the chapter drafts and notes**:
   - Current draft text
   - Research notes
   - Outline or structure documents
4. **Read surrounding chapters** for context and connections
5. Identify what's already written vs. what gaps need research

### Step 3: Cross-Chapter Context
1. **Look at materials from related chapters**:
   - Previous chapters (for continuity)
   - Later chapters that might connect thematically
   - Identify where themes emerge across the book
2. **Note cross-references and connections**

### Step 4: Deep Analysis
With actual content in hand:
- Extract key themes and arguments **from the documents themselves**
- Identify compelling facts and quotes **with exact sources and page numbers**
- Suggest narrative structure based on **what the research actually says**
- Collect examples and cases **with specific details**
- Identify research gaps **based on what's missing from current materials**

### Step 5: Generate Comprehensive Markdown
Write to `output/chapter-{number}-analysis-{timestamp}.md` including:
- Key themes from the research
- Great facts with full citations
- Narrative thread suggestions
- Bag of examples with details
- Cross-chapter connections
- Identified research gaps
- Notes on what's in Scrivener already

## Important Notes

### Before Running
- Close Zotero application (database lock conflict)
- Start Docker containers: `docker compose up -d`
- MCP server configuration is in `.claude/mcp.json` (project-specific for Claude Code)
- Verify Scrivener project path is accessible

### Code Style
- Use Python 3.8+ features
- Follow uv package management (see global CLAUDE.md)
- Use ruff for linting and formatting
- Keep TUI simple and intuitive

### Analysis Quality
- Focus on **extracting** insights, not generating content
- Preserve source attribution (Zotero items)
- Flag connections to other chapters
- Note gaps in research materials

### Output Handling
- One markdown file per chapter analysis
- Timestamp each analysis
- Keep previous analyses (don't overwrite)
- Use clear, structured markdown format

## Configuration

### Zotero Collection Pattern
Collections follow: `{number}. {title}` format
Example: "1. The Early Days of Firewalls", "2. DEC and the Packet Filter"

### Scrivener Structure
Variable nested structure - use folder picker instead of pattern matching.

### Analysis Sections
Default sections (configurable in config.json):
- key_points
- great_facts
- narrative_thread
- bag_of_examples

## Dependencies

### Python Packages
- Standard library only for basic script
- Optional: `rich` for better TUI (install with `uv add rich`)
- Optional: `pick` for menu selection (install with `uv add pick`)

### External Services
- Book Research MCP server (custom, runs in Docker)
- Qdrant vector database (runs in Docker)
- Claude Code with MCP support (configured via `.claude/mcp.json`)

## Error Handling

### Common Issues
1. **Zotero database locked**: Remind user to close Zotero
2. **Scrivener path not found**: Verify path in config.json
3. **Empty collections**: Warn user if selected collection has no items
4. **MCP not configured**: Provide clear setup instructions

### Graceful Degradation
If MCP servers aren't available, script should:
- Warn user about missing MCP configuration
- Provide setup instructions
- Exit gracefully with helpful error messages

## Development Guidelines

### When Adding Features
- Update this claude.md with context
- Update README.md with user-facing documentation
- Test with actual Zotero collections and Scrivener folders
- Ensure TUI is keyboard-accessible

### When Analyzing Materials
- Prioritize quality over speed
- Consider the entire manuscript context
- Flag important cross-references
- Note research gaps or weak points

### When Generating Output
- Use clear, actionable language
- Structure for quick reference during writing
- Include source attribution
- Keep format consistent across analyses

## User's Book Context

**Title**: FIREWALL (working title)
**Topic**: History of firewall technology and network security
**Research**: Managed in Zotero with chapter-organized collections
**Drafting**: In Scrivener with nested chapter folders

## Future Enhancements

Potential additions:
- Cross-chapter theme tracking
- Research gap identification
- Citation export for final manuscript
- Progress tracking dashboard
- Automated outline suggestions
