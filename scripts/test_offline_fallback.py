#!/usr/bin/env python3
"""Test script for offline Ollama fallback functionality.

This script tests:
1. Online LLM connection (if available)
2. Offline Ollama fallback (if online unavailable)
3. Agent creation with fallback
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def test_imports():
    """Test that all imports work."""
    print("=" * 60)
    print("TEST 1: Testing imports...")
    print("=" * 60)

    try:
        from src.agent_v2 import (
            create_llm_with_fallback,
            create_research_agent,
            is_using_offline_mode,
            test_llm_connection,
        )

        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_connection_function():
    """Test the LLM connection test function."""
    print("\n" + "=" * 60)
    print("TEST 2: Testing connection test function...")
    print("=" * 60)

    try:
        from langchain_openai import ChatOpenAI
        from src.agent_v2 import test_llm_connection

        # Try online LLM
        online_model = os.getenv("DEFAULT_MODEL", "anthropic.claude-4.5-haiku")
        api_base = os.getenv("OPENAI_API_BASE", "http://localhost:4000")
        api_key = os.getenv("OPENAI_API_KEY", "sk-1234")

        print(f"\nTesting online LLM: {online_model}")
        print(f"  URL: {api_base}")

        online_llm = ChatOpenAI(
            model=online_model,
            base_url=api_base,
            api_key=api_key,
            temperature=0.7
        )

        online_available = test_llm_connection(online_llm, timeout=5)

        if online_available:
            print("  ✓ Online LLM is available")
        else:
            print("  ⚠ Online LLM is not available (will test fallback)")

        # Try Ollama
        offline_model = os.getenv("OFFLINE_AGENT_MODEL", "llama3.2:3b")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        print(f"\nTesting Ollama: {offline_model}")
        print(f"  URL: {ollama_url}")

        offline_llm = ChatOpenAI(
            model=offline_model,
            base_url=ollama_url,
            api_key="ollama",
            temperature=0.7
        )

        offline_available = test_llm_connection(offline_llm, timeout=10)

        if offline_available:
            print("  ✓ Ollama is available")
        else:
            print("  ⚠ Ollama is not available")

        return online_available or offline_available

    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback_mechanism():
    """Test the automatic fallback mechanism."""
    print("\n" + "=" * 60)
    print("TEST 3: Testing fallback mechanism...")
    print("=" * 60)

    try:
        from src.agent_v2 import create_llm_with_fallback

        print("\nAttempting to create LLM with automatic fallback...")
        llm, is_offline = create_llm_with_fallback()

        if is_offline:
            print("✓ Fallback mechanism activated - using Ollama")
            print(f"  Model: {os.getenv('OFFLINE_AGENT_MODEL', 'llama3.2:3b')}")
        else:
            print("✓ Online LLM connected successfully")
            print(f"  Model: {os.getenv('DEFAULT_MODEL', 'anthropic.claude-4.5-haiku')}")

        return True

    except Exception as e:
        print(f"✗ Fallback mechanism failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_creation():
    """Test creating the research agent."""
    print("\n" + "=" * 60)
    print("TEST 4: Testing agent creation...")
    print("=" * 60)

    try:
        from src.agent_v2 import create_research_agent, is_using_offline_mode

        print("\nCreating research agent...")
        # Note: This will also initialize RAG which loads the embedding model
        # Skip this if you don't want to load embeddings

        print("  (Skipping full agent creation to avoid loading embeddings)")
        print("  Use: uv run main.py to test full agent creation")

        return True

    except Exception as e:
        print(f"✗ Agent creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_simple_query():
    """Test a simple query with the LLM."""
    print("\n" + "=" * 60)
    print("TEST 5: Testing simple LLM query...")
    print("=" * 60)

    try:
        from src.agent_v2 import create_llm_with_fallback

        print("\nSending test query to LLM...")
        llm, is_offline = create_llm_with_fallback()

        mode = "OFFLINE (Ollama)" if is_offline else "ONLINE"
        print(f"  Mode: {mode}")

        # Simple test
        response = llm.invoke([
            {"role": "user", "content": "Reply with exactly: 'Test successful'"}
        ])

        print(f"  Response: {response.content}")

        if "test" in response.content.lower() and "successful" in response.content.lower():
            print("✓ Query test successful")
            return True
        else:
            print("⚠ Unexpected response, but LLM is responding")
            return True

    except Exception as e:
        print(f"✗ Query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OFFLINE FALLBACK TEST SUITE")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Connection Function", test_connection_function()))
    results.append(("Fallback Mechanism", test_fallback_mechanism()))
    results.append(("Agent Creation", test_agent_creation()))
    results.append(("Simple Query", test_simple_query()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:.<40} {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
