"""Custom Rich theme for better contrast on light and dark terminals."""

from rich.theme import Theme

# Custom theme with colors that work well on both light and dark backgrounds
# Uses deeper, more saturated colors for better contrast
BOOK_BUDDY_THEME = Theme(
    {
        # Semantic styles for different message types
        "success": "bold green",
        "error": "bold red",
        "warning": "bold dark_orange",
        "info": "blue",
        # User/agent conversation styles
        "user": "bold blue",  # Changed from cyan for better contrast
        "agent": "bold magenta",  # Changed from green for distinction
        "system": "dim italic",
        # Headers and emphasis
        "header": "bold blue",  # Changed from cyan
        "subheader": "bold",
        "emphasis": "bold",
        "highlight": "bold magenta",
        # Status indicators
        "checkmark": "bold green",
        "cross": "bold red",
        "bullet": "blue",
        # Data display
        "number": "magenta",
        "path": "blue underline",
        "filename": "bold blue",
        # Table styling (for compatibility)
        "table.header": "bold blue",
        "table.cell": "white",
        # Dim text (relative, adapts to background)
        "muted": "dim",
        # Command/code
        "command": "bold cyan",
    }
)


def get_console():
    """Get a Rich Console instance with the custom theme.

    Returns:
        Console: Rich Console with custom theme applied
    """
    from rich.console import Console

    return Console(theme=BOOK_BUDDY_THEME)
