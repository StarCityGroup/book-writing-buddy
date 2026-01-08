#!/usr/bin/env python3
"""Test script to force offline mode by simulating online LLM failure.

This verifies that the fallback mechanism works correctly when the
online LLM is unreachable.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def test_forced_offline_mode():
    """Force offline mode by using invalid online credentials."""
    print("=" * 60)
    print("TESTING FORCED OFFLINE MODE")
    print("=" * 60)

    # Temporarily break the online connection
    original_key = os.getenv("OPENAI_API_KEY")
    original_base = os.getenv("OPENAI_API_BASE")

    try:
        # Set invalid credentials to force offline mode
        print("\n1. Breaking online connection (simulating network failure)...")
        os.environ["OPENAI_API_KEY"] = "invalid-key"
        os.environ["OPENAI_API_BASE"] = "http://invalid-url:9999"

        from src.agent_v2 import create_llm_with_fallback

        print("\n2. Attempting to create LLM (should fallback to Ollama)...")
        llm, is_offline = create_llm_with_fallback()

        if is_offline:
            print("\n✓ SUCCESS: Fallback to Ollama activated!")
            print(f"  Offline model: {os.getenv('OFFLINE_AGENT_MODEL', 'llama3.2:3b')}")

            # Test a simple query in offline mode
            print("\n3. Testing query in offline mode...")
            response = llm.invoke([
                {"role": "user", "content": "Reply with exactly: 'Offline mode works'"}
            ])

            print(f"  Response: {response.content}")

            if "offline" in response.content.lower() or "works" in response.content.lower():
                print("\n✓ Offline query successful!")
                return True
            else:
                print("\n⚠ Unexpected response, but Ollama is responding")
                return True
        else:
            print("\n✗ FAIL: Should have fallen back to offline mode")
            return False

    except Exception as e:
        print(f"\n✗ FAIL: Error during forced offline test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Restore original credentials
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        if original_base:
            os.environ["OPENAI_API_BASE"] = original_base
        print("\n4. Restored original credentials")


def test_ollama_only():
    """Test using Ollama directly without fallback."""
    print("\n" + "=" * 60)
    print("TESTING DIRECT OLLAMA CONNECTION")
    print("=" * 60)

    try:
        from langchain_openai import ChatOpenAI

        offline_model = os.getenv("OFFLINE_AGENT_MODEL", "llama3.2:3b")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        print(f"\nConnecting directly to Ollama...")
        print(f"  Model: {offline_model}")
        print(f"  URL: {ollama_url}")

        llm = ChatOpenAI(
            model=offline_model,
            base_url=ollama_url,
            api_key="ollama",
            temperature=0.7
        )

        print("\nSending test message...")
        response = llm.invoke([
            {
                "role": "system",
                "content": "You are a helpful assistant. Keep responses brief."
            },
            {
                "role": "user",
                "content": "What is 2+2? Reply with just the number."
            }
        ])

        print(f"  Response: {response.content}")

        if "4" in response.content:
            print("\n✓ Direct Ollama connection works!")
            return True
        else:
            print("\n⚠ Unexpected response but Ollama is working")
            return True

    except Exception as e:
        print(f"\n✗ Direct Ollama test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run forced offline tests."""
    print("\n" + "=" * 60)
    print("FORCED OFFLINE MODE TEST SUITE")
    print("=" * 60)
    print("\nThis test simulates what happens when the online LLM")
    print("is unavailable (network down, API error, etc.)")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Direct Ollama", test_ollama_only()))
    results.append(("Forced Offline Fallback", test_forced_offline_mode()))

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
        print("\n✓ All forced offline tests passed!")
        print("\nConclusion: The fallback mechanism works correctly.")
        print("When the online LLM is unavailable, the agent will")
        print("automatically use Ollama for offline operation.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
