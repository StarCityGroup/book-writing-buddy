# Workflow Skills

This directory contains workflow skill definitions in markdown format. Skills are automatically discovered and loaded when the agent starts.

## What are Workflow Skills?

Workflow skills are high-level orchestrators that combine multiple research tools to accomplish complex tasks. When you invoke a skill, the agent:

1. Receives workflow guidance (which tools to use and in what order)
2. Executes the appropriate tools based on the context
3. Synthesizes results into a comprehensive response

## How to Add a New Skill

Create a new `.md` file in this directory with the following format:

```markdown
# Skill Title

**Name:** `skill_name`

**Description:** Brief one-line description of what this skill does

**Parameters:**
- `param1` (int, required): Description of parameter
- `param2` (str, optional): Description of parameter

**Workflow Steps:**

1. First step: Use tool X to do Y
2. Second step: Use tool Z to do W
3. Final step: Synthesize results into response

**Example Usage:**
- "Example query that triggers this skill"
- "Another example query"
- "Third example"
```

## Available Tools

Your workflow can reference any of these core research tools:

**Core Research:**
- `search_research` - Semantic search with filters
- `get_annotations` - Zotero highlights and notes
- `get_chapter_info` - Chapter statistics
- `list_chapters` - Book structure
- `check_sync` - Alignment status
- `get_scrivener_summary` - Indexing breakdown

**Analysis:**
- `compare_chapters` - Compare research density
- `find_cross_chapter_themes` - Track concepts
- `analyze_source_diversity` - Check source balance
- `identify_key_sources` - Find key citations

**Export:**
- `export_chapter_summary` - Generate research brief
- `generate_bibliography` - Create citation list

## Example Skills

See the existing `.md` files in this directory for examples:
- `analyze_chapter.md` - Comprehensive chapter analysis
- `track_theme.md` - Cross-chapter theme tracking
- `research_gaps.md` - Identify under-researched chapters

## Tips

1. **Keep descriptions concise** - One sentence that clearly states the purpose
2. **List specific tools** - Don't just say "analyze data", say "Use get_chapter_info to..."
3. **Provide examples** - Show what queries would trigger this skill
4. **Parameters are typed** - Use `int`, `str`, `bool`, or `float`
5. **Mark required params** - Add "required" or "optional" after the type

## How It Works

The `src/skill_loader.py` module:
1. Scans this directory for `.md` files
2. Parses the markdown format
3. Creates SDK tool functions dynamically
4. Registers them with the agent

Changes to `.md` files take effect on next agent restart.
