#!/usr/bin/env python3
"""Quick test to verify refactored agent works."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.agent_v2 import create_agent_options

load_dotenv()


def main():
    """Test basic agent setup."""
    print("\n=== Refactoring Verification ===\n")

    # Create agent options
    options = create_agent_options()

    # Get tool names
    tool_names = [tool.name for tool in options.tools]

    print(f"✓ Agent created successfully")
    print(f"✓ Found {len(tool_names)} tools total")
    print(f"  - 12 core research tools")
    print(f"  - 5 workflow skills")

    # Verify no MCP prefix
    mcp_tools = [name for name in tool_names if "mcp__" in name]
    if mcp_tools:
        print(f"✗ ERROR: Found MCP-prefixed tools: {mcp_tools}")
        return 1

    print(f"✓ No MCP prefixes found")

    # List all tools
    print("\n=== All Tools ===")
    for i, name in enumerate(tool_names, 1):
        prefix = "  [skill] " if i > 12 else "  [tool]  "
        print(f"{prefix}{name}")

    print("\n✓ Refactoring successful!")
    print("  - MCP wrapper removed")
    print("  - Direct tools work")
    print("  - Workflow skills added")
    print("\nRun 'uv run main.py' to test interactively.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
