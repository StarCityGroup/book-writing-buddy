"""LangGraph node implementations for the book research agent."""

import os
from typing import Dict, List

from langchain_openai import ChatOpenAI
from openai import APIConnectionError

from .rag import BookRAG
from .state import AgentState

# Book structure context
BOOK_OUTLINE = """# FIREWALL - Book Structure

**Title:** FIREWALL
**Theme:** Technology and AI as tools to buy crucial time to prepare for climate change

## How the Book is Organized
The book breaks down the story of climate adaptation into three parts across 27 chapters (2,000-2,500 words each).

### Part I: Adaptation Shock (Chapters 1-4)
Lays out the challenge of climate adaptation and makes the case for why AI is essential.
- Chapter 1: The Mangrove and the Space Mirror - Contrasting extremes of adaptation
- Chapter 2: Adaptation Shock - Overview of growing challenges and sudden onset
- Chapter 3: Gaps and Traps - The work ahead, costs, and potential pitfalls
- Chapter 4: Adaptive Intelligence - How AI boom makes adaptation easier

### Part II: Behind the Firewall (Chapters 5-23)
Tour of localized hazards and technology-powered solutions around the world.

**Early Warning & Risk Assessment (5-7)**
- Chapter 5: Early Warning - Wildfire alerts and digital twins
- Chapter 6: Predicting Floods - AI-powered flood mapping and prediction
- Chapter 7: Fortified Homes - Climate risk in real estate and smart homes

**Infrastructure & Basic Systems (8-12)**
- Chapter 8: Weatherproof Buildings - Drone inspections in Singapore
- Chapter 9: Underground Cables - Protecting power and telecom networks
- Chapter 10: Decentralized Electricity - Grid independence with AI coordination
- Chapter 11: Active and Automated Mobility - Climate-proof transit and pedtech
- Chapter 12: Resilient Supply Chains - Last-mile delivery via waterways

**Urban Heat Solutions (13-15)**
- Chapter 13: Hyperlocal Heatmaps - Measuring urban heat islands with precision
- Chapter 14: Thermal Grids - Heat pumps and thermal infrastructure
- Chapter 15: Passive and Connected Cooling - Indoor climate risks and wearables

**Nature-Based Solutions (16-21)**
- Chapter 16: Quantified Canopies - Digital twins of urban forests
- Chapter 17: Smart Sponge Cities - Blue roofs and bioswales
- Chapter 18: Data Against Drought - Desalination and water conservation
- Chapter 19: Upgrading the Coast - Managed retreat and seasteading
- Chapter 20: Multi-Species Cities - Computational biology and rewilding
- Chapter 21: Capturing Nature's Worth - Earth observation and natural assets

**Extreme Interventions (22-23)**
- Chapter 22: Managing the Sun - Solar radiation management
- Chapter 23: Urban Domes and Underground Cities - Desperate adaptations

### Part III: Transformation (Chapters 24-27)
Assessing choices about technology and how decisions will change us.
- Chapter 24: Intelligence for Adaptation - Future of AI shaped by adaptation needs
- Chapter 25: Financing the Firewall - Private investment in adaptation & resilience
- Chapter 26: Climate-Proof Cities - Using AI to rebuild hastily-constructed cities
- Chapter 27: How to Start - Practical steps for readers to prepare

**Key Concepts:**
- Climate resilience vs. transformation
- Adaptation gap (costs vs. spending)
- Adaptation traps (what could go wrong)
- Co-benefits of nature-based solutions
- Embodied AI for physical world interaction
"""


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
- Zotero collections organized by chapter (1-27)
- Scrivener manuscript drafts
- All content indexed in vector database for semantic search

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
        system_prompt = f"""You are an AI research assistant analyzing book research materials for FIREWALL.

{BOOK_OUTLINE}

Your role is to:
1. Analyze the research data provided in the context of the book's structure
2. Answer the user's question with specific details
3. Cite sources when referencing specific information
4. Make connections between different sources and chapters
5. Suggest where findings might fit in the book's narrative
6. Highlight important insights or patterns
7. Note connections to key concepts (adaptation gap, traps, resilience vs transformation, etc.)

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
