#!/usr/bin/env python3
"""Entry point for Book Research Buddy CLI."""

# CRITICAL: Load environment variables BEFORE any imports
# The Claude Agent SDK checks ANTHROPIC_API_KEY at import time
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# CRITICAL: Unset CLAUDECODE to force API transport mode
# When CLAUDECODE=1 (running inside Claude Code), the SDK defaults to subprocess CLI mode
# which fails with nested session errors. We want API transport instead.
if "CLAUDECODE" in os.environ:
    del os.environ["CLAUDECODE"]

# Set ANTHROPIC_* variables from OPENAI_* if not already set
# This must happen before importing claude_agent_sdk
if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("OPENAI_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.getenv("OPENAI_API_KEY")
if not os.getenv("ANTHROPIC_BASE_URL") and os.getenv("OPENAI_API_BASE"):
    os.environ["ANTHROPIC_BASE_URL"] = os.getenv("OPENAI_API_BASE")

# NOW we can import the CLI
from src.cli import main

if __name__ == "__main__":
    main()
