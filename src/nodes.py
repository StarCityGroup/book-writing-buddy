"""LangGraph node implementations for the book research agent."""

import os
from pathlib import Path
from typing import Dict, List

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from .rag import BookRAG
from .state import AgentState


def load_book_context() -> str:
    """Load book context from Scrivener structure and outline.txt.

    Returns:
        Combined context with Scrivener structure and narrative outline.
    """
    parts = []

    # 1. Get Scrivener chapter structure (definitive)
    scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
    if scrivener_path and Path(scrivener_path).exists():
        try:
            from .scrivener_parser import ScrivenerParser

            parser = ScrivenerParser(scrivener_path)
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


# Load book context from both sources
BOOK_OUTLINE = load_book_context()


class BookResearchNodes:
    """Node implementations for the book research agent."""

    def __init__(self):
        """Initialize nodes with necessary clients."""
        # LiteLLM proxy configuration
        litellm_url = os.getenv("OPENAI_API_BASE") or os.getenv(
            "LITELLM_PROXY_URL", "http://localhost:4000"
        )
        litellm_key = os.getenv("OPENAI_API_KEY") or os.getenv(
            "LITELLM_API_KEY", "sk-1234"
        )
        model_name = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-haiku")

        self.llm = ChatOpenAI(
            model=model_name,
            base_url=litellm_url,
            api_key=litellm_key,
            temperature=0.7,
        )

        # RAG system
        self.rag = BookRAG()

    def planning_node(self, state: AgentState) -> Dict:
        """Planning phase: understand user's research request.

        Args:
            state: Current agent state

        Returns:
            Updated state
        """
        messages = state["messages"]

        # System prompt for planning
        system_prompt = f"""You are an AI research assistant for analyzing book research materials.

{BOOK_OUTLINE}

Your role in the PLANNING phase is to:
1. Understand the user's research question in the context of the book's structure
2. Determine what type of information they need:
   - **search**: General research questions requiring semantic search
   - **annotations**: Requesting Zotero highlights/notes for a chapter
   - **gap_analysis**: Asking about research coverage or what's missing
   - **similarity**: Checking for duplicate or similar content
3. Briefly acknowledge what you'll look up (1-2 sentences)

Available data:
- Zotero collections organized by chapter
- Scrivener manuscript drafts
- All content indexed in vector database for semantic search

**IMPORTANT - Handling Sync Issues:**
The outline.txt, Zotero collections, and Scrivener chapters may be out of sync as the author revises their structure.
- **Scrivener is the definitive source of truth** for chapter structure
- If you encounter ambiguity or missing data, ask clarifying questions
- If chapter numbers don't match, note this and suggest running the check-sync skill
- Be graceful when information is incomplete - do your best with available data

Keep your response brief - just acknowledge the request. The system will automatically proceed to gather the information."""

        # Helper functions
        def get_msg_content(msg):
            if isinstance(msg, dict):
                return msg.get("content", "")
            return getattr(msg, "content", "")

        def get_msg_role(msg):
            if isinstance(msg, dict):
                return msg.get("role", "")
            return getattr(msg, "type", "")

        # Add system message if this is first planning interaction
        if not any(
            isinstance(get_msg_content(m), str) and "PLANNING phase" in get_msg_content(m)
            for m in messages
        ):
            messages = [{"role": "system", "content": system_prompt}] + list(messages)

        # Get LLM response
        try:
            response = self.llm.invoke(messages)
            updates = {
                "messages": [{"role": "assistant", "content": response.content}],
                "current_phase": "planning",
            }
        except APIConnectionError:
            error_msg = """🔌 **Connection Error**

Unable to connect to the AI model service. Please check your LiteLLM proxy configuration.

**To fix:**
- Ensure LiteLLM proxy is running
- Check OPENAI_API_BASE and OPENAI_API_KEY in your .env file
- Restart the application

Type `/exit` to quit and fix the configuration."""
            return {
                "messages": [{"role": "assistant", "content": error_msg}],
                "current_phase": "error",
                "needs_user_input": True,
            }

        # Determine query type from user message
        if messages:
            last_msg = messages[-1]
            if get_msg_role(last_msg) in ["user", "human"]:
                user_msg = get_msg_content(last_msg).lower()
                research_query = get_msg_content(last_msg)

                # Classify query type
                query_type = self._classify_query(user_msg)

                updates["research_query"] = research_query
                updates["current_phase"] = query_type

        return updates

    def _classify_query(self, query: str) -> str:
        """Classify the type of research query.

        Args:
            query: User's query text (lowercase)

        Returns:
            Query type: 'search', 'annotations', 'gap_analysis', or 'similarity'
        """
        # Annotations queries
        if any(word in query for word in ["annotation", "highlight", "note", "comment"]):
            return "annotations"

        # Gap analysis queries
        if any(word in query for word in ["gap", "missing", "coverage", "weak", "need more"]):
            return "gap_analysis"

        # Similarity queries
        if any(
            word in query
            for word in ["similar", "duplicate", "repeat", "redundant", "plagiarism"]
        ):
            return "similarity"

        # Default to search
        return "search"

    def search_node(self, state: AgentState) -> Dict:
        """Semantic search through research materials.

        Args:
            state: Current agent state

        Returns:
            Updated state with search results
        """
        query = state.get("research_query", "")

        if not query:
            return {"search_results": [], "current_phase": "analyzing"}

        # Perform search
        results = self.rag.search(query=query, limit=20, score_threshold=0.6)

        return {"search_results": results, "current_phase": "analyzing"}

    def annotations_node(self, state: AgentState) -> Dict:
        """Retrieve Zotero annotations.

        Args:
            state: Current agent state

        Returns:
            Updated state with annotations
        """
        # Extract chapter number from query if present
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        annotations = self.rag.get_annotations(chapter=chapter)

        return {"annotations": annotations, "current_phase": "analyzing"}

    def gap_analysis_node(self, state: AgentState) -> Dict:
        """Analyze research gaps.

        Args:
            state: Current agent state

        Returns:
            Updated state with gap analysis
        """
        # Extract chapter numbers if specified
        query = state.get("research_query", "")
        chapters = self._extract_chapter_numbers(query)

        gap_analysis = self.rag.analyze_gaps(chapters=chapters)

        return {"gap_analysis": gap_analysis, "current_phase": "analyzing"}

    def similarity_node(self, state: AgentState) -> Dict:
        """Find similar or duplicate content.

        Args:
            state: Current agent state

        Returns:
            Updated state with similarity results
        """
        query = state.get("research_query", "")

        # Use higher threshold for similarity detection
        results = self.rag.find_similar(text=query, threshold=0.80, limit=10)

        return {"similarity_results": results, "current_phase": "analyzing"}

    def analyze_node(self, state: AgentState) -> Dict:
        """Analyze gathered data and generate insights.

        Args:
            state: Current agent state

        Returns:
            Updated state with analysis
        """
        query = state.get("research_query", "")
        phase = state.get("current_phase", "analyzing")

        # Build context from gathered data
        context_parts = []

        # Search results
        if state.get("search_results"):
            context = self._format_search_results(state["search_results"])
            context_parts.append(f"## Search Results\n{context}")

        # Annotations
        if state.get("annotations"):
            context = self._format_annotations(state["annotations"])
            context_parts.append(f"## Zotero Annotations\n{context}")

        # Gap analysis
        if state.get("gap_analysis"):
            context = self._format_gap_analysis(state["gap_analysis"])
            context_parts.append(f"## Research Coverage Analysis\n{context}")

        # Similarity results
        if state.get("similarity_results"):
            context = self._format_similarity_results(state["similarity_results"])
            context_parts.append(f"## Similar Content\n{context}")

        full_context = "\n\n".join(context_parts)

        # System prompt for analysis
        system_prompt = f"""You are an AI research assistant analyzing book research materials.

{BOOK_OUTLINE}

Your role is to:
1. Analyze the research data provided in the context of the book's structure
2. Answer the user's question with specific details
3. Cite sources when referencing specific information
4. Make connections between different sources and chapters
5. Suggest where findings might fit in the book's narrative
6. Highlight important insights or patterns
7. Note connections to key concepts mentioned in the outline

**Handling Sync Issues:**
If you notice gaps or inconsistencies (e.g., outline mentions chapters not in Zotero, or vice versa):
- Note the discrepancy clearly
- Work with available data - don't fail because of missing sources
- Suggest the author may need to sync their outline/Zotero/Scrivener structure
- Recommend using the check-sync skill to see detailed mismatches

Be thorough but concise. Focus on actionable insights that help advance the book's argument."""

        analysis_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {query}\n\n{full_context}"},
        ]

        try:
            response = self.llm.invoke(analysis_messages)

            return {
                "messages": [{"role": "assistant", "content": response.content}],
                "current_phase": "complete",
            }
        except APIConnectionError:
            error_msg = "🔌 **Connection Error During Analysis**\n\nUnable to connect to the AI model service."
            return {
                "messages": [{"role": "assistant", "content": error_msg}],
                "current_phase": "error",
                "needs_user_input": True,
            }

    def refinement_node(self, state: AgentState) -> Dict:
        """Handle refinement based on user feedback.

        Args:
            state: Current agent state

        Returns:
            Updated state with refined analysis
        """
        feedback = state.get("user_feedback")
        if not feedback:
            return {}

        iteration = state.get("iteration_count", 0) + 1

        # Get previous messages for context
        messages = state.get("messages", [])

        # Add user feedback
        messages_with_feedback = messages + [
            {"role": "user", "content": feedback}
        ]

        # System prompt for refinement
        system_prompt = """You are refining your previous research analysis based on user feedback.

Your task is to:
1. Address the user's specific feedback
2. Expand on areas they want more detail
3. Maintain context from previous responses
4. Provide additional insights or connections

Build upon your previous analysis while incorporating the new direction."""

        try:
            response = self.llm.invoke(
                [{"role": "system", "content": system_prompt}] + messages_with_feedback
            )

            return {
                "messages": [{"role": "assistant", "content": response.content}],
                "current_phase": "complete",
                "iteration_count": iteration,
                "user_feedback": None,
            }
        except Exception as e:
            return {
                "messages": [
                    {"role": "assistant", "content": f"Error during refinement: {e}"}
                ],
                "current_phase": "error",
                "iteration_count": iteration,
                "user_feedback": None,
            }

    def _extract_chapter_number(self, text: str) -> int:
        """Extract a single chapter number from text."""
        import re

        match = re.search(r"chapter\s+(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_chapter_numbers(self, text: str) -> List[int]:
        """Extract multiple chapter numbers from text."""
        import re

        matches = re.findall(r"chapter\s+(\d+)", text, re.IGNORECASE)
        if matches:
            return [int(m) for m in matches]
        return None

    def _format_search_results(self, results: List[Dict]) -> str:
        """Format search results for LLM context."""
        if not results:
            return "No results found."

        formatted = []
        for r in results[:10]:  # Limit to top 10
            meta = r.get("metadata", {})
            formatted.append(
                f"**Source:** {meta.get('title', 'Unknown')} "
                f"(Relevance: {r['score']:.0%})\n"
                f"{r['text'][:300]}...\n"
            )

        return "\n".join(formatted)

    def _format_annotations(self, annotations: Dict) -> str:
        """Format annotations for LLM context."""
        if annotations.get("error"):
            return f"Error retrieving annotations: {annotations['error']}"

        count = annotations.get("count", 0)
        if count == 0:
            return "No annotations found."

        items = annotations.get("items", [])[:20]  # Limit to 20
        formatted = [f"Found {count} annotations\n"]
        for item in items:
            formatted.append(f"- {item['content']}")

        return "\n".join(formatted)

    def _format_gap_analysis(self, gap_analysis: Dict) -> str:
        """Format gap analysis for LLM context."""
        total = gap_analysis.get("total_indexed", 0)
        chapters = gap_analysis.get("chapters", {})

        formatted = [f"Total indexed chunks: {total}\n"]

        if chapters:
            formatted.append("Chapter coverage:")
            for chapter_num, data in sorted(chapters.items()):
                status = data["status"]
                count = data["chunk_count"]
                emoji = "✓" if status == "adequate" else "⚠"
                formatted.append(f"  {emoji} Chapter {chapter_num}: {count} chunks ({status})")

        return "\n".join(formatted)

    def _format_similarity_results(self, results: List[Dict]) -> str:
        """Format similarity results for LLM context."""
        if not results:
            return "No similar content found."

        formatted = ["Found potentially similar content:\n"]
        for r in results[:5]:  # Limit to top 5
            meta = r.get("metadata", {})
            formatted.append(
                f"**Similarity:** {r['score']:.0%} | "
                f"**Source:** {meta.get('title', 'Unknown')}\n"
                f"{r['text'][:200]}...\n"
            )

        return "\n".join(formatted)
