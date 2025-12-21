"""LangGraph node implementations for the book research agent."""

import os
from pathlib import Path
from typing import Dict, List

import structlog
from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from .rag import BookRAG
from .state import AgentState

logger = structlog.get_logger()


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
            isinstance(get_msg_content(m), str)
            and "PLANNING phase" in get_msg_content(m)
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
                research_query = get_msg_content(last_msg)

                # Classify query type using LLM
                try:
                    query_type = self._classify_query_with_llm(research_query)
                except Exception as e:
                    logger.warning(
                        f"LLM classification failed: {e}, falling back to heuristics"
                    )
                    query_type = self._classify_query_heuristic(research_query.lower())

                updates["research_query"] = research_query
                updates["current_phase"] = query_type

        return updates

    def _classify_query_with_llm(self, query: str) -> str:
        """Classify query type using LLM for robust natural language understanding.

        Args:
            query: User's query text

        Returns:
            Query type: 'search', 'annotations', 'gap_analysis', etc.
        """
        classification_prompt = f"""You are a query classifier for a book research assistant.
Classify the following user query into ONE of these categories:

**Categories:**
- check_sync: Queries about whether outline, Zotero, and Scrivener are aligned
- list_chapters: Asking to list all chapters or show chapter structure
- chapter_info: Requesting detailed info about a specific chapter
- cross_chapter_theme: Tracking a theme or concept across multiple chapters
- compare_chapters: Comparing research density or content between chapters
- source_diversity: Analyzing variety of source types in a chapter
- key_sources: Identifying most-cited sources in a chapter
- export_summary: Exporting or generating a research summary/brief
- bibliography: Generating citations or bibliography
- timeline: Asking about when research was added or indexed
- related_research: Suggesting relevant research from other chapters
- annotations: Getting Zotero highlights, notes, or annotations
- gap_analysis: Identifying weak areas or missing research
- similarity: Finding similar or duplicate content
- search: General semantic search through research (DEFAULT)

**User Query:** "{query}"

Respond with ONLY the category name, nothing else."""

        try:
            response = self.llm.invoke(
                [{"role": "user", "content": classification_prompt}]
            )
            classification = response.content.strip().lower()

            # Validate classification
            valid_types = {
                "check_sync",
                "list_chapters",
                "chapter_info",
                "cross_chapter_theme",
                "compare_chapters",
                "source_diversity",
                "key_sources",
                "export_summary",
                "bibliography",
                "timeline",
                "related_research",
                "annotations",
                "gap_analysis",
                "similarity",
                "search",
            }

            if classification in valid_types:
                return classification
            else:
                logger.warning(
                    f"LLM returned invalid classification: {classification}, defaulting to search"
                )
                return "search"

        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            raise

    def _classify_query_heuristic(self, query: str) -> str:
        """Classify query type using heuristic string matching (fallback).

        Args:
            query: User's query text (lowercase)

        Returns:
            Query type: 'search', 'annotations', 'gap_analysis', 'similarity', etc.
        """
        # Sync check queries
        if any(word in query for word in ["sync", "aligned", "in sync", "out of sync"]):
            return "check_sync"

        # List chapters queries
        if any(
            phrase in query
            for phrase in [
                "list chapters",
                "what chapters",
                "show chapters",
                "all chapters",
            ]
        ):
            return "list_chapters"

        # Chapter info queries
        if any(
            phrase in query
            for phrase in [
                "chapter info",
                "info about chapter",
                "information about chapter",
                "chapter details",
            ]
        ):
            return "chapter_info"

        # Cross-chapter theme queries
        if any(
            phrase in query
            for phrase in [
                "cross chapter",
                "across chapters",
                "theme across",
                "track theme",
                "where does",
                "appears in",
            ]
        ):
            return "cross_chapter_theme"

        # Compare chapters queries
        if any(
            phrase in query
            for phrase in ["compare chapter", "comparison", "versus", "vs chapter"]
        ):
            return "compare_chapters"

        # Source diversity queries
        if any(
            phrase in query
            for phrase in [
                "source diversity",
                "diversity of sources",
                "source types",
                "balance of sources",
                "too many",
                "relying on",
            ]
        ):
            return "source_diversity"

        # Key sources queries
        if any(
            phrase in query
            for phrase in [
                "key sources",
                "most cited",
                "main sources",
                "heavily cited",
                "most referenced",
            ]
        ):
            return "key_sources"

        # Export/summary queries
        if any(
            phrase in query
            for phrase in [
                "export summary",
                "chapter summary",
                "summarize chapter",
                "research brief",
            ]
        ):
            return "export_summary"

        # Bibliography queries
        if any(
            phrase in query
            for phrase in [
                "bibliography",
                "citations",
                "references",
                "cite",
                "citation format",
            ]
        ):
            return "bibliography"

        # Timeline queries
        if any(
            phrase in query
            for phrase in [
                "recent",
                "recently added",
                "timeline",
                "when did i",
                "last week",
            ]
        ):
            return "timeline"

        # Related research queries
        if any(
            phrase in query
            for phrase in [
                "related research",
                "suggest research",
                "other chapters",
                "cross reference",
                "relevant from",
            ]
        ):
            return "related_research"

        # Annotations queries
        if any(
            word in query for word in ["annotation", "highlight", "note", "comment"]
        ):
            return "annotations"

        # Gap analysis queries
        if any(
            word in query
            for word in ["gap", "missing", "coverage", "weak", "need more"]
        ):
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

        # Chapter info
        if state.get("chapter_info"):
            context = self._format_chapter_info(state["chapter_info"])
            context_parts.append(f"## Chapter Information\n{context}")

        # Sync status
        if state.get("sync_status"):
            context = self._format_sync_status(state["sync_status"])
            context_parts.append(f"## Sync Status\n{context}")

        # Chapters list
        if state.get("chapters_list"):
            context = self._format_chapters_list(state["chapters_list"])
            context_parts.append(f"## Chapters\n{context}")

        # Cross-chapter theme
        if state.get("cross_chapter_theme"):
            context = self._format_cross_chapter_theme(state["cross_chapter_theme"])
            context_parts.append(f"## Cross-Chapter Theme Analysis\n{context}")

        # Chapter comparison
        if state.get("chapter_comparison"):
            context = self._format_chapter_comparison(state["chapter_comparison"])
            context_parts.append(f"## Chapter Comparison\n{context}")

        # Source diversity
        if state.get("source_diversity"):
            context = self._format_source_diversity(state["source_diversity"])
            context_parts.append(f"## Source Diversity Analysis\n{context}")

        # Key sources
        if state.get("key_sources"):
            context = self._format_key_sources(state["key_sources"])
            context_parts.append(f"## Key Sources\n{context}")

        # Export summary
        if state.get("export_summary"):
            context = self._format_export_summary(state["export_summary"])
            context_parts.append(f"## Chapter Research Summary\n{context}")

        # Bibliography
        if state.get("bibliography"):
            context = self._format_bibliography(state["bibliography"])
            context_parts.append(f"## Bibliography\n{context}")

        # Timeline
        if state.get("timeline"):
            context = self._format_timeline(state["timeline"])
            context_parts.append(f"## Research Timeline\n{context}")

        # Related research
        if state.get("related_research"):
            context = self._format_related_research(state["related_research"])
            context_parts.append(f"## Related Research Suggestions\n{context}")

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
        messages_with_feedback = messages + [{"role": "user", "content": feedback}]

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

    def chapter_info_node(self, state: AgentState) -> Dict:
        """Get comprehensive chapter information.

        Args:
            state: Current agent state

        Returns:
            Updated state with chapter info
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        if not chapter:
            return {
                "chapter_info": {"error": "No chapter number specified"},
                "current_phase": "analyzing",
            }

        chapter_info = self.rag.get_chapter_info(chapter)

        return {"chapter_info": chapter_info, "current_phase": "analyzing"}

    def check_sync_node(self, state: AgentState) -> Dict:
        """Check sync status between sources.

        Args:
            state: Current agent state

        Returns:
            Updated state with sync status
        """
        sync_status = self.rag.check_sync()

        return {"sync_status": sync_status, "current_phase": "analyzing"}

    def list_chapters_node(self, state: AgentState) -> Dict:
        """List all chapters from Scrivener.

        Args:
            state: Current agent state

        Returns:
            Updated state with chapter list
        """
        chapters_info = self.rag.list_chapters()

        return {"chapters_list": chapters_info, "current_phase": "analyzing"}

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

        source_count = annotations.get("source_count", 0)
        total_annotations = annotations.get("total_annotations", 0)

        if total_annotations == 0:
            return "No annotations found."

        formatted = [
            f"Found {total_annotations} annotations from {source_count} sources\n"
        ]

        sources = annotations.get("sources", [])[:10]  # Limit to 10 sources
        for source in sources:
            formatted.append(
                f"\n**{source['title']}** ({source['collection']})"
                f" - {source['annotation_count']} annotations:"
            )
            for annot in source["annotations"][:5]:  # Show first 5 per source
                annot_type = annot["type"]
                text = annot["text"][:200] if annot["text"] else ""
                comment = annot["comment"][:200] if annot["comment"] else ""

                if text:
                    formatted.append(f"  - [{annot_type}] {text}")
                if comment:
                    formatted.append(f"    Note: {comment}")

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
                formatted.append(
                    f"  {emoji} Chapter {chapter_num}: {count} chunks ({status})"
                )

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

    def _format_chapter_info(self, info: Dict) -> str:
        """Format chapter info for LLM context."""
        if info.get("error"):
            return f"Error: {info['error']}"

        chapter_num = info.get("chapter_number")
        formatted = [f"Chapter {chapter_num} Information:"]

        # Zotero info
        zotero = info.get("zotero", {})
        if zotero:
            formatted.append(
                f"\nZotero: {zotero.get('source_count', 0)} sources, "
                f"{zotero.get('chunk_count', 0)} chunks indexed"
            )

        # Scrivener info
        scrivener = info.get("scrivener", {})
        if scrivener:
            formatted.append(
                f"Scrivener: ~{scrivener.get('estimated_words', 0)} words, "
                f"{scrivener.get('chunk_count', 0)} chunks indexed"
            )

        formatted.append(f"\nTotal indexed chunks: {info.get('indexed_chunks', 0)}")

        return "\n".join(formatted)

    def _format_sync_status(self, status: Dict) -> str:
        """Format sync status for LLM context."""
        in_sync = status.get("in_sync", False)
        formatted = [
            "✓ All sources in sync" if in_sync else "⚠ Sources are out of sync"
        ]

        formatted.append(
            f"\nScrivener: {len(status.get('scrivener_chapters', {}))} chapters"
        )
        formatted.append(f"Zotero: {len(status.get('zotero_chapters', {}))} chapters")
        formatted.append(f"Outline: {len(status.get('outline_chapters', {}))} chapters")

        mismatches = status.get("mismatches", [])
        if mismatches:
            formatted.append(f"\n{len(mismatches)} mismatches found:")
            for m in mismatches[:5]:  # Show first 5
                formatted.append(f"- {m['message']}")

        recommendations = status.get("recommendations", [])
        if recommendations:
            formatted.append("\nRecommendations:")
            for rec in recommendations[:3]:
                formatted.append(f"- {rec}")

        return "\n".join(formatted)

    def _format_chapters_list(self, info: Dict) -> str:
        """Format chapters list for LLM context."""
        if info.get("error"):
            return f"Error: {info['error']}"

        formatted = [
            f"Project: {info.get('project_name', 'Unknown')}",
            f"Total chapters: {info.get('chapter_count', 0)}\n",
        ]

        chapters = info.get("chapters", [])
        for ch in chapters[:10]:  # Show first 10
            formatted.append(f"Chapter {ch['number']}: {ch['title']}")

        if len(chapters) > 10:
            formatted.append(f"... and {len(chapters) - 10} more chapters")

        return "\n".join(formatted)

    # ========================================================================
    # New Tool Nodes
    # ========================================================================

    def cross_chapter_theme_node(self, state: AgentState) -> Dict:
        """Track a theme across multiple chapters.

        Args:
            state: Current agent state

        Returns:
            Updated state with cross-chapter theme results
        """
        query = state.get("research_query", "")
        # Extract the theme/keyword from the query
        keyword = self._extract_theme_keyword(query)

        if not keyword:
            return {
                "cross_chapter_theme": {"error": "No theme keyword specified"},
                "current_phase": "analyzing",
            }

        results = self.rag.find_cross_chapter_themes(keyword=keyword)

        return {"cross_chapter_theme": results, "current_phase": "analyzing"}

    def compare_chapters_node(self, state: AgentState) -> Dict:
        """Compare two chapters.

        Args:
            state: Current agent state

        Returns:
            Updated state with comparison results
        """
        query = state.get("research_query", "")
        chapters = self._extract_chapter_numbers(query)

        if not chapters or len(chapters) < 2:
            return {
                "chapter_comparison": {"error": "Need two chapter numbers to compare"},
                "current_phase": "analyzing",
            }

        comparison = self.rag.compare_chapters(chapters[0], chapters[1])

        return {"chapter_comparison": comparison, "current_phase": "analyzing"}

    def source_diversity_node(self, state: AgentState) -> Dict:
        """Analyze source diversity for a chapter.

        Args:
            state: Current agent state

        Returns:
            Updated state with diversity analysis
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        if not chapter:
            return {
                "source_diversity": {"error": "No chapter number specified"},
                "current_phase": "analyzing",
            }

        diversity = self.rag.analyze_source_diversity(chapter)

        return {"source_diversity": diversity, "current_phase": "analyzing"}

    def key_sources_node(self, state: AgentState) -> Dict:
        """Identify key sources for a chapter.

        Args:
            state: Current agent state

        Returns:
            Updated state with key sources
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        if not chapter:
            return {
                "key_sources": {"error": "No chapter number specified"},
                "current_phase": "analyzing",
            }

        key_sources = self.rag.identify_key_sources(chapter)

        return {"key_sources": key_sources, "current_phase": "analyzing"}

    def export_summary_node(self, state: AgentState) -> Dict:
        """Export chapter research summary.

        Args:
            state: Current agent state

        Returns:
            Updated state with exported summary
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        if not chapter:
            return {
                "export_summary": {"error": "No chapter number specified"},
                "current_phase": "analyzing",
            }

        # Default to markdown format
        summary = self.rag.export_chapter_summary(chapter, format="markdown")

        return {
            "export_summary": {"chapter": chapter, "summary": summary},
            "current_phase": "analyzing",
        }

    def bibliography_node(self, state: AgentState) -> Dict:
        """Generate bibliography.

        Args:
            state: Current agent state

        Returns:
            Updated state with bibliography
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        # Detect citation style from query
        style = "apa"  # default
        if "mla" in query.lower():
            style = "mla"
        elif "chicago" in query.lower():
            style = "chicago"

        bibliography = self.rag.generate_bibliography(chapter=chapter, style=style)

        return {"bibliography": bibliography, "current_phase": "analyzing"}

    def timeline_node(self, state: AgentState) -> Dict:
        """Get research timeline.

        Args:
            state: Current agent state

        Returns:
            Updated state with timeline
        """
        query = state.get("research_query", "")

        # Check if asking for recent additions
        if "recent" in query.lower() or "last week" in query.lower():
            days = 7
            if "last month" in query.lower():
                days = 30
            timeline = self.rag.get_recent_additions(days=days)
        else:
            # Full timeline
            chapter = self._extract_chapter_number(query)
            timeline = self.rag.get_research_timeline(chapter=chapter)

        return {"timeline": timeline, "current_phase": "analyzing"}

    def related_research_node(self, state: AgentState) -> Dict:
        """Suggest related research from other chapters.

        Args:
            state: Current agent state

        Returns:
            Updated state with suggestions
        """
        query = state.get("research_query", "")
        chapter = self._extract_chapter_number(query)

        if not chapter:
            return {
                "related_research": {"error": "No chapter number specified"},
                "current_phase": "analyzing",
            }

        suggestions = self.rag.suggest_related_research(chapter)

        return {"related_research": suggestions, "current_phase": "analyzing"}

    def _extract_theme_keyword(self, text: str) -> str:
        """Extract theme keyword from query text."""
        # Look for quoted strings first
        import re

        quoted = re.search(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted.group(1)

        # Look for "theme of X" or "track X" patterns
        patterns = [
            r"theme (?:of |about )?(.+?)(?:\s+across|\s+in|\?|$)",
            r"track (?:the )?(.+?)(?:\s+across|\s+in|\?|$)",
            r"(?:where does|find) (.+?)(?:\s+appear|\s+show|\s+in|\?|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                keyword = match.group(1).strip()
                # Remove common words
                keyword = re.sub(
                    r"\b(the|a|an|this|that)\b", "", keyword, flags=re.IGNORECASE
                )
                return keyword.strip()

        # Default: use the whole query
        return text

    # ========================================================================
    # Formatting Methods for New Data Types
    # ========================================================================

    def _format_cross_chapter_theme(self, results: Dict) -> str:
        """Format cross-chapter theme results for LLM context."""
        if results.get("error"):
            return f"Error: {results['error']}"

        keyword = results.get("keyword", "Unknown")
        total_chapters = results.get("total_chapters", 0)
        total_mentions = results.get("total_mentions", 0)

        formatted = [
            f"Tracking theme: **{keyword}**",
            f"Found in {total_chapters} chapters with {total_mentions} mentions\n",
        ]

        chapters = results.get("chapters", [])
        for ch in chapters[:10]:  # Show first 10
            ch_num = ch["chapter_number"]
            ch_title = ch["chapter_title"]
            mentions = ch["mentions"]
            formatted.append(
                f"\n**Chapter {ch_num}: {ch_title}** ({len(mentions)} mentions)"
            )
            for mention in mentions[:3]:  # Show first 3 mentions per chapter
                formatted.append(
                    f"  - ({mention['score']:.0%}) {mention['text'][:150]}..."
                )

        return "\n".join(formatted)

    def _format_chapter_comparison(self, comparison: Dict) -> str:
        """Format chapter comparison for LLM context."""
        if comparison.get("error"):
            return f"Error: {comparison['error']}"

        ch1 = comparison["chapter1"]
        ch2 = comparison["chapter2"]
        comp = comparison["comparison"]

        formatted = [
            f"**Chapter {ch1['number']}:**",
            f"  - Sources: {ch1['zotero_sources']}",
            f"  - Research chunks: {ch1['zotero_chunks']}",
            f"  - Draft words: ~{ch1['scrivener_words']}",
            f"  - Research density: {ch1['research_density']:.3f}",
            "",
            f"**Chapter {ch2['number']}:**",
            f"  - Sources: {ch2['zotero_sources']}",
            f"  - Research chunks: {ch2['zotero_chunks']}",
            f"  - Draft words: ~{ch2['scrivener_words']}",
            f"  - Research density: {ch2['research_density']:.3f}",
            "",
            "**Comparison:**",
            f"  - More sources: Chapter {comp['more_sources']}",
            f"  - More research-dense: Chapter {comp['more_research_dense']}",
            f"  - Density ratio: {comp['density_ratio']:.2f}x",
        ]

        return "\n".join(formatted)

    def _format_source_diversity(self, diversity: Dict) -> str:
        """Format source diversity for LLM context."""
        if diversity.get("error"):
            return f"Error: {diversity['error']}"

        chapter = diversity["chapter"]
        total = diversity["total_sources"]
        score = diversity["diversity_score"]

        formatted = [
            f"Chapter {chapter} has {total} unique sources",
            f"Diversity score: {score} (0=homogeneous, 1=diverse)\n",
        ]

        source_types = diversity.get("source_types", {})
        if source_types:
            formatted.append("**Source types:**")
            for item_type, count in sorted(
                source_types.items(), key=lambda x: x[1], reverse=True
            ):
                formatted.append(f"  - {item_type}: {count}")

        most_cited = diversity.get("most_cited", [])
        if most_cited:
            formatted.append("\n**Most cited sources:**")
            for src in most_cited[:5]:
                formatted.append(f"  - {src['title']}: {src['chunks']} chunks")

        return "\n".join(formatted)

    def _format_key_sources(self, key_sources: Dict) -> str:
        """Format key sources for LLM context."""
        if key_sources.get("error"):
            return f"Error: {key_sources['error']}"

        chapter = key_sources["chapter"]
        count = key_sources["key_sources_count"]
        threshold = key_sources["threshold"]

        formatted = [
            f"Chapter {chapter}: {count} key sources (threshold: {threshold}+ mentions)\n"
        ]

        sources = key_sources.get("key_sources", [])
        for src in sources[:15]:  # Show top 15
            formatted.append(
                f"- **{src['title']}** ({src['item_type']}): {src['chunk_count']} chunks"
            )

        return "\n".join(formatted)

    def _format_export_summary(self, export: Dict) -> str:
        """Format exported summary for LLM context."""
        if export.get("error"):
            return f"Error: {export['error']}"

        chapter = export["chapter"]
        summary = export["summary"]

        # Just return the summary as-is (it's already formatted)
        return f"Summary for Chapter {chapter}:\n\n{summary}"

    def _format_bibliography(self, bibliography: List[Dict]) -> str:
        """Format bibliography for LLM context."""
        if not bibliography:
            return "No sources found"

        formatted = [f"Found {len(bibliography)} sources:\n"]

        for i, entry in enumerate(bibliography[:20], 1):  # Show first 20
            citation = entry["citation"]
            chapters = entry.get("chapters", [])
            ch_str = f" (Chapters: {', '.join(map(str, chapters))})" if chapters else ""
            formatted.append(f"{i}. {citation}{ch_str}")

        if len(bibliography) > 20:
            formatted.append(f"\n... and {len(bibliography) - 20} more sources")

        return "\n".join(formatted)

    def _format_timeline(self, timeline: Dict) -> str:
        """Format research timeline for LLM context."""
        # Check if it's recent additions or full timeline
        if "sources" in timeline:
            # Recent additions format
            cutoff = timeline.get("cutoff_date", "Unknown")
            sources = timeline.get("sources", {})

            if not sources:
                return f"No research added since {cutoff}"

            formatted = [f"Research added since {cutoff}:\n"]
            for source_type, info in sources.items():
                formatted.append(
                    f"- {source_type}: indexed {info['indexed_at']} "
                    f"({info['age_hours']} hours ago)"
                )

            return "\n".join(formatted)
        else:
            # Full timeline format
            chapter = timeline.get("chapter")
            periods = timeline.get("total_periods", 0)
            timeline_list = timeline.get("timeline", [])

            if not timeline_list:
                return "No timeline data available"

            header = (
                f"Research timeline for Chapter {chapter}"
                if chapter
                else "Research timeline"
            )
            formatted = [f"{header} ({periods} time periods):\n"]

            for period in timeline_list[:12]:  # Show last 12 months
                month = period["month"]
                count = period["count"]
                chapters = period.get("chapters", [])
                ch_str = (
                    f" (Chapters: {', '.join(map(str, chapters))})" if chapters else ""
                )
                formatted.append(f"- {month}: {count} chunks indexed{ch_str}")

            return "\n".join(formatted)

    def _format_related_research(self, suggestions: Dict) -> str:
        """Format related research suggestions for LLM context."""
        if suggestions.get("error"):
            return f"Error: {suggestions['error']}"

        chapter = suggestions["chapter"]
        count = suggestions["suggestions_count"]
        chapters_count = suggestions["chapters_with_suggestions"]

        if count == 0:
            return f"No related research found for Chapter {chapter}"

        formatted = [
            f"Found {count} related items from {chapters_count} other chapters:\n"
        ]

        for ch_group in suggestions.get("suggestions", [])[:5]:  # Show top 5 chapters
            ch_num = ch_group["chapter"]
            ch_title = ch_group["chapter_title"]
            items = ch_group["items"]
            formatted.append(f"\n**Chapter {ch_num}: {ch_title}** ({len(items)} items)")

            for item in items[:3]:  # Show top 3 items per chapter
                formatted.append(
                    f"  - ({item['relevance']:.0%}) {item['source']}: "
                    f"{item['text_preview'][:100]}..."
                )

        return "\n".join(formatted)
