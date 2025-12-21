#!/usr/bin/env python3
"""Run all tests for the new functionality."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_env():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if env_file.exists():
        print("📄 Loading .env file...")
        for line in env_file.read_text().split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
        print("✅ Environment loaded\n")
    else:
        print("⚠️  No .env file found\n")


def test_scrivener_parser():
    """Test Scrivener parser."""
    print("\n" + "=" * 60)
    print("TEST 1: Scrivener Parser")
    print("=" * 60)

    scrivener_path = os.getenv("SCRIVENER_PROJECT_PATH")
    if not scrivener_path or not Path(scrivener_path).exists():
        print("⚠️  SCRIVENER_PROJECT_PATH not configured, skipping")
        return False

    try:
        from src.scrivener_parser import ScrivenerParser

        parser = ScrivenerParser(scrivener_path)
        structure = parser.get_chapter_structure()

        print(f"✅ Parsed {len(structure['chapters'])} chapters")
        print("\n📚 Sample chapters:")
        for ch in structure["chapters"][:3]:
            print(f"  Chapter {ch['number']}: {ch['title']}")

        # Show formatted text
        text = parser.format_structure_as_text()
        print(f"\n📄 Formatted output ({len(text)} chars)")

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_context_loading():
    """Test context loading from both sources."""
    print("\n" + "=" * 60)
    print("TEST 2: Context Loading")
    print("=" * 60)

    try:
        from src.nodes import load_book_context

        context = load_book_context()

        print(f"✅ Loaded context ({len(context)} chars)")

        # Check for both sources
        has_scrivener = "Scrivener Structure" in context
        has_outline = any(
            x in context for x in ["Book Outline", "FIREWALL", "Climate", "Adaptation"]
        )

        print("\n📊 Context Sources:")
        print(f"  Scrivener: {'✅' if has_scrivener else '❌'}")
        print(f"  Outline: {'✅' if has_outline else '❌'}")

        # Show preview
        print("\n📋 Preview (first 500 chars):")
        print("-" * 60)
        print(context[:500])
        print("-" * 60)

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_sync_checker():
    """Test sync checker."""
    print("\n" + "=" * 60)
    print("TEST 3: Sync Checker")
    print("=" * 60)

    try:
        from src.sync_checker import SyncChecker

        checker = SyncChecker()
        status = checker.check_sync_status()

        print("✅ Sync check completed")
        print("\n📊 Results:")
        print(f"  Status: {'✅ In Sync' if status['in_sync'] else '⚠️  Out of Sync'}")
        print(f"  Scrivener chapters: {len(status['scrivener_chapters'])}")
        print(f"  Zotero chapters: {len(status['zotero_chapters'])}")
        print(f"  Outline chapters: {len(status['outline_chapters'])}")
        print(f"  Mismatches: {len(status['mismatches'])}")

        if status["mismatches"]:
            print("\n⚠️  Mismatches found:")
            for m in status["mismatches"][:3]:
                print(f"  - {m['message']}")

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_skill_execution():
    """Test that the check-sync skill can be executed."""
    print("\n" + "=" * 60)
    print("TEST 4: Check-Sync Skill")
    print("=" * 60)

    skill_path = Path(".claude/skills/check-sync/main.py")
    if not skill_path.exists():
        print("❌ Skill file not found")
        return False

    try:
        # Import and run the skill
        import importlib.util

        spec = importlib.util.spec_from_file_location("check_sync_skill", skill_path)
        skill_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(skill_module)

        print("✅ Skill can be imported and executed")
        print("\n📄 Running skill:")
        print("-" * 60)
        skill_module.main()
        print("-" * 60)

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n🧪 COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    load_env()

    results = {
        "Scrivener Parser": test_scrivener_parser(),
        "Context Loading": test_context_loading(),
        "Sync Checker": test_sync_checker(),
        "Check-Sync Skill": test_skill_execution(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {test_name}")

    passed_count = sum(results.values())
    total_count = len(results)

    print(f"\n🎯 {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
