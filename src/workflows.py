"""High-level workflow skills for the book research agent.

Workflow skills orchestrate multiple tools to accomplish complex tasks.
These are intended as workflow entry points that the LLM will then
break down into individual tool calls.

Note: This module is separate from src/skills/ which contains analysis utilities.
"""

import json
from typing import Any

from claude_agent_sdk import tool


@tool(
    "analyze_chapter",
    "Comprehensive chapter analysis workflow: research, gaps, themes, sources",
    {"chapter": int},
)
async def analyze_chapter(args: dict[str, Any]) -> dict[str, Any]:
    """Run full chapter analysis including research search, annotations,
    source diversity, key sources, and cross-chapter themes.

    This is a skill that signals to the LLM to orchestrate multiple tools.
    The LLM will call this, then decide which sub-tools to use.
    """
    chapter = args["chapter"]

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "workflow": "analyze_chapter",
                        "chapter": chapter,
                        "next_steps": [
                            "Use get_chapter_info to get basic stats",
                            "Use search_research to find key themes",
                            "Use get_annotations to review highlights",
                            "Use analyze_source_diversity to check source balance",
                            "Use identify_key_sources to find most-cited sources",
                            "Synthesize findings into comprehensive analysis",
                        ],
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "check_sync_workflow",
    "Check sync status and provide detailed recommendations",
    {},
)
async def check_sync_workflow(args: dict[str, Any]) -> dict[str, Any]:
    """Check sync status between outline, Zotero, and Scrivener,
    then provide detailed recommendations for fixing issues.

    This is a skill that signals to the LLM to orchestrate multiple tools.
    """
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "workflow": "check_sync_workflow",
                        "next_steps": [
                            "Use check_sync to identify mismatches",
                            "Use list_chapters to verify Scrivener structure",
                            "Use get_chapter_info to check indexed content",
                            "Provide specific recommendations for each issue",
                        ],
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "research_gaps",
    "Identify chapters that need more research",
    {},
)
async def research_gaps(args: dict[str, Any]) -> dict[str, Any]:
    """Identify chapters with insufficient research materials.

    This is a skill that signals to the LLM to orchestrate multiple tools.
    """
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "workflow": "research_gaps",
                        "next_steps": [
                            "Use list_chapters to get all chapters",
                            "Use get_chapter_info for each chapter to compare source counts",
                            "Use compare_chapters to analyze density differences",
                            "Identify chapters with significantly fewer sources",
                            "Provide recommendations for filling gaps",
                        ],
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "track_theme",
    "Follow a concept or theme across all chapters",
    {"theme": str},
)
async def track_theme(args: dict[str, Any]) -> dict[str, Any]:
    """Track how a specific theme or concept appears throughout the book.

    This is a skill that signals to the LLM to orchestrate multiple tools.
    """
    theme = args["theme"]

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "workflow": "track_theme",
                        "theme": theme,
                        "next_steps": [
                            "Use find_cross_chapter_themes to search for the theme",
                            "Use search_research with the theme keyword for each chapter",
                            "Identify patterns in how theme evolves across chapters",
                            "Note connections and variations in treatment",
                            "Suggest opportunities for stronger thematic connections",
                        ],
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "export_research",
    "Generate formatted research summary or bibliography",
    {"chapter": int, "output_type": str},
)
async def export_research(args: dict[str, Any]) -> dict[str, Any]:
    """Generate formatted output for a chapter (summary or bibliography).

    This is a skill that signals to the LLM to orchestrate multiple tools.

    Args:
        chapter: Chapter number
        output_type: "summary" or "bibliography"
    """
    chapter = args["chapter"]
    output_type = args.get("output_type", "summary")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "workflow": "export_research",
                        "chapter": chapter,
                        "output_type": output_type,
                        "next_steps": [
                            "Use get_chapter_info to verify chapter exists",
                            "Use export_chapter_summary if output_type is 'summary'",
                            "Use generate_bibliography if output_type is 'bibliography'",
                            "Format output for user consumption",
                        ],
                    },
                    indent=2,
                ),
            }
        ]
    }


# All skills available to the agent
ALL_SKILLS = [
    analyze_chapter,
    check_sync_workflow,
    research_gaps,
    track_theme,
    export_research,
]
