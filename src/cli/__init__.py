"""Main CLI coordinator for Book Research Agent."""

from dotenv import load_dotenv
from rich.prompt import Prompt
from rich.status import Status

from ..theme import get_console
from .agent_wrapper import AgentWrapper
from .commands import CommandHandler
from .connection import ConnectionTester
from .display import DisplayManager


class BookResearchChatCLI:
    """Interactive CLI for book research agent using Claude Agent SDK."""

    def __init__(self):
        """Initialize CLI."""
        load_dotenv()

        # Core components
        self.console = get_console()
        self.display = DisplayManager(self.console)
        self.connection = ConnectionTester(self.console)

        # Agent wrapper (SDK client)
        self.agent = AgentWrapper(self.console)

        # RAG instance (for direct queries)
        self.rag = None

        # Command handler (initialized after RAG)
        self.commands = None

    def startup_checks(self) -> bool:
        """Run startup connection checks.

        Returns:
            True if all checks pass, False otherwise
        """
        # Test Anthropic API connection
        if not self.connection.test_anthropic_connection():
            self.console.print(
                "\n[warning]Starting anyway - you can fix configuration later[/warning]\n"
            )

        # Check Qdrant
        success, rag_instance = self.connection.check_qdrant()
        if not success:
            self.console.print(
                "\n[warning]Continuing without index - some features won't work[/warning]\n"
            )
        else:
            self.rag = rag_instance

        # Initialize command handler now that we have RAG
        self.commands = CommandHandler(self.console, self.display, self.agent, self.rag)

        return True

    def run_agent(self, user_input: str):
        """Run the agent with user input.

        Args:
            user_input: User's message
        """
        try:
            # Run agent with status spinner
            with Status(
                "[header]Researching...[/header]",
                spinner="dots",
                console=self.console,
            ):
                response = self.agent.run_sync(user_input)

            if not response:
                self.console.print(
                    "\n[warning]No response generated. Try rephrasing your question.[/warning]"
                )
                return

            # Display response
            self.display.print_message("assistant", response)

        except Exception as e:
            self.console.print(f"\n[error]Error: {e}[/error]\n")
            import traceback

            traceback.print_exc()

    def run(self):
        """Run the interactive CLI."""
        # Startup checks
        self.startup_checks()

        # Welcome message
        self.display.print_welcome()

        # Main loop
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[user]You[/user]")

                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if self.commands.handle_command(user_input):
                        break  # Exit requested
                    continue

                # Run agent
                self.run_agent(user_input)

            except KeyboardInterrupt:
                self.console.print(
                    "\n\n[warning]Use /exit to quit properly.[/warning]\n"
                )
            except EOFError:
                break

        # Cleanup
        self.agent.disconnect_sync()


def main():
    """Entry point for CLI."""
    cli = BookResearchChatCLI()
    cli.run()


if __name__ == "__main__":
    main()
