"""Test Scrivener parser functionality."""

import os
from pathlib import Path

import pytest

from src.scrivener_parser import ScrivenerParser


@pytest.fixture
def scrivener_path():
    """Get Scrivener project path from environment."""
    path = os.getenv("SCRIVENER_PROJECT_PATH")
    if not path or not Path(path).exists():
        pytest.skip("SCRIVENER_PROJECT_PATH not configured or doesn't exist")
    return path


def test_parser_initialization(scrivener_path):
    """Test parser can be initialized."""
    parser = ScrivenerParser(scrivener_path)
    assert parser.scriv_path.exists()
    assert parser.scrivx_file.exists()


def test_get_chapter_structure(scrivener_path):
    """Test extracting chapter structure."""
    parser = ScrivenerParser(scrivener_path)
    structure = parser.get_chapter_structure()

    assert "project_name" in structure
    assert "structure" in structure
    assert "chapters" in structure
    assert isinstance(structure["chapters"], list)

    print(f"\n📚 Project: {structure['project_name']}")
    print(f"📖 Found {len(structure['chapters'])} chapters")

    for ch in structure["chapters"][:5]:  # Show first 5
        print(f"  Chapter {ch['number']}: {ch['title']}")


def test_format_structure_as_text(scrivener_path):
    """Test formatting structure as text."""
    parser = ScrivenerParser(scrivener_path)
    text = parser.format_structure_as_text()

    assert len(text) > 0
    assert "Chapter" in text

    print("\n📄 Formatted Structure:")
    print(text[:500])  # Show first 500 chars


def test_chapter_number_extraction(scrivener_path):
    """Test chapter number extraction from various formats."""
    parser = ScrivenerParser(scrivener_path)

    test_cases = [
        ("1. The Beginning", 1),
        ("Chapter 2: Middle", 2),
        ("Ch 3 - The End", 3),
        ("Ch. 4 Something", 4),
        ("5 — Another Chapter", 5),
        ("No Number Here", None),
    ]

    for title, expected in test_cases:
        result = parser._extract_chapter_number(title)
        print(f"  '{title}' -> {result}")
        if expected is not None:
            assert result == expected


if __name__ == "__main__":
    # Run tests manually
    path = os.getenv("SCRIVENER_PROJECT_PATH")
    if not path:
        print("❌ SCRIVENER_PROJECT_PATH not set in environment")
        exit(1)

    print("🧪 Testing Scrivener Parser\n")

    try:
        test_parser_initialization(path)
        print("✅ Parser initialization")

        test_get_chapter_structure(path)
        print("✅ Chapter structure extraction")

        test_format_structure_as_text(path)
        print("✅ Text formatting")

        test_chapter_number_extraction(path)
        print("✅ Chapter number extraction")

        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
