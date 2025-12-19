"""CLI chat interface for book research agent."""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status

from .agent import create_agent
from .rag import BookRAG
from .state import create_initial_state


class BookResearchChatCLI:
    """Interactive CLI for book research agent."""

    def __init__(self):
        """Initialize CLI."""
        load_dotenv()

        self.console = Console()
        self.agent = create_agent()
        self.state = create_initial_state()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_dir = Path("conversations")
        self.conversation_dir.mkdir(exist_ok=True)
        self.rag = None  # Initialized in run()

    def test_connection(self):
        """Test LLM connection at startup.

        Returns:
            True if connection successful, False otherwise
        """
        from langchain_openai import ChatOpenAI

        self.console.print("\n[dim]Testing connection to LLM...[/dim]")

        try:
            # Get configuration
            api_base = os.getenv("OPENAI_API_BASE") or os.getenv(
                "LITELLM_PROXY_URL", "http://localhost:4000"
            )
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv(
                "LITELLM_API_KEY", "sk-1234"
            )
            model_name = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-haiku")

            # Create test LLM instance
            llm = ChatOpenAI(
                model=model_name,
                base_url=api_base,
                api_key=api_key,
                temperature=0.7,
            )

            # Simple test prompt
            llm.invoke([{"role": "user", "content": "Say 'OK' if you can read this."}])

            self.console.print(
                f"[green]✓[/green] [dim]Connected to {model_name} at {api_base}[/dim]"
            )
            return True

        except APIConnectionError as e:
            self.console.print(f"\n[red]✗ Connection failed to {api_base}[/red]")
            self.console.print(f"[yellow]Error: {str(e)}[/yellow]\n")
            self.console.print("Please check your .env configuration:")
            self.console.print("  - OPENAI_API_BASE or LITELLM_PROXY_URL")
            self.console.print("  - OPENAI_API_KEY or LITELLM_API_KEY\n")
            return False

        except Exception as e:
            self.console.print(f"\n[red]✗ Unexpected error: {str(e)}[/red]\n")
            return False

    def check_qdrant(self):
        """Check Qdrant connection and index status.

        Returns:
            True if successful, False otherwise
        """
        self.console.print("[dim]Checking Qdrant vector database...[/dim]")

        try:
            self.rag = BookRAG()
            stats = self.rag.get_index_stats()

            if stats["points_count"] > 0:
                self.console.print(
                    f"[green]✓[/green] [dim]Index ready: {stats['points_count']:,} chunks[/dim]"
                )

                # Show last index times
                last_indexed = stats["last_indexed"]
                if last_indexed["zotero"] or last_indexed["scrivener"]:
                    self.console.print(
                        f"[dim]  Last indexed: "
                        f"Zotero {last_indexed.get('zotero', 'never')}, "
                        f"Scrivener {last_indexed.get('scrivener', 'never')}[/dim]"
                    )

                return True
            else:
                self.console.print(
                    "[yellow]⚠ Index is empty - run indexer first[/yellow]"
                )
                return False

        except Exception as e:
            self.console.print(f"[red]✗ Qdrant connection failed: {str(e)}[/red]")
            self.console.print(
                "[yellow]Make sure Qdrant is running: docker compose up -d qdrant[/yellow]\n"
            )
            return False

    def print_welcome(self):
        """Print welcome message."""
        welcome = """
# Book Research Buddy

Welcome! I'm your AI research assistant for analyzing your Zotero research library and Scrivener manuscript.

I can help you:
- **Search semantically** across all your research materials
- **Get annotations** from your Zotero library for specific chapters
- **Analyze research gaps** to identify where you need more sources
- **Find similar content** to check for redundancy or verify originality

Available commands:
- `/help` - Show this help message
- `/knowledge` - View indexed data and last update times
- `/model` - Switch between model tiers (good/better/best)
- `/history` - View past conversations
- `/reindex` - Manually trigger re-indexing
- `/new` - Start fresh conversation
- `/exit` - Exit the application

**Just ask a question to get started!**
        """
        self.console.print(Panel(Markdown(welcome), border_style="blue"))

    def print_message(self, role: str, content: str):
        """Print a formatted message.

        Args:
            role: Message role (user/assistant/system)
            content: Message content
        """
        if role == "user":
            self.console.print(f"\n[bold cyan]You:[/bold cyan] {content}")
        elif role == "assistant":
            self.console.print("\n[bold green]Agent:[/bold green]")
            self.console.print(Markdown(content))
        elif role == "system":
            self.console.print(f"\n[dim]{content}[/dim]")

    def handle_command(self, command: str) -> bool:
        """Handle CLI commands.

        Args:
            command: Command string

        Returns:
            True if should exit, False otherwise
        """
        command_lower = command.lower().strip()

        if command_lower == "/exit":
            self.save_conversation()
            self.console.print(
                "\n[yellow]Goodbye! Your conversation has been saved.[/yellow]\n"
            )
            return True

        elif command_lower == "/help":
            self.print_welcome()

        elif command_lower == "/new":
            self.save_conversation()
            self.state = create_initial_state()
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.console.print("\n[green]Started new research session.[/green]\n")

        elif command_lower == "/history":
            self.show_history()

        elif command_lower.startswith("/model"):
            parts = command.strip().split()
            model_map = {
                "good": os.getenv("MODEL_GOOD", "anthropic.claude-4.5-haiku"),
                "better": os.getenv("MODEL_BETTER", "anthropic.claude-4.5-sonnet"),
                "best": os.getenv("MODEL_BEST", "anthropic.claude-opus-4.5"),
            }
            if len(parts) == 1:
                # Show current model
                current = os.getenv("DEFAULT_MODEL", model_map["good"])
                current_tier = "custom"
                for tier, model in model_map.items():
                    if model == current:
                        current_tier = tier
                        break
                self.console.print(f"\n[cyan]Current model: {current}[/cyan]")
                if current_tier != "custom":
                    self.console.print(f"[cyan]Tier: {current_tier}[/cyan]")
                self.console.print("\nAvailable tiers:")
                self.console.print(f"  - good   ({model_map['good']}) - Fast & economical")
                self.console.print(f"  - better ({model_map['better']}) - Balanced")
                self.console.print(f"  - best   ({model_map['best']}) - Highest quality")
                self.console.print("\nUsage: /model <good|better|best>\n")
            else:
                tier = parts[1].lower()
                if tier in model_map:
                    os.environ["DEFAULT_MODEL"] = model_map[tier]
                    # Recreate agent with new model
                    self.agent = create_agent()
                    self.console.print(
                        f"\n[green]✓ Switched to {tier} ({model_map[tier]})[/green]\n"
                    )
                else:
                    self.console.print(f"\n[red]Unknown tier: {tier}[/red]")
                    self.console.print("Available: good, better, best\n")

        elif command_lower == "/knowledge":
            self.show_knowledge()

        elif command_lower == "/reindex":
            self.trigger_reindex()

        else:
            self.console.print(f"\n[red]Unknown command: {command}[/red]")
            self.console.print("Type /help for available commands.\n")

        return False

    def show_knowledge(self):
        """Show summary of indexed data."""
        self.console.print("\n[bold cyan]Knowledge Base Summary[/bold cyan]\n")

        if self.rag:
            stats = self.rag.get_index_stats()
            self.console.print(
                f"[bold]Indexed Data:[/bold] {stats['points_count']:,} chunks"
            )
            self.console.print(f"[bold]Status:[/bold] {stats['status']}")

            last_indexed = stats["last_indexed"]
            self.console.print("\n[bold]Last Indexed:[/bold]")
            self.console.print(
                f"  - Zotero: {last_indexed.get('zotero', 'never')}"
            )
            self.console.print(
                f"  - Scrivener: {last_indexed.get('scrivener', 'never')}"
            )
        else:
            self.console.print("[yellow]RAG system not initialized[/yellow]")

        self.console.print()

    def trigger_reindex(self):
        """Trigger manual re-indexing."""
        self.console.print("\n[yellow]Manual re-indexing not yet implemented.[/yellow]")
        self.console.print(
            "Use the Docker watcher or run indexer scripts directly.\n"
        )

    def show_history(self):
        """Show past conversations."""
        if not self.conversation_dir.exists():
            self.console.print("\n[yellow]No conversations found yet.[/yellow]\n")
            return

        conversations = sorted(self.conversation_dir.glob("*.json"), reverse=True)
        if not conversations:
            self.console.print("\n[yellow]No conversations found yet.[/yellow]\n")
            return

        self.console.print("\n[bold]Past Conversations:[/bold]")
        for i, conv in enumerate(conversations[:10], 1):
            timestamp = conv.stem.replace("conversation_", "")
            self.console.print(f"  {i}. {conv.name} ({timestamp})")
        self.console.print()

    def save_conversation(self):
        """Save current conversation to file."""
        if not self.state.get("messages"):
            return

        filepath = self.conversation_dir / f"conversation_{self.session_id}.json"

        conversation_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": self.state["messages"],
            "research_query": self.state.get("research_query"),
        }

        with open(filepath, "w") as f:
            json.dump(conversation_data, f, indent=2, default=str)

    def run_agent(self, user_input: str):
        """Run the agent with user input.

        Args:
            user_input: User's message
        """
        # Track how many messages we had before
        messages_before = len(self.state.get("messages", []))

        # Add user message to state
        self.state["messages"].append({"role": "user", "content": user_input})

        try:
            # Run agent with thinking spinner
            with Status(
                "[bold cyan]Thinking...[/bold cyan]",
                spinner="dots",
                console=self.console,
            ):
                result = self.agent.invoke(self.state)

            # Update state
            self.state = result

            # Print only NEW agent responses
            all_messages = result.get("messages", [])
            new_messages = all_messages[messages_before + 1:]

            if not new_messages:
                self.console.print(
                    "\n[yellow]No response generated. Try rephrasing your question.[/yellow]"
                )

            for msg in new_messages:
                # Handle both dict and message objects
                msg_role = (
                    msg.get("role")
                    if isinstance(msg, dict)
                    else getattr(msg, "type", None)
                )
                msg_content = (
                    msg.get("content")
                    if isinstance(msg, dict)
                    else getattr(msg, "content", "")
                )

                if msg_role in ["assistant", "ai"]:
                    self.print_message("assistant", msg_content)

        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]\n")
            import traceback

            traceback.print_exc()

    def run(self):
        """Run the interactive CLI."""
        # Test connection first
        if not self.test_connection():
            self.console.print(
                "\n[yellow]Starting anyway - you can fix configuration later[/yellow]\n"
            )

        # Check Qdrant
        if not self.check_qdrant():
            self.console.print(
                "\n[yellow]Continuing without index - some features won't work[/yellow]\n"
            )

        self.print_welcome()

        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if self.handle_command(user_input):
                        break
                    continue

                # Run agent
                self.run_agent(user_input)

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Use /exit to quit properly.[/yellow]\n")
            except EOFError:
                break

        self.save_conversation()


def main():
    """Entry point for CLI."""
    cli = BookResearchChatCLI()
    cli.run()


if __name__ == "__main__":
    main()
