"""Claude Agent SDK tools for book research agent.

These tools wrap BookRAG methods and provide direct access to the vector database
and research capabilities via MCP (Model Context Protocol).
"""

import json
import threading
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from .rag import BookRAG

# Thread-safe singleton for RAG instance
_rag_instance = None
_rag_lock = threading.Lock()


def get_rag() -> BookRAG:
    """Get or create shared RAG instance (thread-safe)."""
    global _rag_instance
    if _rag_instance is None:
        with _rag_lock:
            # Double-check pattern to prevent race conditions
            if _rag_instance is None:
                _rag_instance = BookRAG()
    return _rag_instance


def initialize_rag() -> None:
    """Pre-initialize RAG instance before agent starts.

    Call this once during application startup to avoid race conditions
    when tools execute in parallel.
    """
    get_rag()  # Trigger initialization


# =============================================================================
# Core Research Tools
# =============================================================================


@tool(
    "search_research",
    "Search semantically through research materials from Zotero and/or Scrivener",
    {
        "query": str,
        "chapter": int,
        "source_type": str,
        "limit": int,
    },
)
async def search_research(args: dict[str, Any]) -> dict[str, Any]:
    """Search semantically through research materials.

    Use this to find relevant information from Zotero sources and/or Scrivener drafts.
    """
    rag = get_rag()

    # Build filters
    filters = {}
    if args.get("chapter"):
        filters["chapter_number"] = args["chapter"]
    if args.get("source_type"):
        filters["source_type"] = args["source_type"]

    results = rag.search(
        query=args["query"],
        filters=filters if filters else None,
        limit=args.get("limit", 20),
        score_threshold=0.6,
    )

    # Format for easy consumption
    output = {
        "query": args["query"],
        "chapter_filter": args.get("chapter"),
        "source_type_filter": args.get("source_type") or "all (zotero + scrivener)",
        "result_count": len(results),
        "results": [
            {
                "text": r["text"][:500],  # Truncate long texts
                "score": f"{r['score']:.0%}",
                "source": r["metadata"].get("title", "Unknown"),
                "chapter": r["metadata"].get("chapter_number"),
                "source_type": r["metadata"].get("source_type"),
            }
            for r in results
        ],
    }

    return {"content": [{"type": "text", "text": json.dumps(output, indent=2)}]}


@tool(
    "get_annotations",
    "Get Zotero annotations and highlights for a chapter",
    {"chapter": int},
)
async def get_annotations(args: dict[str, Any]) -> dict[str, Any]:
    """Get Zotero annotations and highlights for a chapter.

    Retrieves all your highlights, notes, and annotations from Zotero sources.
    """
    rag = get_rag()
    result = rag.get_annotations(chapter=args.get("chapter"))
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "get_chapter_info",
    "Get comprehensive information about a specific chapter",
    {"chapter_number": int},
)
async def get_chapter_info(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive information about a specific chapter.

    Includes source counts, word counts, and indexed content statistics.
    """
    rag = get_rag()
    result = rag.get_chapter_info(chapter_number=args["chapter_number"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "list_chapters",
    "List all chapters from the Scrivener project",
    {},
)
async def list_chapters(args: dict[str, Any]) -> dict[str, Any]:
    """List all chapters from the Scrivener project.

    Returns the definitive chapter structure with numbers and titles.
    """
    rag = get_rag()
    result = rag.list_chapters()
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "check_sync",
    "Check sync status between outline, Zotero, and Scrivener",
    {},
)
async def check_sync(args: dict[str, Any]) -> dict[str, Any]:
    """Check sync status between outline, Zotero, and Scrivener.

    Identifies mismatches and provides recommendations.
    """
    rag = get_rag()
    result = rag.check_sync()
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "get_scrivener_summary",
    "Get detailed breakdown of indexed Scrivener documents per chapter",
    {},
)
async def get_scrivener_summary(args: dict[str, Any]) -> dict[str, Any]:
    """Get detailed breakdown of indexed Scrivener documents per chapter.

    Shows how many documents, chunks, and words are indexed for each chapter.
    """
    rag = get_rag()
    result = rag.get_scrivener_summary()
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


# =============================================================================
# Analysis Tools
# =============================================================================


@tool(
    "compare_chapters",
    "Compare research density and coverage between two chapters",
    {"chapter1": int, "chapter2": int},
)
async def compare_chapters(args: dict[str, Any]) -> dict[str, Any]:
    """Compare research density and coverage between two chapters.

    Shows which chapter has more sources, research density, etc.
    """
    rag = get_rag()
    result = rag.compare_chapters(
        chapter1=args["chapter1"], chapter2=args["chapter2"]
    )
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "find_cross_chapter_themes",
    "Track a theme or concept across all chapters",
    {"keyword": str},
)
async def find_cross_chapter_themes(args: dict[str, Any]) -> dict[str, Any]:
    """Track a theme or concept across all chapters.

    Finds where a theme appears and how it's discussed in different chapters.
    """
    rag = get_rag()
    result = rag.find_cross_chapter_themes(keyword=args["keyword"], min_chapters=1)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "analyze_source_diversity",
    "Analyze diversity of source types for a chapter",
    {"chapter": int},
)
async def analyze_source_diversity(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze diversity of source types for a chapter.

    Checks if chapter relies too heavily on one type of source.
    """
    rag = get_rag()
    result = rag.analyze_source_diversity(chapter=args["chapter"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "identify_key_sources",
    "Find the most-cited sources in a chapter",
    {"chapter": int},
)
async def identify_key_sources(args: dict[str, Any]) -> dict[str, Any]:
    """Find the most-cited sources in a chapter.

    Shows which sources you reference most frequently.
    """
    rag = get_rag()
    result = rag.identify_key_sources(chapter=args["chapter"], min_mentions=2)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


# =============================================================================
# Export Tools
# =============================================================================


@tool(
    "export_chapter_summary",
    "Generate a formatted research summary for a chapter",
    {"chapter": int, "format": str},
)
async def export_chapter_summary(args: dict[str, Any]) -> dict[str, Any]:
    """Generate a formatted research summary for a chapter.

    Creates a comprehensive overview of research for the chapter.
    """
    rag = get_rag()
    summary = rag.export_chapter_summary(
        chapter=args["chapter"], format=args.get("format", "markdown")
    )
    result = {
        "chapter": args["chapter"],
        "format": args.get("format", "markdown"),
        "summary": summary,
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool(
    "generate_bibliography",
    "Generate formatted bibliography from Zotero sources",
    {"chapter": int, "style": str},
)
async def generate_bibliography(args: dict[str, Any]) -> dict[str, Any]:
    """Generate formatted bibliography from Zotero sources.

    Creates citation list in APA, MLA, or Chicago style.
    """
    rag = get_rag()
    bibliography = rag.generate_bibliography(
        chapter=args.get("chapter"), style=args.get("style", "apa")
    )
    result = {
        "chapter": args.get("chapter"),
        "style": args.get("style", "apa"),
        "citation_count": len(bibliography),
        "citations": bibliography,
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


# =============================================================================
# MCP Server Configuration
# =============================================================================

# Create SDK MCP server with all research tools
research_server = create_sdk_mcp_server(
    name="research",
    version="1.0.0",
    tools=[
        search_research,
        get_annotations,
        get_chapter_info,
        list_chapters,
        check_sync,
        get_scrivener_summary,
        compare_chapters,
        find_cross_chapter_themes,
        analyze_source_diversity,
        identify_key_sources,
        export_chapter_summary,
        generate_bibliography,
    ],
)
