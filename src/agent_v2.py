"""Simplified ReAct agent for book research.

This agent uses a plan-research-analyze-respond loop with direct tool access.
Much simpler than the complex multi-node architecture.

Supports offline operation via Ollama fallback when online LLM is unavailable.
"""

import os

import structlog
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from openai import APIConnectionError

from .tools import ALL_TOOLS, initialize_rag

logger = structlog.get_logger()

# Global flag to track if we're using offline mode
_using_offline_mode = False


def load_book_context() -> str:
    """Load book context from Scrivener structure and outline.txt."""
    from pathlib import Path

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


def test_llm_connection(llm: ChatOpenAI, timeout: int = 5) -> bool:
    """Test if an LLM is reachable.

    Args:
        llm: LLM instance to test
        timeout: Connection timeout in seconds

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Simple test prompt
        llm.invoke(
            [{"role": "user", "content": "Say 'OK' if you can read this."}],
            config={"timeout": timeout},
        )
        return True
    except (APIConnectionError, Exception) as e:
        logger.debug("LLM connection test failed", error=str(e))
        return False


def create_llm_with_fallback() -> tuple[ChatOpenAI, bool]:
    """Create LLM instance with automatic Ollama fallback.

    Tries to connect to online LLM first. If that fails, falls back to
    local Ollama instance for offline operation.

    Returns:
        Tuple of (llm_instance, is_offline_mode)
    """
    # Try online LLM first
    litellm_url = os.getenv("OPENAI_API_BASE") or os.getenv(
        "LITELLM_PROXY_URL", "http://localhost:4000"
    )
    litellm_key = os.getenv("OPENAI_API_KEY") or os.getenv("LITELLM_API_KEY", "sk-1234")
    online_model = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-haiku")

    logger.info(
        "Attempting to connect to online LLM", model=online_model, url=litellm_url
    )

    online_llm = ChatOpenAI(
        model=online_model, base_url=litellm_url, api_key=litellm_key, temperature=0.7
    )

    if test_llm_connection(online_llm):
        logger.info("✓ Connected to online LLM", model=online_model)
        return online_llm, False

    # Fallback to Ollama
    logger.warning("⚠ Online LLM unavailable, falling back to Ollama")

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    offline_model = os.getenv("OFFLINE_AGENT_MODEL", "llama3.2:3b")

    logger.info("Attempting to connect to Ollama", model=offline_model, url=ollama_url)

    offline_llm = ChatOpenAI(
        model=offline_model,
        base_url=ollama_url,
        api_key="ollama",  # Ollama doesn't need a real key
        temperature=0.7,
    )

    if test_llm_connection(offline_llm, timeout=10):
        logger.info("✓ Connected to Ollama (offline mode)", model=offline_model)
        return offline_llm, True

    # If both fail, return online LLM anyway and let it fail with a proper error
    logger.error("⨯ Both online LLM and Ollama are unavailable")
    return online_llm, False


def is_using_offline_mode() -> bool:
    """Check if agent is running in offline mode.

    Returns:
        True if using Ollama, False if using online LLM
    """
    return _using_offline_mode


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


def create_research_agent():
    """Create the book research ReAct agent with automatic offline fallback.

    Attempts to connect to online LLM first. If unavailable, falls back to
    local Ollama for offline operation.

    Returns:
        LangGraph compiled agent that can be invoked with user queries
    """
    global _using_offline_mode

    # Create LLM with automatic fallback
    llm, is_offline = create_llm_with_fallback()
    _using_offline_mode = is_offline

    # Pre-initialize RAG to avoid parallel initialization race conditions
    # This loads the embedding model once before any tools are called
    initialize_rag()

    # Create ReAct agent using LangGraph prebuilt
    # This automatically handles the ReAct loop with tool calling
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,  # System prompt for the agent
    )

    return agent
