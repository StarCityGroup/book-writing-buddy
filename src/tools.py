"""LangChain tools for book research agent.

These tools wrap BookRAG methods and provide direct access to the vector database
and research capabilities. The agent can use these flexibly to gather information.
"""

from typing import Optional

from langchain_core.tools import tool

from .rag import BookRAG


# Initialize RAG instance (shared across all tools)
_rag_instance = None


def get_rag() -> BookRAG:
    """Get or create shared RAG instance."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = BookRAG()
    return _rag_instance


# =============================================================================
# Core Research Tools
# =============================================================================


@tool
def search_research(
    query: str, chapter: Optional[int] = None, limit: int = 20
) -> dict:
    """Search semantically through research materials.

    Use this to find relevant information from Zotero sources and Scrivener drafts.

    Args:
        query: What to search for (e.g., "infrastructure failure", "heat adaptation")
        chapter: Optional chapter number to limit search (e.g., 9)
        limit: Maximum results to return (default 20)

    Returns:
        Dict with search results including text, sources, and relevance scores
    """
    rag = get_rag()
    filters = {"chapter_number": chapter} if chapter else None
    results = rag.search(query=query, filters=filters, limit=limit, score_threshold=0.6)

    # Format for easy consumption
    return {
        "query": query,
        "chapter_filter": chapter,
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


@tool
def get_annotations(chapter: Optional[int] = None) -> dict:
    """Get Zotero annotations and highlights for a chapter.

    Retrieves all your highlights, notes, and annotations from Zotero sources.

    Args:
        chapter: Chapter number (if None, gets all annotations)

    Returns:
        Dict with annotations organized by source document
    """
    rag = get_rag()
    return rag.get_annotations(chapter=chapter)


@tool
def get_chapter_info(chapter_number: int) -> dict:
    """Get comprehensive information about a specific chapter.

    Includes source counts, word counts, and indexed content statistics.

    Args:
        chapter_number: The chapter to get info about

    Returns:
        Dict with chapter metadata and statistics
    """
    rag = get_rag()
    return rag.get_chapter_info(chapter_number=chapter_number)


@tool
def list_chapters() -> dict:
    """List all chapters from the Scrivener project.

    Returns the definitive chapter structure with numbers and titles.

    Returns:
        Dict with project name and list of chapters
    """
    rag = get_rag()
    return rag.list_chapters()


@tool
def check_sync() -> dict:
    """Check sync status between outline, Zotero, and Scrivener.

    Identifies mismatches and provides recommendations.

    Returns:
        Dict with sync status, mismatches, and recommendations
    """
    rag = get_rag()
    return rag.check_sync()


@tool
def get_scrivener_summary() -> dict:
    """Get detailed breakdown of indexed Scrivener documents per chapter.

    Shows how many documents, chunks, and words are indexed for each chapter.

    Returns:
        Dict with per-chapter Scrivener indexing statistics
    """
    rag = get_rag()
    return rag.get_scrivener_summary()


# =============================================================================
# Analysis Tools
# =============================================================================


@tool
def compare_chapters(chapter1: int, chapter2: int) -> dict:
    """Compare research density and coverage between two chapters.

    Shows which chapter has more sources, research density, etc.

    Args:
        chapter1: First chapter number
        chapter2: Second chapter number

    Returns:
        Dict with comparison metrics
    """
    rag = get_rag()
    return rag.compare_chapters(chapter1=chapter1, chapter2=chapter2)


@tool
def find_cross_chapter_themes(keyword: str) -> dict:
    """Track a theme or concept across all chapters.

    Finds where a theme appears and how it's discussed in different chapters.

    Args:
        keyword: Theme to track (e.g., "resilience", "infrastructure failure")

    Returns:
        Dict with chapters containing theme and relevant excerpts
    """
    rag = get_rag()
    return rag.find_cross_chapter_themes(keyword=keyword, min_chapters=1)


@tool
def analyze_source_diversity(chapter: int) -> dict:
    """Analyze diversity of source types for a chapter.

    Checks if chapter relies too heavily on one type of source.

    Args:
        chapter: Chapter number to analyze

    Returns:
        Dict with source type breakdown and diversity score
    """
    rag = get_rag()
    return rag.analyze_source_diversity(chapter=chapter)


@tool
def identify_key_sources(chapter: int) -> dict:
    """Find the most-cited sources in a chapter.

    Shows which sources you reference most frequently.

    Args:
        chapter: Chapter number to analyze

    Returns:
        Dict with key sources and citation counts
    """
    rag = get_rag()
    return rag.identify_key_sources(chapter=chapter, min_mentions=2)


# =============================================================================
# Export Tools
# =============================================================================


@tool
def export_chapter_summary(chapter: int, format: str = "markdown") -> dict:
    """Generate a formatted research summary for a chapter.

    Creates a comprehensive overview of research for the chapter.

    Args:
        chapter: Chapter number to export
        format: Output format ("markdown", "text", or "json")

    Returns:
        Dict with chapter number and formatted summary
    """
    rag = get_rag()
    summary = rag.export_chapter_summary(chapter=chapter, format=format)
    return {"chapter": chapter, "format": format, "summary": summary}


@tool
def generate_bibliography(chapter: Optional[int] = None, style: str = "apa") -> dict:
    """Generate formatted bibliography from Zotero sources.

    Creates citation list in APA, MLA, or Chicago style.

    Args:
        chapter: Optional chapter number (None for all chapters)
        style: Citation style ("apa", "mla", "chicago", or "raw")

    Returns:
        Dict with list of formatted citations
    """
    rag = get_rag()
    bibliography = rag.generate_bibliography(chapter=chapter, style=style)
    return {
        "chapter": chapter,
        "style": style,
        "citation_count": len(bibliography),
        "citations": bibliography,
    }


# =============================================================================
# Tool List for Agent
# =============================================================================

ALL_TOOLS = [
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
]
