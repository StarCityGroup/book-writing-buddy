"""Book research agent using Claude Agent SDK.

This agent uses the Claude Agent SDK with custom tools for research operations.
"""

import os
from pathlib import Path

import structlog
from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server

from .skill_loader import load_all_skills
from .tools import ALL_TOOLS, initialize_rag

logger = structlog.get_logger()


def load_book_context() -> str:
    """Load book context from Scrivener structure and outline.txt."""
    parts = []

    # 1. Get Scrivener chapter structure (definitive)
    scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
    scrivener_manuscript_folder = os.getenv("SCRIVENER_MANUSCRIPT_FOLDER", "")
    if scrivener_path and Path(scrivener_path).exists():
        try:
            from .scrivener_parser import ScrivenerParser

            parser = ScrivenerParser(
                scrivener_path, manuscript_folder=scrivener_manuscript_folder or None
            )
            structure = parser.format_structure_as_text()
            parts.append(structure)
        except Exception as e:
            parts.append(f"# Scrivener Structure\n\nCould not parse: {e}\n")
    else:
        parts.append("# Scrivener Structure\n\nPath not configured in .env\n")

    # 2. Get narrative outline (provides context, themes, descriptions)
    outline_path = Path(__file__).parent.parent / "data" / "outline.txt"
    if outline_path.exists():
        parts.append("# Book Outline & Context\n\n" + outline_path.read_text())
    else:
        parts.append(
            "# Book Outline\n\nNo outline file found. "
            "Create `data/outline.txt` with narrative context about your book."
        )

    return "\n\n---\n\n".join(parts)


BOOK_CONTEXT = load_book_context()


SYSTEM_PROMPT = f"""You are an AI research assistant helping an author analyze their book research materials.

# Your Capabilities

You have DIRECT ACCESS to a vector database containing:
- **6,378+ indexed chunks** from Zotero research library and Scrivener manuscript
- **All Zotero sources**: PDFs, articles, web pages, books, with full text and annotations
- **All Scrivener content**: Chapter drafts, research notes, outlines, synopses
- **Indexed by chapter**: Each chunk tagged with chapter number for filtering

You can query this data using 12 powerful tools:

**Core Research:**
- search_research: Semantic search with optional chapter and source_type filters
  * source_type="zotero" → Search ONLY published research papers, articles, books
  * source_type="scrivener" → Search ONLY manuscript drafts and notes
  * source_type=None → Search BOTH (default)
- get_annotations: Zotero highlights and notes
- get_chapter_info: Detailed chapter statistics
- list_chapters: Book structure from Scrivener
- check_sync: Alignment status between sources
- get_scrivener_summary: Indexing breakdown per chapter

**Analysis:**
- compare_chapters: Compare research density
- find_cross_chapter_themes: Track concepts across chapters
- analyze_source_diversity: Check source balance
- identify_key_sources: Find most-cited sources

**Export:**
- export_chapter_summary: Generate research brief
- generate_bibliography: Create citation list (APA/MLA/Chicago)

# High-Level Skills

You also have access to skills that orchestrate multiple tools for common workflows:

- **analyze_chapter**: Run comprehensive chapter analysis (research, gaps, themes, sources)
- **check_sync_workflow**: Check sync status and provide detailed recommendations
- **research_gaps**: Identify chapters that need more research
- **track_theme**: Follow a concept or theme across all chapters
- **export_research**: Generate formatted research summary or bibliography

Use skills for complex requests that require multiple tools. Use individual tools for targeted queries.
When you invoke a skill, it will provide guidance on which tools to use next - follow that guidance
to complete the workflow.

# Book Context

{BOOK_CONTEXT}

# How to Respond to Queries

1. **Plan Your Research**: Think about what tools will help answer the question
2. **Gather Data**: Use tools to collect relevant information (you can use multiple tools)
3. **Synthesize**: Analyze the results and identify key insights
4. **Respond**: Present findings clearly with specific citations

## Important Guidelines

- **Be thorough**: Use as many tools as needed to fully answer the question
- **Cite sources**: Always reference specific sources when presenting findings
- **Note gaps**: If data is missing or incomplete, say so clearly
- **Cross-reference**: Make connections between Zotero sources and Scrivener drafts
- **Use chapter context**: When relevant, show how findings relate to the book's structure
- **Handle sync issues**: If you notice mismatches between outline/Zotero/Scrivener, mention them

## When to Filter by Source Type

**Use source_type="zotero"** when:
- User asks about "research", "sources", "papers", "studies", or "literature"
- Looking for published evidence, facts, citations, or expert opinions
- Analyzing research gaps or identifying missing sources
- User wants to know "what research exists" on a topic

**Use source_type="scrivener"** when:
- User asks about "draft", "manuscript", "notes", or "what I wrote"
- Checking what's already written in the manuscript
- Finding the author's own thoughts and ideas
- Reviewing chapter content or structure

**Use source_type=None (search both)** when:
- User doesn't specify which source they want
- Looking for general information on a topic
- Want to see how research connects to draft content
- Default behavior for most queries

## Interpreting Search Results

When presenting search results, ALWAYS acknowledge the source type:
- **Zotero results** (source_type="zotero"): These are PUBLISHED research papers, books, articles
  - Cite as: "According to [Source Title] (Zotero research)..."
  - Example: "According to 'Urban Heat Islands' (Zotero research), heat exposure increases mortality by 15%"
- **Scrivener results** (source_type="scrivener"): These are the AUTHOR'S OWN draft notes and text
  - Cite as: "From your manuscript draft (Chapter X)..."
  - Example: "From your manuscript draft (Chapter 13), you noted that 'heat mapping requires hyperlocal resolution'"

This distinction is CRITICAL - the user needs to know whether findings come from published research or their own work.

## When You Don't Have Data

If tool results are empty or insufficient:
- Explain what you searched for and what you found (or didn't find)
- Suggest what might be missing (e.g., "This chapter may need more research")
- Recommend next steps (e.g., "Run a sync check to identify mismatches")
- DON'T say "I don't have access" - you DO have access, the data just isn't indexed yet

## Response Format

Structure your responses as:
1. **Summary**: Brief answer to the question
2. **Key Findings**: Specific details with citations
3. **Analysis**: Insights and connections
4. **Recommendations** (if applicable): Suggested actions

Use markdown formatting for clarity.
"""


def create_agent_options() -> ClaudeAgentOptions:
    """Create Claude Agent SDK options.

    Returns:
        ClaudeAgentOptions configured with research tools and system prompt
    """
    # Get LiteLLM proxy credentials from environment
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_base = os.getenv("OPENAI_API_BASE", "")

    # Determine if we're using LiteLLM proxy
    using_litellm = bool(
        api_base and ("litellm" in api_base.lower() or "cornell" in api_base.lower())
    )

    # Get model from environment
    model_env = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-sonnet")

    if using_litellm:
        # When using LiteLLM, keep the full model name format
        model_name = model_env
    else:
        # When using Anthropic directly, convert to SDK format
        if model_env.startswith("anthropic."):
            model_env = model_env.replace("anthropic.", "")

        # Map common names to SDK format
        model_mapping = {
            "claude-4.5-haiku": "claude-haiku-4-5-20250514",
            "claude-4.5-sonnet": "claude-sonnet-4-5-20250514",
            "claude-4.5-opus": "claude-opus-4-5-20251001",
        }
        model_name = model_mapping.get(model_env, model_env)

    # Pre-initialize RAG to avoid parallel initialization race conditions
    initialize_rag()

    # CRITICAL: Set environment variables in os.environ BEFORE creating SDK client
    # The SDK checks os.environ during transport auto-detection to decide whether
    # to use API transport or CLI transport. If ANTHROPIC_API_KEY is not found,
    # it falls back to subprocess CLI mode which expects tool names (strings),
    # not tool objects.
    logger.debug(
        "Setting SDK environment variables",
        has_api_key=bool(api_key),
        has_api_base=bool(api_base),
        api_key_prefix=api_key[:10] if api_key else None,
        api_base=api_base,
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        logger.debug("Set ANTHROPIC_API_KEY in os.environ")
    if api_base:
        os.environ["ANTHROPIC_BASE_URL"] = api_base
        logger.debug("Set ANTHROPIC_BASE_URL in os.environ")

    # Also prepare env dict for ClaudeAgentOptions (belt and suspenders)
    sdk_env = {}
    if api_key:
        sdk_env["ANTHROPIC_API_KEY"] = api_key
    if api_base:
        sdk_env["ANTHROPIC_BASE_URL"] = api_base

    # Load workflow skills (from code + markdown files)
    all_skills = load_all_skills()

    # Combine tools and skills
    all_tools = ALL_TOOLS + all_skills

    logger.info(
        "Agent tools loaded",
        core_tools=len(ALL_TOOLS),
        workflow_skills=len(all_skills),
        total=len(all_tools),
    )

    # CRITICAL: SdkMcpTools (created by @tool decorator) must be wrapped in an MCP server
    # They cannot be passed directly to the tools parameter
    custom_server = create_sdk_mcp_server(
        name="book-research",
        version="1.0.0",
        tools=all_tools,  # All @tool decorated functions go here
    )

    # Create agent options with MCP server containing custom tools
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"book-research": custom_server},  # MCP server goes here
        allowed_tools=["mcp__book-research__*"],  # Allow all tools from this server
        model=model_name,
        permission_mode="bypassPermissions",  # Auto-approve tool use
        env=sdk_env,  # Pass LiteLLM proxy credentials
    )

    return options
