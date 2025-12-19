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
- `config/` - Project configuration files
- `output/` - Generated markdown analyses
- `.claude/skills/` - **Claude Code skills (project-specific)**
- `CLAUDE.md` - This file (project context and instructions)

## Data Sources

Project-specific details are configured in `data/project.json` (copy from `data/project.example.json` and customize).

### Zotero Collections
- **Structure**: Nested hierarchy under a root collection
  - Root collection name configured in `data/project.json`
  - Special collections: General Reference (cross-chapter context), __incoming (unsorted)
  - Chapter collections organized by parts
- **Pattern**: Chapters typically numbered with format `{number}. {title}`
- **Location**: Local Zotero database (path set in `.env`)
- **Access**: Via Docker indexer (must close Zotero before running)
- **Content**: Research sources, clippings, annotations, notes
- **General Reference**: Cross-chapter context materials

### Scrivener Project
- **Location**: Configured in `.env` as `SCRIVENER_PROJECT_PATH`
- **Structure**: Nested folder structure (naming varies by project)
- **Access**: Via Docker indexer
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

## Keeping Structure in Sync

**Critical Design Principle:** The outline, Zotero collections, and Scrivener chapters can drift out of sync as the author revises their book structure.

- **Scrivener is the definitive source of truth** for chapter structure
- The agent should detect and gracefully handle mismatches
- When ambiguity exists, ask clarifying questions
- Proactively suggest checking sync status when you detect issues
- Don't fail - work with available data

**Sync Check Skill:** Use the `check-sync` skill to identify mismatches and provide recommendations.

See `docs/SYNCING.md` for detailed workflow guidance.

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
1. Navigate to Scrivener project (path from `.env`)
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

### Before Running Skills
- Close Zotero application (database lock conflict)
- Start Qdrant: `docker compose up -d`
- Ensure data is indexed (run indexer scripts if needed)
- Verify environment variable: `QDRANT_URL=http://localhost:6333`

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
Collections follow the pattern defined in `data/project.json` (typically `{number}. {title}`)
Example: "1. Chapter Title", "2. Another Chapter Title"

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
Core dependencies (install with `uv sync`):
- `qdrant-client` - Vector database client
- `sentence-transformers` - For embeddings
- `structlog` - Structured logging

### External Services
- Qdrant vector database (runs in Docker)
- Zotero desktop application (for database access)

## Claude Code Skills

This project uses Claude Code skills (not MCP servers) for research analysis. Skills are located in `.claude/skills/`:

### Available Skills

1. **search-research** - Semantic search through indexed materials
   - Query Zotero and Scrivener content
   - Filter by chapter or source type
   - Returns relevant chunks with similarity scores

2. **get-annotations** - Retrieve Zotero annotations
   - Get all highlights, notes, and comments for a chapter
   - Organized by source document
   - Includes annotation types and colors

3. **analyze-gaps** - Identify research gaps
   - Analyze source density and coverage
   - Compare chapters to find weak areas
   - Get recommendations for additional research

4. **find-similar** - Detect similar or duplicate content
   - Check for redundancy across sources
   - Verify draft text against sources (plagiarism check)
   - Configurable similarity threshold

5. **get-chapter-info** - Comprehensive chapter overview
   - Zotero collection details and source counts
   - Scrivener structure and word counts
   - Research density assessment

### Using Skills

Skills are automatically available in Claude Code. Example usage:
```
"Search for early DEC firewall implementations in chapter 2"
"Get all annotations for chapter 9"
"Analyze research gaps across the manuscript"
```

## Error Handling

### Common Issues
1. **Zotero database locked**: Close Zotero application before running skills
2. **Qdrant not running**: Start with `docker compose up -d`
3. **No indexed data**: Run indexer scripts to populate vector database
4. **Module not found errors**: Run `uv sync` to install dependencies
5. **Empty results**: Check that chapter number matches Zotero collection naming

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

## Project-Specific Context

The agent gets book context from two sources:

1. **Scrivener Project Structure** (automatic, definitive)
   - Chapter hierarchy, numbers, and titles parsed from `.scrivx` file
   - Scrivener is the source of truth for chapter structure
   - No manual maintenance needed

2. **`data/outline.txt`** (manual, narrative context)
   - Themes, key concepts, argument structure
   - Narrative descriptions of what each section accomplishes
   - Important terminology and frameworks
   - Copy from `data/outline.example.txt` to get started
   - Update when themes/concepts evolve (not when chapters move)

Both are combined into the system prompt to give the agent full context.

## Future Enhancements

Potential additions:
- Cross-chapter theme tracking
- Research gap identification
- Citation export for final manuscript
- Progress tracking dashboard
- Automated outline suggestions
