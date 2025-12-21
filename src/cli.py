"""CLI chat interface for book research agent."""

import json
import os
import sqlite3
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

            # Backfill timestamps if needed (for data indexed before timestamp feature)
            self.rag.vectordb.backfill_timestamps_if_needed()

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

## What I Can Do

**Basic Research:**
- **Search semantically** across all your research materials
- **Get annotations** from your Zotero library for specific chapters
- **Analyze research gaps** to identify where you need more sources
- **Find similar content** to check for redundancy or verify originality

**Advanced Analysis:**
- **Track themes** across multiple chapters (e.g., "Where does 'resilience' appear?")
- **Compare chapters** to see which need more research
- **Analyze source diversity** to ensure balanced coverage
- **Identify key sources** that you cite most frequently
- **Export summaries** and generate bibliographies (APA/MLA/Chicago)
- **View research timeline** to see when materials were added
- **Get smart suggestions** for relevant research from other chapters

**Project Management:**
- **List all chapters** from your Scrivener project
- **Check sync status** between outline, Zotero, and Scrivener
- **Get chapter info** with detailed statistics

## Commands

- `/help` - Show this help message
- `/diagnose` - Check paths, connections, and configuration
- `/knowledge` - View indexed data and last update times
- `/zotero-summary` - Show document counts by chapter and type
- `/model` - Switch between model tiers (good/better/best)
- `/history` - View past conversations
- `/reindex` - Manually trigger re-indexing (close Zotero first!)
- `/new` - Start fresh conversation
- `/exit` - Exit the application

**Just ask a question to get started!** Examples:
- "Track the theme 'infrastructure failure' across all chapters"
- "Compare research density between chapters 5 and 9"
- "What are the key sources for chapter 3?"
- "Get all my Zotero annotations for chapter 9"
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
                self.console.print(
                    f"  - good   ({model_map['good']}) - Fast & economical"
                )
                self.console.print(f"  - better ({model_map['better']}) - Balanced")
                self.console.print(
                    f"  - best   ({model_map['best']}) - Highest quality"
                )
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

        elif command_lower == "/diagnose":
            self.show_diagnostics()

        elif command_lower == "/zotero-summary":
            self.show_zotero_summary()

        else:
            self.console.print(f"\n[red]Unknown command: {command}[/red]")
            self.console.print("Type /help for available commands.\n")

        return False

    def show_diagnostics(self):
        """Show diagnostic information about paths and configuration."""
        self.console.print("\n[bold cyan]System Diagnostics[/bold cyan]\n")

        # Check environment variables
        self.console.print("[bold]Environment Variables:[/bold]")
        zotero_path = os.getenv("ZOTERO_PATH")
        scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

        self.console.print(f"  ZOTERO_PATH: {zotero_path or '[red]NOT SET[/red]'}")
        if zotero_path:
            exists = Path(zotero_path).exists()
            self.console.print(
                f"    Exists: {'[green]YES[/green]' if exists else '[red]NO[/red]'}"
            )
            if exists:
                db_path = Path(zotero_path) / "zotero.sqlite"
                db_exists = db_path.exists()
                self.console.print(
                    f"    Database: {'[green]FOUND[/green]' if db_exists else '[red]NOT FOUND[/red]'}"
                )

        self.console.print(
            f"\n  SCRIVENER_PROJECT_PATH: {scrivener_path or '[red]NOT SET[/red]'}"
        )
        if scrivener_path:
            exists = Path(scrivener_path).exists()
            self.console.print(
                f"    Exists: {'[green]YES[/green]' if exists else '[red]NO[/red]'}"
            )
            if exists:
                scriv_file = (
                    Path(scrivener_path) / f"{Path(scrivener_path).stem}.scrivx"
                )
                scriv_exists = scriv_file.exists()
                self.console.print(
                    f"    .scrivx file: {'[green]FOUND[/green]' if scriv_exists else '[red]NOT FOUND[/red]'}"
                )

        self.console.print(f"\n  QDRANT_URL: {qdrant_url}")

        # Test Qdrant connection
        self.console.print("\n[bold]Qdrant Connection:[/bold]")
        if self.rag:
            try:
                info = self.rag.vectordb.get_collection_info()
                self.console.print("  Status: [green]CONNECTED[/green]")
                self.console.print(f"  Points: {info['points_count']:,}")
            except Exception as e:
                self.console.print(f"  Status: [red]FAILED[/red] - {e}")
        else:
            self.console.print("  [yellow]RAG not initialized[/yellow]")

        # Check indexed data sample
        if self.rag:
            self.console.print("\n[bold]Indexed Data Sample:[/bold]")
            try:
                # Get a sample of data to see what's indexed
                sample = self.rag.vectordb.client.scroll(
                    collection_name=self.rag.vectordb.collection_name,
                    limit=10,
                    with_payload=True,
                )

                source_types = {}
                chapter_numbers = set()

                for point in sample[0]:
                    source_type = point.payload.get("source_type", "unknown")
                    source_types[source_type] = source_types.get(source_type, 0) + 1

                    chapter_num = point.payload.get("chapter_number")
                    if chapter_num:
                        chapter_numbers.add(chapter_num)

                self.console.print(f"  Source types: {dict(source_types)}")
                if chapter_numbers:
                    self.console.print(
                        f"  Chapter numbers found: {sorted(chapter_numbers)}"
                    )
                else:
                    self.console.print(
                        "  [yellow]No chapter numbers in sample[/yellow]"
                    )

            except Exception as e:
                self.console.print(f"  [red]Error sampling data: {e}[/red]")

        self.console.print()

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
            self.console.print(f"  - Zotero: {last_indexed.get('zotero', 'never')}")
            self.console.print(
                f"  - Scrivener: {last_indexed.get('scrivener', 'never')}"
            )
        else:
            self.console.print("[yellow]RAG system not initialized[/yellow]")

        self.console.print()

    def show_zotero_summary(self):
        """Show summary of Zotero documents by chapter and type."""
        from rich.table import Table

        self.console.print("\n[bold cyan]Zotero Library Summary[/bold cyan]\n")

        zotero_path = os.getenv("ZOTERO_PATH")
        if not zotero_path:
            self.console.print("[red]✗ ZOTERO_PATH not set in .env[/red]\n")
            return

        db_path = Path(zotero_path) / "zotero.sqlite"
        if not db_path.exists():
            self.console.print(f"[red]✗ Zotero database not found at: {db_path}[/red]\n")
            return

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Load config to get chapter pattern
            config_path = Path(__file__).parent.parent / "config" / "default.json"
            with open(config_path) as f:
                config = json.load(f)

            chapter_pattern = config.get("project", {}).get("zotero", {}).get("chapter_pattern", r"^(\d+)\.")
            import re

            # Get all collections with their item counts and attachment types
            cursor.execute("""
                SELECT
                    c.collectionID,
                    c.collectionName,
                    COUNT(DISTINCT i.itemID) as total_items,
                    COUNT(DISTINCT CASE WHEN ia.path LIKE '%.pdf' THEN ia.itemID END) as pdf_count,
                    COUNT(DISTINCT CASE WHEN ia.path LIKE '%.html' OR ia.path LIKE '%.htm' THEN ia.itemID END) as html_count,
                    COUNT(DISTINCT CASE WHEN ia.path LIKE '%.txt' THEN ia.itemID END) as txt_count,
                    COUNT(DISTINCT CASE WHEN ia.path IS NOT NULL
                        AND ia.path NOT LIKE '%.pdf'
                        AND ia.path NOT LIKE '%.html'
                        AND ia.path NOT LIKE '%.htm'
                        AND ia.path NOT LIKE '%.txt'
                        THEN ia.itemID END) as other_count
                FROM collections c
                LEFT JOIN collectionItems ci ON c.collectionID = ci.collectionID
                LEFT JOIN items i ON ci.itemID = i.itemID
                LEFT JOIN itemAttachments ia ON i.itemID = ia.parentItemID
                GROUP BY c.collectionID, c.collectionName
                ORDER BY c.collectionName
            """)

            results = cursor.fetchall()
            conn.close()

            # Create table
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Chapter", style="bold")
            table.add_column("Collection", style="dim")
            table.add_column("Items", justify="right")
            table.add_column("PDFs", justify="right", style="green")
            table.add_column("HTML", justify="right", style="blue")
            table.add_column("TXT", justify="right", style="yellow")
            table.add_column("Other", justify="right", style="dim")

            total_items = 0
            total_pdf = 0
            total_html = 0
            total_txt = 0
            total_other = 0
            chapter_count = 0

            for coll_id, coll_name, items, pdf, html, txt, other in results:
                # Extract chapter number if matches pattern
                match = re.match(chapter_pattern, coll_name)
                chapter_num = match.group(1) if match else "-"

                # Only show collections with items
                if items > 0:
                    table.add_row(
                        chapter_num,
                        coll_name[:50] + "..." if len(coll_name) > 50 else coll_name,
                        str(items),
                        str(pdf) if pdf > 0 else "-",
                        str(html) if html > 0 else "-",
                        str(txt) if txt > 0 else "-",
                        str(other) if other > 0 else "-"
                    )

                    total_items += items
                    total_pdf += pdf
                    total_html += html
                    total_txt += txt
                    total_other += other
                    if match:
                        chapter_count += 1

            # Add totals row
            table.add_section()
            table.add_row(
                "[bold]TOTAL",
                f"[bold]{chapter_count} chapters",
                f"[bold]{total_items}",
                f"[bold green]{total_pdf}",
                f"[bold blue]{total_html}",
                f"[bold yellow]{total_txt}",
                f"[bold dim]{total_other}"
            )

            self.console.print(table)
            self.console.print()

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self.console.print("[red]✗ Zotero database is locked[/red]")
                self.console.print("[yellow]Please close Zotero and try again[/yellow]\n")
            else:
                self.console.print(f"[red]✗ Database error: {e}[/red]\n")
        except Exception as e:
            self.console.print(f"[red]✗ Error: {e}[/red]\n")
            import traceback
            traceback.print_exc()

    def trigger_reindex(self):
        """Trigger manual re-indexing."""
        import json

        from .indexer.scrivener_indexer import ScrivenerIndexer
        from .indexer.zotero_indexer import ZoteroIndexer
        from .vectordb.client import VectorDBClient

        self.console.print("\n[bold cyan]Starting re-indexing...[/bold cyan]\n")

        try:
            # Load config
            config_path = Path(__file__).parent.parent / "config" / "default.json"
            with open(config_path) as f:
                config = json.load(f)

            # Try to load local config
            local_config_path = Path(__file__).parent.parent / "config.local.json"
            if local_config_path.exists():
                with open(local_config_path) as f:
                    local_config = json.load(f)
                    config.update(local_config)

            # Get paths from environment
            zotero_path = os.getenv("ZOTERO_PATH")
            scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

            if not zotero_path or not Path(zotero_path).exists():
                self.console.print(
                    "[red]✗ Zotero path not configured or doesn't exist[/red]"
                )
                self.console.print(
                    "[yellow]Set ZOTERO_PATH in your .env file[/yellow]\n"
                )
                return

            if not scrivener_path or not Path(scrivener_path).exists():
                self.console.print(
                    "[red]✗ Scrivener path not configured or doesn't exist[/red]"
                )
                self.console.print(
                    "[yellow]Set SCRIVENER_PROJECT_PATH in your .env file[/yellow]\n"
                )
                return

            # Initialize vector DB client
            vectordb = VectorDBClient(
                qdrant_url=qdrant_url,
                collection_name=config["vectordb"]["collection_name"],
                embedding_model=config["embedding"]["model"],
                vector_size=config["embedding"]["vector_size"],
            )

            # Index Zotero
            self.console.print("[dim]Indexing Zotero library...[/dim]")
            with Status(
                "[bold cyan]Indexing Zotero...[/bold cyan]",
                spinner="dots",
                console=self.console,
            ):
                zotero_indexer = ZoteroIndexer(
                    zotero_path=zotero_path, vectordb=vectordb, config=config
                )
                zotero_stats = zotero_indexer.index_all()

            self.console.print(
                f"[green]✓[/green] Indexed {zotero_stats.get('documents_indexed', 0)} Zotero documents "
                f"({zotero_stats.get('chunks_indexed', 0)} chunks)"
            )

            # Index Scrivener
            self.console.print("[dim]Indexing Scrivener project...[/dim]")
            with Status(
                "[bold cyan]Indexing Scrivener...[/bold cyan]",
                spinner="dots",
                console=self.console,
            ):
                scrivener_indexer = ScrivenerIndexer(
                    scrivener_path=scrivener_path, vectordb=vectordb, config=config
                )
                scrivener_stats = scrivener_indexer.index_all()

            self.console.print(
                f"[green]✓[/green] Indexed {scrivener_stats.get('documents_indexed', 0)} Scrivener documents "
                f"({scrivener_stats.get('chunks_indexed', 0)} chunks)"
            )

            self.console.print("\n[bold green]✓ Re-indexing complete![/bold green]\n")

            # Refresh RAG instance
            self.rag = BookRAG()

        except FileNotFoundError as e:
            self.console.print(f"\n[red]✗ Configuration file not found: {e}[/red]\n")
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                self.console.print("\n[red]✗ Zotero database is locked[/red]")
                self.console.print(
                    "[yellow]Please close Zotero and try again[/yellow]\n"
                )
            else:
                self.console.print(f"\n[red]✗ Database error: {e}[/red]\n")
        except Exception as e:
            self.console.print(f"\n[red]✗ Re-indexing failed: {e}[/red]\n")
            import traceback

            traceback.print_exc()

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
            new_messages = all_messages[messages_before + 1 :]

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
