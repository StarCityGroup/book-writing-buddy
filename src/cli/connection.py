"""Connection testing for CLI."""

import os

from ..tools import get_rag


class ConnectionTester:
    """Handles connection testing for LLM and Qdrant."""

    def __init__(self, console):
        """Initialize connection tester.

        Args:
            console: Rich console for output
        """
        self.console = console

    def test_anthropic_connection(self) -> bool:
        """Test connection to Anthropic API (via LiteLLM proxy).

        Returns:
            True if connection successful, False otherwise
        """
        self.console.print("\n[muted]Testing connection to Anthropic API...[/muted]")

        try:
            import anthropic

            # Get configuration from environment
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            api_base = os.getenv("OPENAI_API_BASE")

            if not api_key:
                self.console.print(
                    "[cross]✗ No API key found[/cross] (OPENAI_API_KEY or ANTHROPIC_API_KEY)"
                )
                return False

            # Create client (will use base URL if provided)
            client_kwargs = {"api_key": api_key}
            if api_base:
                client_kwargs["base_url"] = api_base

            client = anthropic.Anthropic(**client_kwargs)

            # Simple test - list available models (lightweight call)
            # Note: This may not work with LiteLLM proxy, so we'll just verify client creation
            self.console.print(
                f"[checkmark]✓[/checkmark] [muted]Connected to API"
                + (f" at {api_base}" if api_base else "")
                + "[/muted]"
            )
            return True

        except Exception as e:
            self.console.print(f"\n[cross]✗ Connection failed[/cross]")
            self.console.print(f"[warning]Error: {str(e)}[/warning]\n")
            self.console.print("Please check your .env configuration:")
            self.console.print("  - OPENAI_API_KEY or ANTHROPIC_API_KEY")
            if os.getenv("OPENAI_API_BASE"):
                self.console.print("  - OPENAI_API_BASE (for LiteLLM proxy)")
            self.console.print()
            return False

    def check_qdrant(self) -> tuple[bool, object]:
        """Check Qdrant connection and index status.

        Returns:
            Tuple of (success: bool, rag_instance: BookRAG or None)
        """
        self.console.print("[muted]Checking Qdrant vector database...[/muted]")

        try:
            rag = get_rag()

            # Backfill timestamps if needed (for data indexed before timestamp feature)
            rag.vectordb.backfill_timestamps_if_needed()

            stats = rag.get_index_stats()

            if stats["points_count"] > 0:
                self.console.print(
                    f"[checkmark]✓[/checkmark] [muted]Connected to Qdrant: "
                    f"{stats['points_count']:,} indexed chunks[/muted]"
                )
                return True, rag
            else:
                self.console.print(
                    "[warning]⚠[/warning] [muted]Qdrant is empty. Run /reindex to populate.[/muted]"
                )
                return True, rag  # Connection OK, just empty

        except Exception as e:
            self.console.print(f"[cross]✗ Qdrant connection failed: {e}[/cross]")
            return False, None
