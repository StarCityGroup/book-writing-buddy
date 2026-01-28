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

- `main.py` - TUI agent entry point
- `config/` - Project configuration files
- `src/` - Source code (agent, tools, indexing, etc.)
- `scripts/` - **Working scripts and utilities**
- `docs/` - **Documentation, architecture diagrams, migration notes**
- `data/` - Data files (outline.txt, vector database)
- `CLAUDE.md` - This file (project context and instructions)

## File Organization Rules

**IMPORTANT**: Keep the root directory clean!

### Where to Put Files

- **Working scripts** → `scripts/`
  - Example: `test_agent.py`, `debug_tools.py`, `benchmark.py`
  - Temporary utility scripts, test scripts, debugging tools

- **Documentation & reports** → `docs/`
  - Example: `ARCHITECTURE_V2.md`, `MIGRATION_COMPLETE.md`, `WORKFLOW_FIXES.md`
  - Architecture diagrams, migration notes, design decisions, analysis reports
  - Markdown files explaining how things work

- **Source code** → `src/`
  - Core application code, modules, libraries

- **Configuration** → `config/` or root `.env`
  - Settings files, environment configuration

- **Data files** → `data/`
  - Outline files, project-specific data
  - NOT the vector database (that's in `data/qdrant_storage/`)

### Do NOT Create in Root

❌ `WORKFLOW_FIXES.md` → ✅ `docs/WORKFLOW_FIXES.md`
❌ `test_script.py` → ✅ `scripts/test_script.py`
❌ `debug_agent.py` → ✅ `scripts/debug_agent.py`

The only markdown files allowed in root are:
- `README.md` (project overview)
- `CLAUDE.md` (this file)
- `LICENSE.md`

## Data Sources

Project-specific details are configured in `data/project.json` (copy from `data/project.example.json` and customize).

### Zotero Collections
- **Structure**: Nested hierarchy under a root collection
  - Root collection name configured in `.env` as `ZOTERO_ROOT_COLLECTION` (optional)
  - If set, only indexes collections under that root collection
  - If not set, indexes all collections
  - Special collections: General Reference (cross-chapter context), __incoming (unsorted)
  - Chapter collections organized by parts
- **Pattern**: Chapters typically numbered with format `{number}. {title}`
- **Location**: Local Zotero database (path set in `.env` as `ZOTERO_PATH`)
- **Access**: Via Docker indexer (must close Zotero before running)
- **Content**: Research sources, clippings, annotations, notes
- **General Reference**: Cross-chapter context materials
- **Scoping**: Set `ZOTERO_ROOT_COLLECTION=<collection_name>` in `.env` to limit indexing to a specific collection tree

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

### Tool Architecture
- **Direct SDK Tools**: 12 core research tools provide direct access to vector database
- **Workflow Skills**: 5 high-level skills orchestrate multiple tools for complex tasks
- **No MCP Wrapper**: Tools use Claude Agent SDK directly for better performance
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

## Research Tools

The agent uses **Claude Agent SDK** with custom tools and workflow skills (no MCP wrapper).

### Tool Categories

**Core Tools (12):**
- `search_research`, `get_annotations`, `get_chapter_info`, `list_chapters`
- `check_sync`, `get_scrivener_summary`, `compare_chapters`
- `find_cross_chapter_themes`, `analyze_source_diversity`, `identify_key_sources`
- `export_chapter_summary`, `generate_bibliography`

**Workflow Skills (5):**
- `analyze_chapter` - Full chapter analysis workflow
- `check_sync_workflow` - Sync check with recommendations
- `research_gaps` - Identify chapters needing research
- `track_theme` - Follow concepts across chapters
- `export_research` - Generate formatted summaries

## TUI Agent Capabilities

The interactive TUI agent (`uv run main.py`) provides natural language access to all research tools.

### Core Query Types

**Semantic Search:**
- "Search for climate adaptation research in chapter 5"
- "Find sources about urban heat islands"

**Annotations & Notes:**
- "Get all my Zotero annotations for chapter 9"
- "Show me highlights from chapter 3 sources"

**Gap Analysis:**
- "Which chapters need more research?"
- "Analyze research gaps across the manuscript"

**Similarity Detection:**
- "Find similar content to this paragraph: [text]"
- "Check for duplicate content"

**Structure & Organization:**
- "List all my chapters"
- "Check if my chapters are in sync"
- "Show me a Scrivener summary"
- "How many Scrivener documents are indexed per chapter?"

### Advanced Analysis Features (NEW)

**Cross-Chapter Theme Tracking:**
Track concepts and themes across the entire manuscript to maintain consistency:
- "Track the theme 'resilience' across all chapters"
- "Where does 'infrastructure failure' appear in the book?"
- "Find mentions of 'adaptation trap' across chapters"

Uses semantic search to find related content even when exact wording differs.

**Chapter Comparison:**
Compare research density, source counts, and coverage between chapters:
- "Compare research density between chapters 5 and 9"
- "Which has more sources, chapter 3 or chapter 7?"
- "Compare chapters 2 and 8"

Helps identify chapters that need more research and maintain balanced coverage.

**Source Diversity Analysis:**
Evaluate source type balance using Simpson's Diversity Index:
- "Analyze source diversity for chapter 3"
- "Am I relying too heavily on one type of source in chapter 9?"
- "What types of sources does chapter 5 use?"

Ensures academic rigor through balanced mix of books, articles, reports, etc.

**Key Source Identification:**
Find most-referenced sources in each chapter:
- "What are the key sources for chapter 9?"
- "Show me the most cited sources in chapter 12"
- "Which sources am I referencing most in chapter 3?"

Helps ensure you're not over-relying on single sources.

**Export & Summarization:**
Generate formatted research summaries and bibliographies:
- "Export a research summary for chapter 7"
- "Generate an APA bibliography for chapter 4"
- "Create a research brief for chapter 5 in markdown"
- "Show me citations for chapter 9 in MLA format"

Perfect for preparing reference materials before writing sessions.

**Research Timeline:**
Track when research materials were collected:
- "What research have I added recently?"
- "Show me the research timeline for chapter 9"
- "What did I index last week?"
- "Timeline of research collection for the whole book"

Helps identify research collection patterns and gaps over time.

**Smart Cross-References:**
Get AI-powered suggestions for relevant research from other chapters:
- "Suggest related research for chapter 5"
- "What from other chapters is relevant to chapter 8?"
- "Find cross-references for chapter 12"

Uses semantic similarity to discover connections you might have missed.

**Scrivener Indexing Summary:**
Get detailed breakdown of indexed Scrivener documents per chapter:
- "Show me a Scrivener summary"
- "How many Scrivener documents are indexed?"
- "What's the Scrivener breakdown per chapter?"
- "Show indexed Scrivener documents by chapter"

Provides comprehensive statistics including:
- Total documents, chunks, and word counts
- Per-chapter breakdown with document types (draft, note, synopsis)
- Identification of unassigned documents
- Helps verify that your Scrivener project is properly indexed

### How Agent Routing Works

The agent automatically classifies your query and routes to the appropriate tool:

1. **Planning Phase**: Understands your question and intent
2. **Tool Execution**: Runs the right BookRAG method(s)
3. **Analysis Phase**: AI synthesizes results into actionable insights
4. **Refinement** (optional): Provides follow-up details if you ask

All queries are handled conversationally - no need to learn specific commands or syntax.

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
