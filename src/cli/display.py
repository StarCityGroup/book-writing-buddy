"""Display functions for CLI."""

from rich.markdown import Markdown
from rich.panel import Panel


class DisplayManager:
    """Handles all display/UI output for CLI."""

    def __init__(self, console):
        """Initialize display manager.

        Args:
            console: Rich console for output
        """
        self.console = console

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
