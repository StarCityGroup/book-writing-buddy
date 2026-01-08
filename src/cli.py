"""CLI chat interface for book research agent."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status

from .agent_v2 import create_research_agent, is_using_offline_mode
from .theme import get_console
from .tools import get_rag


class BookResearchChatCLI:
    """Interactive CLI for book research agent."""

    def __init__(self):
        """Initialize CLI."""
        load_dotenv()

        self.console = get_console()  # Use themed console
        self.agent = create_research_agent()
        self.conversation_history = []  # Store conversation messages
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_dir = Path("conversations")
        self.conversation_dir.mkdir(exist_ok=True)
        self.rag = None  # Initialized in run()

    def test_connection(self):
        """Initialize agent and display connection status.

        The agent automatically handles online/offline fallback.

        Returns:
            True (always, since fallback is handled automatically)
        """
        self.console.print("\n[muted]Initializing LLM agent...[/muted]")

        # Agent creation handles connection testing and fallback
        # No need to test separately - just check the result
        if is_using_offline_mode():
            offline_model = os.getenv("OFFLINE_AGENT_MODEL", "llama3.2:3b")
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.console.print("[warning]⚠ Using offline mode with Ollama[/warning]")
            self.console.print(
                f"[muted]  Model: {offline_model} at {ollama_url}[/muted]"
            )
            self.console.print(
                "[muted]  Note: Local LLM generation is slower - responses will stream[/muted]"
            )
        else:
            online_model = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-haiku")
            api_base = os.getenv("OPENAI_API_BASE") or os.getenv(
                "LITELLM_PROXY_URL", "http://localhost:4000"
            )
            self.console.print(
                f"[checkmark]✓[/checkmark] [muted]Connected to {online_model} at {api_base}[/muted]"
            )

        return True

    def check_qdrant(self):
        """Check Qdrant connection and index status.

        Returns:
            True if successful, False otherwise
        """
        self.console.print("[muted]Checking Qdrant vector database...[/muted]")

        try:
            self.rag = get_rag()

            # Backfill timestamps if needed (for data indexed before timestamp feature)
            self.rag.vectordb.backfill_timestamps_if_needed()

            stats = self.rag.get_index_stats()

            if stats["points_count"] > 0:
                self.console.print(
                    f"[checkmark]✓[/checkmark] [muted]Index ready: {stats['points_count']:,} chunks[/muted]"
                )

                # Show last index times
                last_indexed = stats["last_indexed"]
                if last_indexed["zotero"] or last_indexed["scrivener"]:
                    self.console.print(
                        f"[muted]  Last indexed: "
                        f"Zotero {last_indexed.get('zotero', 'never')}, "
                        f"Scrivener {last_indexed.get('scrivener', 'never')}[/muted]"
                    )

                return True
            else:
                self.console.print(
                    "[warning]⚠ Index is empty - run indexer first[/warning]"
                )
                return False

        except Exception as e:
            self.console.print(f"[cross]✗ Qdrant connection failed: {str(e)}[/error]")
            self.console.print(
                "[warning]Make sure Qdrant is running: docker compose up -d qdrant[/warning]\n"
            )
            return False

    def print_welcome(self):
        """Print welcome message."""
        welcome = """
# Book Writing Buddy

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

<table>
<tr>
<td width="50%">

- `/help` - Show this help
- `/settings` - Check configuration
- `/knowledge` - View indexed data
- `/model` - Switch model tiers

</td>
<td width="50%">

- `/history` - View past conversations
- `/reindex [source]` - Re-index data
- `/new` - Start fresh conversation
- `/exit` - Exit application

</td>
</tr>
</table>

**Just ask a question to get started!** Examples:
- "Track the theme 'infrastructure failure' across all chapters"
- "Compare research density between chapters 5 and 9"
- "What are the key sources for chapter 3?"
- "Get all my Zotero annotations for chapter 9"
        """
        self.console.print(Panel(Markdown(welcome), border_style="info"))

    def print_message(self, role: str, content: str):
        """Print a formatted message.

        Args:
            role: Message role (user/assistant/system)
            content: Message content
        """
        if role == "user":
            self.console.print(f"\n[user]You:[/user] {content}")
        elif role == "assistant":
            self.console.print("\n[agent]Agent:[/agent]")
            self.console.print(Markdown(content))
        elif role == "system":
            self.console.print(f"\n[muted]{content}[/muted]")

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
                "\n[warning]Goodbye! Your conversation has been saved.[/warning]\n"
            )
            return True

        elif command_lower == "/help":
            self.print_welcome()

        elif command_lower == "/new":
            self.save_conversation()
            self.conversation_history = []
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.console.print("\n[success]Started new research session.[/success]\n")

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
                self.console.print(f"\n[info]Current model: {current}[/info]")
                if current_tier != "custom":
                    self.console.print(f"[info]Tier: {current_tier}[/info]")
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
                        f"\n[success]✓ Switched to {tier} ({model_map[tier]})[/success]\n"
                    )
                else:
                    self.console.print(f"\n[error]Unknown tier: {tier}[/error]")
                    self.console.print("Available: good, better, best\n")

        elif command_lower == "/knowledge":
            self.show_knowledge()

        elif command_lower.startswith("/reindex"):
            # Parse optional source parameter
            parts = command_lower.split()
            source = parts[1] if len(parts) > 1 else "all"
            if source not in ["all", "zotero", "scrivener"]:
                self.console.print(
                    "\n[warning]Usage: /reindex [all|zotero|scrivener][/warning]\n"
                )
            else:
                self.trigger_reindex(source)

        elif command_lower == "/settings":
            self.show_diagnostics()

        else:
            self.console.print(f"\n[error]Unknown command: {command}[/error]")
            self.console.print("Type /help for available commands.\n")

        return False

    def show_diagnostics(self):
        """Show diagnostic information about paths and configuration."""
        self.console.print("\n[header]System Diagnostics[/header]\n")

        # Check environment variables
        self.console.print("[bold]Environment Variables:[/bold]")
        zotero_path = os.getenv("ZOTERO_PATH")
        zotero_root_collection = os.getenv("ZOTERO_ROOT_COLLECTION")
        scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

        self.console.print(f"  ZOTERO_PATH: {zotero_path or '[error]NOT SET[/error]'}")
        if zotero_path:
            exists = Path(zotero_path).exists()
            self.console.print(
                f"    Exists: {'[success]YES[/success]' if exists else '[error]NO[/error]'}"
            )
            if exists:
                db_path = Path(zotero_path) / "zotero.sqlite"
                db_exists = db_path.exists()
                self.console.print(
                    f"    Database: {'[success]FOUND[/success]' if db_exists else '[error]NOT FOUND[/error]'}"
                )

        self.console.print(
            f"\n  ZOTERO_ROOT_COLLECTION: {zotero_root_collection or '[muted]NOT SET (indexes all collections)[/muted]'}"
        )
        if zotero_root_collection:
            self.console.print(
                f"    [muted]Only indexing collections under '{zotero_root_collection}'[/muted]"
            )

        self.console.print(
            f"\n  SCRIVENER_PROJECT_PATH: {scrivener_path or '[error]NOT SET[/error]'}"
        )
        if scrivener_path:
            exists = Path(scrivener_path).exists()
            self.console.print(
                f"    Exists: {'[success]YES[/success]' if exists else '[error]NO[/error]'}"
            )
            if exists:
                # Find .scrivx file dynamically (like ScrivenerParser does)
                scrivx_files = list(Path(scrivener_path).glob("*.scrivx"))
                if scrivx_files:
                    self.console.print(
                        f"    .scrivx file: [success]FOUND ({scrivx_files[0].name})[/success]"
                    )
                else:
                    self.console.print("    .scrivx file: [error]NOT FOUND[/error]")

        self.console.print(f"\n  QDRANT_URL: {qdrant_url}")

        # Test Qdrant connection
        self.console.print("\n[bold]Qdrant Connection:[/bold]")
        if self.rag:
            try:
                info = self.rag.vectordb.get_collection_info()
                self.console.print("  Status: [success]CONNECTED[/success]")
                self.console.print(f"  Points: {info['points_count']:,}")
            except Exception as e:
                self.console.print(f"  Status: [error]FAILED[/error] - {e}")
        else:
            self.console.print("  [warning]RAG not initialized[/warning]")

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
                        "  [warning]No chapter numbers in sample[/warning]"
                    )

            except Exception as e:
                self.console.print(f"  [error]Error sampling data: {e}[/error]")

        self.console.print()

    def show_knowledge(self):
        """Show comprehensive knowledge base summary including Zotero and Scrivener details."""
        self.console.print("\n[header]Knowledge Base Summary[/header]\n")

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
            self.console.print("\n[header]═══ Zotero Library ═══[/header]")
            self.show_zotero_summary(header=False)

            # Scrivener summary
            self.console.print("\n[header]═══ Scrivener Project ═══[/header]")
            self.show_scrivener_summary(header=False)
        else:
            self.console.print("[warning]RAG system not initialized[/warning]")

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
            self.console.print("\n[header]Zotero Library Summary[/header]\n")

        if not self.rag:
            self.console.print("[warning]RAG system not initialized[/warning]\n")
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
                self.console.print(
                    "[warning]No Zotero documents indexed yet.[/warning]"
                )
                self.console.print(
                    "[muted]Run /reindex zotero to index your Zotero library.[/muted]\n"
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
            table = Table(show_header=True, header_style="table.header")
            table.add_column("Chapter", style="bold", width=7)
            table.add_column("Collection", style="muted")
            table.add_column("Items", justify="right")
            table.add_column("Chunks", justify="right", style="number")
            table.add_column("PDFs", justify="right", style="success")
            table.add_column("HTML", justify="right", style="info")
            table.add_column("TXT", justify="right", style="highlight")

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
                f"[number]{total_chunks}",
                f"[success]{total_pdf}",
                f"[info]{total_html}",
                f"[highlight]{total_txt}",
            )

            self.console.print(
                f"[muted]Showing indexed Zotero data ({len(all_points):,} chunks)[/muted]\n"
            )
            self.console.print(table)
            self.console.print()

        except Exception as e:
            self.console.print(f"[cross]✗ Error: {e}[/error]\n")
            import traceback

            traceback.print_exc()

    def show_scrivener_summary(self, header: bool = True):
        """Show summary of indexed Scrivener documents by chapter.

        Args:
            header: Whether to print the section header (default: True)
        """
        from rich.table import Table

        if header:
            self.console.print("\n[header]Scrivener Indexing Summary[/header]\n")

        try:
            # Get summary from RAG
            summary = self.rag.get_scrivener_summary()

            if summary.get("message"):
                self.console.print(f"[warning]{summary['message']}[/warning]\n")
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
                table = Table(show_header=True, header_style="table.header")
                table.add_column("Ch", style="bold", width=4)
                table.add_column("Title", style="muted")
                table.add_column("Docs", justify="right")
                table.add_column("Chunks", justify="right")
                table.add_column("Words", justify="right", style="success")
                table.add_column("Types", style="muted")

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
                    f"[warning]⚠ {unassigned_count} unassigned documents[/warning]"
                )
                unassigned_docs = summary.get("unassigned_docs", [])
                if unassigned_docs:
                    self.console.print("[muted]Sample unassigned documents:[/muted]")
                    for doc in unassigned_docs[:5]:
                        self.console.print(
                            f"  [muted]• {doc['doc_type']}: {doc['words']} words[/muted]"
                        )
                self.console.print()

        except Exception as e:
            self.console.print(f"[cross]✗ Error: {e}[/error]\n")
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
                "\n[header]Starting re-indexing (all sources)...[/header]\n"
            )
        else:
            self.console.print(
                f"\n[header]Starting re-indexing ({source} only)...[/header]\n"
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
                        "[cross]✗ Zotero path not configured or doesn't exist[/error]"
                    )
                    self.console.print(
                        "[warning]Set ZOTERO_PATH in your .env file[/warning]\n"
                    )
                    return

            if source in ["all", "scrivener"]:
                if not scrivener_path or not Path(scrivener_path).exists():
                    self.console.print(
                        "[cross]✗ Scrivener path not configured or doesn't exist[/error]"
                    )
                    self.console.print(
                        "[warning]Set SCRIVENER_PROJECT_PATH in your .env file[/warning]\n"
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
                self.console.print("[muted]Removing old Zotero data...[/muted]")
                vectordb.delete_by_source("zotero")

                self.console.print("[muted]Indexing Zotero library...[/muted]")
                with Status(
                    "[header]Indexing Zotero...[/header]",
                    spinner="dots",
                    console=self.console,
                ):
                    zotero_indexer = ZoteroIndexer(
                        zotero_path=zotero_path, vectordb=vectordb, config=config
                    )
                    zotero_stats = zotero_indexer.index_all()

                self.console.print(
                    f"[checkmark]✓[/checkmark] Indexed {zotero_stats.get('documents_indexed', 0)} Zotero documents "
                    f"({zotero_stats.get('chunks_indexed', 0)} chunks)"
                )

            # Index Scrivener (if requested)
            if source in ["all", "scrivener"]:
                # Delete old Scrivener data first
                self.console.print("[muted]Removing old Scrivener data...[/muted]")
                vectordb.delete_by_source("scrivener")

                self.console.print("[muted]Indexing Scrivener project...[/muted]")
                with Status(
                    "[header]Indexing Scrivener...[/header]",
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
                    f"[checkmark]✓[/checkmark] Indexed {scrivener_stats.get('documents_indexed', 0)} Scrivener documents "
                    f"({scrivener_stats.get('chunks_indexed', 0)} chunks)"
                )

            self.console.print("\n[success]✓ Re-indexing complete![/bold green]\n")

            # Refresh RAG instance (uses singleton)
            self.rag = get_rag()

        except FileNotFoundError as e:
            self.console.print(
                f"\n[cross]✗ Configuration file not found: {e}[/error]\n"
            )
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                self.console.print("\n[cross]✗ Zotero database is locked[/error]")
                self.console.print(
                    "[warning]Please close Zotero and try again[/warning]\n"
                )
            else:
                self.console.print(f"\n[cross]✗ Database error: {e}[/error]\n")
        except Exception as e:
            self.console.print(f"\n[cross]✗ Re-indexing failed: {e}[/error]\n")
            import traceback

            traceback.print_exc()

    def show_history(self):
        """Show past conversations."""
        if not self.conversation_dir.exists():
            self.console.print("\n[warning]No conversations found yet.[/warning]\n")
            return

        conversations = sorted(self.conversation_dir.glob("*.json"), reverse=True)
        if not conversations:
            self.console.print("\n[warning]No conversations found yet.[/warning]\n")
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
                "[header]Researching...[/header]",
                spinner="dots",
                console=self.console,
            ):
                # LangGraph ReAct agent expects {"messages": [...]} with full history
                result = self.agent.invoke({"messages": self.conversation_history})

            # Extract response from LangGraph format
            # Result format: {"messages": [HumanMessage, AIMessage, ...]}
            messages = result.get("messages", [])
            if not messages:
                self.console.print(
                    "\n[warning]No response generated. Try rephrasing your question.[/warning]"
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
                    "\n[warning]No response generated. Try rephrasing your question.[/warning]"
                )
                return

            # Add to history
            self.conversation_history.append({"role": "assistant", "content": response})

            # Display response
            self.print_message("assistant", response)

        except Exception as e:
            self.console.print(f"\n[error]Error: {e}[/error]\n")
            import traceback

            traceback.print_exc()

    def run(self):
        """Run the interactive CLI."""
        # Initialize connection (automatically handles online/offline fallback)
        self.test_connection()

        # Check Qdrant
        if not self.check_qdrant():
            self.console.print(
                "\n[warning]Continuing without index - some features won't work[/warning]\n"
            )

        self.print_welcome()

        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[user]You[/user]")

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
                self.console.print(
                    "\n\n[warning]Use /exit to quit properly.[/warning]\n"
                )
            except EOFError:
                break

        self.save_conversation()


def main():
    """Entry point for CLI."""
    cli = BookResearchChatCLI()
    cli.run()


if __name__ == "__main__":
    main()
