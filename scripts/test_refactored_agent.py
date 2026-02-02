#!/usr/bin/env python3
"""Test script for refactored agent without MCP wrapper."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from claude_agent_sdk import ClaudeSDKClient
from src.agent_v2 import create_agent_options

load_dotenv()


async def test_basic_tool():
    """Test basic tool usage - list_chapters."""
    print("\n=== Test 1: Basic Tool (list_chapters) ===")

    options = create_agent_options()
    client = ClaudeSDKClient(options=options)

    try:
        response = await client.execute_async("List all chapters")
        print(f"Response: {response[:500]}...")
        print("✓ Test 1 passed: list_chapters works")
    except Exception as e:
        print(f"✗ Test 1 failed: {e}")
    finally:
        await client.disconnect_async()


async def test_search_tool():
    """Test search_research tool."""
    print("\n=== Test 2: Search Tool (search_research) ===")

    options = create_agent_options()
    client = ClaudeSDKClient(options=options)

    try:
        response = await client.execute_async("Search for climate adaptation in chapter 5")
        print(f"Response: {response[:500]}...")
        print("✓ Test 2 passed: search_research works")
    except Exception as e:
        print(f"✗ Test 2 failed: {e}")
    finally:
        await client.disconnect_async()


async def test_skill():
    """Test a skill - analyze_chapter."""
    print("\n=== Test 3: Skill (analyze_chapter) ===")

    options = create_agent_options()
    client = ClaudeSDKClient(options=options)

    try:
        response = await client.execute_async("Analyze chapter 9")
        print(f"Response: {response[:500]}...")
        print("✓ Test 3 passed: analyze_chapter skill works")
    except Exception as e:
        print(f"✗ Test 3 failed: {e}")
    finally:
        await client.disconnect_async()


async def test_tool_names():
    """Verify tool names don't have mcp__ prefix."""
    print("\n=== Test 4: Tool Names ===")

    options = create_agent_options()

    tool_names = [tool.name for tool in options.tools]
    print(f"Found {len(tool_names)} tools:")
    for name in tool_names:
        print(f"  - {name}")

    # Check for MCP prefix
    mcp_tools = [name for name in tool_names if "mcp__" in name]
    if mcp_tools:
        print(f"✗ Test 4 failed: Found MCP-prefixed tools: {mcp_tools}")
    else:
        print("✓ Test 4 passed: No MCP prefixes found")


async def main():
    """Run all tests."""
    print("Testing refactored agent...")
    print("=" * 60)

    # Test tool names first (doesn't require API call)
    await test_tool_names()

    # Test basic functionality
    await test_basic_tool()
    await test_search_tool()
    await test_skill()

    print("\n" + "=" * 60)
    print("All tests complete!")


if __name__ == "__main__":
    asyncio.run(main())
