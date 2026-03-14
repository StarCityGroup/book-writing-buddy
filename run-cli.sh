#!/bin/bash
# Wrapper script to ensure environment variables are set before Python starts

# If ANTHROPIC_API_KEY not set but OPENAI_API_KEY is, copy it
if [ -z "$ANTHROPIC_API_KEY" ] && [ -n "$OPENAI_API_KEY" ]; then
    export ANTHROPIC_API_KEY="$OPENAI_API_KEY"
fi

# If ANTHROPIC_BASE_URL not set but OPENAI_API_BASE is, copy it
if [ -z "$ANTHROPIC_BASE_URL" ] && [ -n "$OPENAI_API_BASE" ]; then
    export ANTHROPIC_BASE_URL="$OPENAI_API_BASE"
fi

# Run the CLI
exec uv run python main.py
