"""SDK agent wrapper for CLI."""

import asyncio
from typing import Optional

from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, TextBlock, ToolUseBlock

from ..agent_v2 import create_agent_options


class AgentWrapper:
    """Wraps ClaudeSDKClient for CLI usage."""

    def __init__(self, console):
        """Initialize agent wrapper.

        Args:
            console: Rich console for output
        """
        self.console = console
        self.client: Optional[ClaudeSDKClient] = None
        self.options = create_agent_options()

    async def connect(self):
        """Connect to Claude SDK client."""
        if self.client is None:
            self.client = ClaudeSDKClient(self.options)
            await self.client.connect()

    async def disconnect(self):
        """Disconnect from Claude SDK client."""
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def reset_conversation(self):
        """Reset conversation by disconnecting and reconnecting."""
        await self.disconnect()
        # Client will be recreated on next query

    async def update_model(self, model_name: str):
        """Update the model and recreate client.

        Args:
            model_name: New model name
        """
        await self.disconnect()
        # Update options with new model
        self.options = create_agent_options()  # This will pick up env var changes

    async def query(self, user_input: str) -> str:
        """Send query to agent and get response.

        Args:
            user_input: User's message

        Returns:
            Agent's response text
        """
        # Ensure connected
        await self.connect()

        # Send query
        await self.client.query(user_input)

        # Collect response
        response_parts = []
        tool_uses = []

        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append(block.name)

        # Log tool usage (optional)
        if tool_uses:
            self.console.print(
                f"[muted]Tools used: {', '.join(set(tool_uses))}[/muted]",
                style="dim",
            )

        return "\n".join(response_parts) if response_parts else ""

    def run_sync(self, user_input: str) -> str:
        """Synchronous wrapper for query (for CLI usage).

        Args:
            user_input: User's message

        Returns:
            Agent's response text
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.query(user_input))

    def reset_sync(self):
        """Synchronous wrapper for reset_conversation."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.reset_conversation())

    def update_model_sync(self, model_name: str):
        """Synchronous wrapper for update_model."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.update_model(model_name))

    def disconnect_sync(self):
        """Synchronous wrapper for disconnect."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.disconnect())
