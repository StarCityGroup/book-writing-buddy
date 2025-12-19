"""LangGraph agent for book research."""

from langgraph.graph import END, StateGraph

from .nodes import BookResearchNodes
from .state import AgentState


def create_agent():
    """Create the book research LangGraph agent.

    Returns:
        Compiled StateGraph
    """
    # Initialize nodes
    nodes = BookResearchNodes()

    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("planning", nodes.planning_node)
    workflow.add_node("search", nodes.search_node)
    workflow.add_node("annotations", nodes.annotations_node)
    workflow.add_node("gap_analysis", nodes.gap_analysis_node)
    workflow.add_node("similarity", nodes.similarity_node)
    workflow.add_node("chapter_info", nodes.chapter_info_node)
    workflow.add_node("check_sync", nodes.check_sync_node)
    workflow.add_node("list_chapters", nodes.list_chapters_node)
    workflow.add_node("analyze", nodes.analyze_node)
    workflow.add_node("refine", nodes.refinement_node)

    # Define routing logic
    def route_from_planning(state: AgentState) -> str:
        """Route from planning phase based on query type."""
        phase = state.get("current_phase", "planning")

        if phase == "error":
            return END
        elif phase == "search":
            return "search"
        elif phase == "annotations":
            return "annotations"
        elif phase == "gap_analysis":
            return "gap_analysis"
        elif phase == "similarity":
            return "similarity"
        elif phase == "chapter_info":
            return "chapter_info"
        elif phase == "check_sync":
            return "check_sync"
        elif phase == "list_chapters":
            return "list_chapters"
        else:
            return END

    def route_from_analysis(state: AgentState) -> str:
        """Route from analysis phase."""
        phase = state.get("current_phase", "complete")

        if phase == "error":
            return END

        # Check if user provided feedback for refinement
        if state.get("user_feedback"):
            return "refine"

        return END

    # Set entry point
    workflow.set_entry_point("planning")

    # Add edges
    workflow.add_conditional_edges("planning", route_from_planning)

    # All tool nodes flow to analysis
    workflow.add_edge("search", "analyze")
    workflow.add_edge("annotations", "analyze")
    workflow.add_edge("gap_analysis", "analyze")
    workflow.add_edge("similarity", "analyze")
    workflow.add_edge("chapter_info", "analyze")
    workflow.add_edge("check_sync", "analyze")
    workflow.add_edge("list_chapters", "analyze")

    # Analysis can go to refinement or end
    workflow.add_conditional_edges("analyze", route_from_analysis)

    # Refinement loops back to analysis
    workflow.add_edge("refine", "analyze")

    # Compile
    return workflow.compile()
