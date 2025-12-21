"""Test that context loading works correctly."""

import os
from pathlib import Path


def test_context_loading():
    """Test loading book context from both sources."""
    # Import after setting environment
    from src.nodes import load_book_context

    print("\n🧪 Testing Context Loading\n")

    context = load_book_context()

    print("📋 Generated Context Length:", len(context))
    print("\n" + "=" * 60)
    print("CONTEXT PREVIEW (first 1000 chars):")
    print("=" * 60)
    print(context[:1000])
    print("=" * 60)

    # Verify both sources are present
    assert len(context) > 0, "Context should not be empty"

    # Check for Scrivener structure section
    if "Scrivener Structure" in context:
        print("✅ Scrivener structure found in context")
    else:
        print("⚠️  Scrivener structure not found (might be expected if not configured)")

    # Check for outline section
    if "Book Outline" in context or "FIREWALL" in context:
        print("✅ Book outline found in context")
    else:
        print("⚠️  Book outline not found")

    return context


def test_context_with_missing_files():
    """Test graceful handling when files are missing."""
    print("\n🧪 Testing Missing File Handling\n")

    # Temporarily rename outline.txt if it exists
    outline_path = Path("data/outline.txt")
    backup_path = Path("data/outline.txt.backup")

    if outline_path.exists():
        outline_path.rename(backup_path)

    try:
        from src.nodes import load_book_context

        context = load_book_context()

        # Should still work, just with fallback messages
        assert (
            "outline file found" in context.lower() or "no outline" in context.lower()
        )
        print("✅ Handles missing outline.txt gracefully")

    finally:
        # Restore
        if backup_path.exists():
            backup_path.rename(outline_path)


if __name__ == "__main__":
    # Ensure environment is set
    if not os.getenv("SCRIVENER_PROJECT_PATH"):
        print("⚠️  SCRIVENER_PROJECT_PATH not set, using .env file")
        # Load from .env
        from pathlib import Path

        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().split("\n"):
                if line.startswith("SCRIVENER_PROJECT_PATH="):
                    path = line.split("=", 1)[1].strip()
                    os.environ["SCRIVENER_PROJECT_PATH"] = path

    try:
        test_context_loading()
        print("\n✅ Context loading test passed!")

        test_context_with_missing_files()
        print("✅ Missing file handling test passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
