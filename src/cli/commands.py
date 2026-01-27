"""Command handlers for CLI."""

import os
from datetime import datetime
from pathlib import Path


class CommandHandler:
    """Handles CLI commands (/help, /model, etc.)."""

    def __init__(self, console, display_manager, agent_wrapper, rag):
        """Initialize command handler.

        Args:
            console: Rich console for output
            display_manager: DisplayManager instance
            agent_wrapper: AgentWrapper instance
            rag: BookRAG instance (can be None)
        """
        self.console = console
        self.display = display_manager
        self.agent = agent_wrapper
        self.rag = rag
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_dir = Path("conversations")
        self.conversation_dir.mkdir(exist_ok=True)

    def handle_command(self, command: str) -> bool:
        """Handle CLI commands.

        Args:
            command: Command string

        Returns:
            True if should exit, False otherwise
        """
        command_lower = command.lower().strip()

        if command_lower == "/exit":
            self.console.print(
                "\n[warning]Goodbye! Your conversation has been saved.[/warning]\n"
            )
            return True

        elif command_lower == "/help":
            self.display.print_welcome()

        elif command_lower == "/new":
            self.agent.reset_sync()
            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.console.print("\n[success]Started new research session.[/success]\n")

        elif command_lower.startswith("/model"):
            self._handle_model_command(command.strip())

        elif command_lower == "/knowledge":
            self._show_knowledge()

        elif command_lower == "/reindex":
            self._trigger_reindex()

        elif command_lower == "/settings":
            self._show_diagnostics()

        elif command_lower == "/history":
            self.console.print(
                "\n[info]Conversation history is now managed by the SDK.[/info]\n"
            )

        else:
            self.console.print(f"\n[error]Unknown command: {command}[/error]")
            self.console.print("Type /help for available commands.\n")

        return False

    def _handle_model_command(self, command: str):
        """Handle /model command."""
        parts = command.split()
        model_map = {
            "good": os.getenv("MODEL_GOOD", "anthropic.claude-4.5-haiku"),
            "better": os.getenv("MODEL_BETTER", "anthropic.claude-4.5-sonnet"),
            "best": os.getenv("MODEL_BEST", "anthropic.claude-4.5-opus"),
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
            self.console.print(f"  - good   ({model_map['good']}) - Fast & economical")
            self.console.print(f"  - better ({model_map['better']}) - Balanced")
            self.console.print(f"  - best   ({model_map['best']}) - Highest quality")
            self.console.print("\nUsage: /model <good|better|best>\n")
        else:
            tier = parts[1].lower()
            if tier in model_map:
                os.environ["DEFAULT_MODEL"] = model_map[tier]
                # Update agent with new model
                self.agent.update_model_sync(model_map[tier])
                self.console.print(
                    f"\n[success]✓ Switched to {tier} ({model_map[tier]})[/success]\n"
                )
            else:
                self.console.print(f"\n[error]Unknown tier: {tier}[/error]")
                self.console.print("Available: good, better, best\n")

    def _show_knowledge(self):
        """Show knowledge base status."""
        if not self.rag:
            self.console.print("[warning]RAG system not initialized[/warning]")
            return

        stats = self.rag.get_index_stats()
        self.console.print("\n[header]Knowledge Base Status[/header]\n")
        self.console.print(f"Total indexed chunks: {stats['points_count']:,}")
        self.console.print(
            f"Last indexed: {stats.get('last_indexed', {}).get('all', 'unknown')}"
        )
        self.console.print()

    def _trigger_reindex(self):
        """Trigger complete re-indexing by clearing data and restarting services."""
        self.console.print("\n[header]Triggering complete re-index...[/header]")
        self.console.print(
            "[warning]Note: Close Zotero before indexing to avoid database locks![/warning]\n"
        )

        import subprocess

        try:
            # Stop services
            self.console.print("[muted]Stopping services...[/muted]")
            subprocess.run(["docker", "compose", "down"], check=True, capture_output=True)

            # Clear existing data
            self.console.print("[muted]Clearing vector database...[/muted]")
            subprocess.run(["rm", "-rf", "data/qdrant_storage/*"], shell=True, check=True)

            # Rebuild and restart
            self.console.print("[muted]Rebuilding and starting services...[/muted]")
            subprocess.run(["docker", "compose", "up", "--build", "-d"], check=True, capture_output=True)

            self.console.print("\n[success]✓ Re-index started! Check progress with: docker compose logs -f watcher[/success]\n")

        except subprocess.CalledProcessError as e:
            self.console.print(f"\n[error]Re-indexing failed: {e}[/error]\n")
        except Exception as e:
            self.console.print(f"\n[error]Error: {e}[/error]\n")

    def _show_diagnostics(self):
        """Show diagnostic information."""
        self.console.print("\n[header]System Diagnostics[/header]\n")

        # Environment variables
        self.console.print("[bold]Environment Variables:[/bold]")
        zotero_path = os.getenv("ZOTERO_PATH")
        scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")

        self.console.print(f"  ZOTERO_PATH: {zotero_path or '[error]NOT SET[/error]'}")
        if zotero_path:
            exists = Path(zotero_path).exists()
            self.console.print(
                f"    Exists: {'[success]YES[/success]' if exists else '[error]NO[/error]'}"
            )

        self.console.print(
            f"\n  SCRIVENER_PROJECT_PATH: {scrivener_path or '[error]NOT SET[/error]'}"
        )
        if scrivener_path:
            exists = Path(scrivener_path).exists()
            self.console.print(
                f"    Exists: {'[success]YES[/success]' if exists else '[error]NO[/error]'}"
            )

        self.console.print(f"\n  QDRANT_URL: {qdrant_url}")

        # Qdrant connection
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

        self.console.print()
