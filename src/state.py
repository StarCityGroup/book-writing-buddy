"""State management for the book research agent."""

from typing import Annotated, List, Optional

from langgraph.graph.message import add_messages


class AgentState(dict):
    """State for the book research agent.

    Inheriting from dict allows LangGraph to properly merge state updates.
    """

    # Conversation
    messages: Annotated[List[dict], add_messages]

    # Research query
    research_query: Optional[str]

    # Tool results
    search_results: List[dict]
    annotations: Optional[dict]
    gap_analysis: Optional[dict]
    similarity_results: Optional[dict]

    # Workflow control
    current_phase: str  # planning, searching, analyzing, refining, complete
    needs_user_input: bool
    user_feedback: Optional[str]
    iteration_count: int


def create_initial_state() -> AgentState:
    """Create initial agent state.

    Returns:
        Initial state dictionary
    """
    return AgentState(
        messages=[],
        research_query=None,
        search_results=[],
        annotations=None,
        gap_analysis=None,
        similarity_results=None,
        chapter_info=None,
        sync_status=None,
        chapters_list=None,
        cross_chapter_theme=None,
        chapter_comparison=None,
        source_diversity=None,
        key_sources=None,
        export_summary=None,
        bibliography=None,
        timeline=None,
        related_research=None,
        scrivener_summary=None,
        current_phase="planning",
        needs_user_input=False,
        user_feedback=None,
        iteration_count=0,
    )
