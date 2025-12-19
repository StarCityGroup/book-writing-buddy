"""Test sync checker functionality."""

import os

import pytest


@pytest.fixture
def sync_checker():
    """Create sync checker instance."""
    from src.sync_checker import SyncChecker

    return SyncChecker()


def test_sync_check(sync_checker):
    """Test checking sync status."""
    print("\n🧪 Testing Sync Checker\n")

    status = sync_checker.check_sync_status()

    print(f"📊 Sync Status: {'✅ In Sync' if status['in_sync'] else '⚠️ Out of Sync'}")
    print(f"\n📚 Chapter Counts:")
    print(f"  Scrivener: {len(status['scrivener_chapters'])}")
    print(f"  Zotero: {len(status['zotero_chapters'])}")
    print(f"  Outline: {len(status['outline_chapters'])}")

    if status["mismatches"]:
        print(f"\n⚠️  Found {len(status['mismatches'])} mismatches:")
        for m in status["mismatches"][:5]:  # Show first 5
            print(f"  - {m['message']}")

    if status["recommendations"]:
        print(f"\n💡 Recommendations:")
        for rec in status["recommendations"][:3]:  # Show first 3
            print(f"  - {rec}")

    return status


def test_sync_report_formatting(sync_checker):
    """Test formatting sync report."""
    print("\n🧪 Testing Report Formatting\n")

    status = sync_checker.check_sync_status()
    report = sync_checker.format_sync_report(status)

    print("📄 Generated Report:")
    print("=" * 60)
    print(report)
    print("=" * 60)

    assert len(report) > 0
    assert "Sync Status Report" in report


def test_outline_extraction(sync_checker):
    """Test extracting chapters from outline.txt."""
    print("\n🧪 Testing Outline Extraction\n")

    outline_chapters = sync_checker._extract_chapters_from_outline()

    print(f"📖 Found {len(outline_chapters)} chapters in outline.txt:")
    for num, title in list(outline_chapters.items())[:5]:  # Show first 5
        print(f"  Chapter {num}: {title}")

    return outline_chapters


if __name__ == "__main__":
    # Load environment
    from pathlib import Path

    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

    try:
        from src.sync_checker import SyncChecker

        checker = SyncChecker()

        test_sync_check(checker)
        print("✅ Sync check test passed!")

        test_sync_report_formatting(checker)
        print("✅ Report formatting test passed!")

        test_outline_extraction(checker)
        print("✅ Outline extraction test passed!")

        print("\n✅ All sync checker tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
