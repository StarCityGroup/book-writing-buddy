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

from .agent_v2 import create_research_agent
from .rag import BookRAG


class BookResearchChatCLI:
    """Interactive CLI for book research agent."""

    def __init__(self):
        """Initialize CLI."""
        load_dotenv()

        self.console = Console()
        self.agent = create_research_agent()
        self.conversation_history = []  # Store conversation messages
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
- `/settings` - Check paths, connections, and configuration
- `/knowledge` - View indexed data, summaries, and last update times
- `/model` - Switch between model tiers (good/better/best)
- `/history` - View past conversations
- `/reindex [all|zotero|scrivener]` - Manually trigger re-indexing (close Zotero first!)
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
            self.conversation_history = []
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
                    self.agent = create_research_agent()
                    self.console.print(
                        f"\n[green]✓ Switched to {tier} ({model_map[tier]})[/green]\n"
                    )
                else:
                    self.console.print(f"\n[red]Unknown tier: {tier}[/red]")
                    self.console.print("Available: good, better, best\n")

        elif command_lower == "/knowledge":
            self.show_knowledge()

        elif command_lower.startswith("/reindex"):
            # Parse optional source parameter
            parts = command_lower.split()
            source = parts[1] if len(parts) > 1 else "all"
            if source not in ["all", "zotero", "scrivener"]:
                self.console.print(
                    "\n[yellow]Usage: /reindex [all|zotero|scrivener][/yellow]\n"
                )
            else:
                self.trigger_reindex(source)

        elif command_lower == "/settings":
            self.show_diagnostics()

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
        zotero_root_collection = os.getenv("ZOTERO_ROOT_COLLECTION")
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
            f"\n  ZOTERO_ROOT_COLLECTION: {zotero_root_collection or '[dim]NOT SET (indexes all collections)[/dim]'}"
        )
        if zotero_root_collection:
            self.console.print(
                f"    [dim]Only indexing collections under '{zotero_root_collection}'[/dim]"
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
                # Find .scrivx file dynamically (like ScrivenerParser does)
                scrivx_files = list(Path(scrivener_path).glob("*.scrivx"))
                if scrivx_files:
                    self.console.print(
                        f"    .scrivx file: [green]FOUND ({scrivx_files[0].name})[/green]"
                    )
                else:
                    self.console.print("    .scrivx file: [red]NOT FOUND[/red]")

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
        """Show comprehensive knowledge base summary including Zotero and Scrivener details."""
        self.console.print("\n[bold cyan]Knowledge Base Summary[/bold cyan]\n")

        if self.rag:
            # Overall stats
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

            # Zotero summary
            self.console.print("\n[bold cyan]═══ Zotero Library ═══[/bold cyan]")
            self.show_zotero_summary(header=False)

            # Scrivener summary
            self.console.print("\n[bold cyan]═══ Scrivener Project ═══[/bold cyan]")
            self.show_scrivener_summary(header=False)
        else:
            self.console.print("[yellow]RAG system not initialized[/yellow]")

        self.console.print()

    def show_zotero_summary(self, header: bool = True):
        """Show summary of indexed Zotero documents by chapter and type.

        Queries the Qdrant index to show what's actually indexed, not the raw
        Zotero database.

        Args:
            header: Whether to print the section header (default: True)
        """
        import re
        from collections import defaultdict

        from rich.table import Table

        if header:
            self.console.print("\n[bold cyan]Zotero Library Summary[/bold cyan]\n")

        if not self.rag:
            self.console.print("[yellow]RAG system not initialized[/yellow]\n")
            return

        try:
            # Load config to get chapter pattern
            config_path = Path(__file__).parent.parent / "config" / "default.json"
            with open(config_path) as f:
                config = json.load(f)

            chapter_pattern = (
                config.get("project", {})
                .get("zotero", {})
                .get("chapter_pattern", r"^(\d+)\.")
            )

            # Query Qdrant for all Zotero chunks
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            scroll_filter = Filter(
                must=[
                    FieldCondition(key="source_type", match=MatchValue(value="zotero"))
                ]
            )

            # Scroll through all Zotero points
            all_points = []
            offset = None
            while True:
                results, offset = self.rag.vectordb.client.scroll(
                    collection_name=self.rag.vectordb.collection_name,
                    scroll_filter=scroll_filter,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                )
                all_points.extend(results)
                if offset is None:
                    break

            if not all_points:
                self.console.print("[yellow]No Zotero documents indexed yet.[/yellow]")
                self.console.print(
                    "[dim]Run /reindex zotero to index your Zotero library.[/dim]\n"
                )
                return

            # Aggregate by collection
            collection_stats = defaultdict(
                lambda: {
                    "chunks": 0,
                    "items": set(),
                    "pdf": 0,
                    "html": 0,
                    "txt": 0,
                    "other": 0,
                }
            )

            for point in all_points:
                payload = point.payload
                coll_name = payload.get("collection_name", "Unknown")
                item_id = payload.get("item_id")
                file_type = payload.get("file_type", "")

                stats = collection_stats[coll_name]
                stats["chunks"] += 1
                if item_id:
                    stats["items"].add(item_id)

                # Count by file type
                if file_type == "pdf":
                    stats["pdf"] += 1
                elif file_type == "html":
                    stats["html"] += 1
                elif file_type == "text":
                    stats["txt"] += 1
                elif file_type:
                    stats["other"] += 1

            # Create table
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Chapter", style="bold", width=7)
            table.add_column("Collection", style="dim")
            table.add_column("Items", justify="right")
            table.add_column("Chunks", justify="right", style="cyan")
            table.add_column("PDFs", justify="right", style="green")
            table.add_column("HTML", justify="right", style="blue")
            table.add_column("TXT", justify="right", style="yellow")

            total_items = 0
            total_chunks = 0
            total_pdf = 0
            total_html = 0
            total_txt = 0
            chapter_count = 0

            # Sort collections by chapter number (numerically), then by name
            def sort_key(coll_name):
                match = re.match(chapter_pattern, coll_name)
                if match:
                    # Extract chapter number and convert to int for numeric sorting
                    # Handle "0" for preface
                    return (0, int(match.group(1)), coll_name)
                else:
                    # Non-chapter collections sort last
                    return (1, 0, coll_name)

            for coll_name in sorted(collection_stats.keys(), key=sort_key):
                stats = collection_stats[coll_name]
                items_count = len(stats["items"])

                # Extract chapter number if matches pattern
                match = re.match(chapter_pattern, coll_name)
                chapter_num = match.group(1) if match else "-"

                table.add_row(
                    chapter_num,
                    coll_name[:45] + "..." if len(coll_name) > 45 else coll_name,
                    str(items_count),
                    str(stats["chunks"]),
                    str(stats["pdf"]) if stats["pdf"] > 0 else "-",
                    str(stats["html"]) if stats["html"] > 0 else "-",
                    str(stats["txt"]) if stats["txt"] > 0 else "-",
                )

                total_items += items_count
                total_chunks += stats["chunks"]
                total_pdf += stats["pdf"]
                total_html += stats["html"]
                total_txt += stats["txt"]
                if match:
                    chapter_count += 1

            # Add totals row
            table.add_section()
            table.add_row(
                "[bold]TOTAL",
                f"[bold]{chapter_count} chapters",
                f"[bold]{total_items}",
                f"[bold cyan]{total_chunks}",
                f"[bold green]{total_pdf}",
                f"[bold blue]{total_html}",
                f"[bold yellow]{total_txt}",
            )

            self.console.print(
                f"[dim]Showing indexed Zotero data ({len(all_points):,} chunks)[/dim]\n"
            )
            self.console.print(table)
            self.console.print()

        except Exception as e:
            self.console.print(f"[red]✗ Error: {e}[/red]\n")
            import traceback

            traceback.print_exc()

    def show_scrivener_summary(self, header: bool = True):
        """Show summary of indexed Scrivener documents by chapter.

        Args:
            header: Whether to print the section header (default: True)
        """
        from rich.table import Table

        if header:
            self.console.print("\n[bold cyan]Scrivener Indexing Summary[/bold cyan]\n")

        try:
            # Get summary from RAG
            summary = self.rag.get_scrivener_summary()

            if summary.get("message"):
                self.console.print(f"[yellow]{summary['message']}[/yellow]\n")
                return

            # Display overall statistics
            stats_table = Table(show_header=False, box=None)
            stats_table.add_row(
                "[bold]Total Chapters:", f"{summary.get('total_chapters', 0)}"
            )
            stats_table.add_row(
                "[bold]Total Documents:", f"{summary.get('total_documents', 0)}"
            )
            stats_table.add_row(
                "[bold]Total Chunks:", f"{summary.get('total_chunks', 0)}"
            )
            stats_table.add_row(
                "[bold]Total Words:", f"{summary.get('total_words', 0):,}"
            )
            self.console.print(stats_table)
            self.console.print()

            # Create per-chapter table
            chapters = summary.get("chapters", [])
            if chapters:
                table = Table(show_header=True, header_style="bold cyan")
                table.add_column("Ch", style="bold", width=4)
                table.add_column("Title", style="dim")
                table.add_column("Docs", justify="right")
                table.add_column("Chunks", justify="right")
                table.add_column("Words", justify="right", style="green")
                table.add_column("Types", style="dim")

                for ch in chapters:
                    # Format document types
                    doc_types = ch.get("doc_types", {})
                    types_str = ", ".join(
                        f"{dtype}:{count}" for dtype, count in doc_types.items()
                    )

                    table.add_row(
                        str(ch["chapter_number"]),
                        ch["chapter_title"][:40] + "..."
                        if len(ch["chapter_title"]) > 40
                        else ch["chapter_title"],
                        str(ch["document_count"]),
                        str(ch["total_chunks"]),
                        f"{ch['total_words']:,}",
                        types_str[:30] + "..." if len(types_str) > 30 else types_str,
                    )

                self.console.print(table)
                self.console.print()

            # Show unassigned documents if any
            unassigned_count = summary.get("unassigned_count", 0)
            if unassigned_count > 0:
                self.console.print(
                    f"[yellow]⚠ {unassigned_count} unassigned documents[/yellow]"
                )
                unassigned_docs = summary.get("unassigned_docs", [])
                if unassigned_docs:
                    self.console.print("[dim]Sample unassigned documents:[/dim]")
                    for doc in unassigned_docs[:5]:
                        self.console.print(
                            f"  [dim]• {doc['doc_type']}: {doc['words']} words[/dim]"
                        )
                self.console.print()

        except Exception as e:
            self.console.print(f"[red]✗ Error: {e}[/red]\n")
            import traceback

            traceback.print_exc()

    def trigger_reindex(self, source: str = "all"):
        """Trigger manual re-indexing.

        Args:
            source: Which source to reindex - "all", "zotero", or "scrivener"
        """
        import json

        from .indexer.scrivener_indexer import ScrivenerIndexer
        from .indexer.zotero_indexer import ZoteroIndexer
        from .vectordb.client import VectorDBClient

        if source == "all":
            self.console.print(
                "\n[bold cyan]Starting re-indexing (all sources)...[/bold cyan]\n"
            )
        else:
            self.console.print(
                f"\n[bold cyan]Starting re-indexing ({source} only)...[/bold cyan]\n"
            )

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
            scrivener_manuscript_folder = os.getenv("SCRIVENER_MANUSCRIPT_FOLDER", "")
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

            # Validate paths based on what we're indexing
            if source in ["all", "zotero"]:
                if not zotero_path or not Path(zotero_path).exists():
                    self.console.print(
                        "[red]✗ Zotero path not configured or doesn't exist[/red]"
                    )
                    self.console.print(
                        "[yellow]Set ZOTERO_PATH in your .env file[/yellow]\n"
                    )
                    return

            if source in ["all", "scrivener"]:
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

            # Index Zotero (if requested)
            if source in ["all", "zotero"]:
                # Delete old Zotero data first
                self.console.print("[dim]Removing old Zotero data...[/dim]")
                vectordb.delete_by_source("zotero")

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

            # Index Scrivener (if requested)
            if source in ["all", "scrivener"]:
                # Delete old Scrivener data first
                self.console.print("[dim]Removing old Scrivener data...[/dim]")
                vectordb.delete_by_source("scrivener")

                self.console.print("[dim]Indexing Scrivener project...[/dim]")
                with Status(
                    "[bold cyan]Indexing Scrivener...[/bold cyan]",
                    spinner="dots",
                    console=self.console,
                ):
                    scrivener_indexer = ScrivenerIndexer(
                        scrivener_path=scrivener_path,
                        vectordb=vectordb,
                        config=config,
                        manuscript_folder=scrivener_manuscript_folder or None,
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
        if not self.conversation_history:
            return

        filepath = self.conversation_dir / f"conversation_{self.session_id}.json"

        conversation_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "messages": self.conversation_history,
        }

        with open(filepath, "w") as f:
            json.dump(conversation_data, f, indent=2, default=str)

    def run_agent(self, user_input: str):
        """Run the agent with user input.

        Args:
            user_input: User's message
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})

        try:
            # Run agent with thinking spinner
            with Status(
                "[bold cyan]Researching...[/bold cyan]",
                spinner="dots",
                console=self.console,
            ):
                # LangGraph ReAct agent expects {"messages": [HumanMessage(...)]}
                result = self.agent.invoke(
                    {"messages": [{"role": "user", "content": user_input}]}
                )

            # Extract response from LangGraph format
            # Result format: {"messages": [HumanMessage, AIMessage, ...]}
            messages = result.get("messages", [])
            if not messages:
                self.console.print(
                    "\n[yellow]No response generated. Try rephrasing your question.[/yellow]"
                )
                return

            # Get last AI message
            last_message = messages[-1]
            response = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message)
            )

            if not response:
                self.console.print(
                    "\n[yellow]No response generated. Try rephrasing your question.[/yellow]"
                )
                return

            # Add to history
            self.conversation_history.append({"role": "assistant", "content": response})

            # Display response
            self.print_message("assistant", response)

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
