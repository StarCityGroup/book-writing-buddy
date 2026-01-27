#!/usr/bin/env python3
"""Test agent configuration with LiteLLM proxy."""

import os

from dotenv import load_dotenv

from src.agent_v2 import create_agent_options

load_dotenv()


def test_agent_config():
    """Test that agent options are created correctly."""
    print("Testing agent configuration...\n")

    # Show environment variables
    print("Environment Variables:")
    print(f"  OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', '')[:20]}...")
    print(f"  OPENAI_API_BASE: {os.getenv('OPENAI_API_BASE', '')}")
    print(f"  DEFAULT_MODEL: {os.getenv('DEFAULT_MODEL', '')}\n")

    # Create options
    options = create_agent_options()

    # Display configuration
    print("Agent Configuration:")
    print(f"  Model: {options.model}")
    print(f"  Permission Mode: {options.permission_mode}")
    print(f"  MCP Servers: {list(options.mcp_servers.keys())}")
    print(f"  Number of allowed tools: {len(options.allowed_tools)}\n")

    # Display SDK environment variables
    print("SDK Environment Variables:")
    if hasattr(options, "env") and options.env:
        for key, value in options.env.items():
            if "KEY" in key:
                print(f"  {key}: {value[:20]}...")
            else:
                print(f"  {key}: {value}")
    else:
        print("  (No custom env variables set)")

    print("\n✓ Configuration looks good!")


if __name__ == "__main__":
    test_agent_config()
