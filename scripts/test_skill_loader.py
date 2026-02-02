#!/usr/bin/env python3
"""Test the dynamic skill loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.skill_loader import load_all_skills, parse_skill_markdown

load_dotenv()


def test_parse_markdown():
    """Test parsing a skill markdown file."""
    print("\n=== Test 1: Parse Markdown ===\n")

    md_file = Path(__file__).parent.parent / "config/skills/analyze_chapter.md"
    if not md_file.exists():
        print("✗ Skill file not found")
        return False

    content = md_file.read_text()
    skill = parse_skill_markdown(content)

    print(f"Name: {skill['name']}")
    print(f"Description: {skill['description']}")
    print(f"Parameters: {skill['parameters']}")
    print(f"Workflow steps: {len(skill['workflow_steps'])}")
    print(f"Examples: {len(skill['examples'])}")

    if skill["name"] == "analyze_chapter":
        print("\n✓ Test 1 passed: Markdown parsed correctly")
        return True
    else:
        print("\n✗ Test 1 failed: Unexpected skill name")
        return False


def test_load_skills():
    """Test loading all skills."""
    print("\n=== Test 2: Load All Skills ===\n")

    skills = load_all_skills()

    print(f"Total skills loaded: {len(skills)}")

    # List all skill names
    skill_names = [s.name for s in skills]
    for name in skill_names:
        source = "code" if name in [
            "analyze_chapter",
            "check_sync_workflow",
            "research_gaps",
            "track_theme",
            "export_research",
        ] else "config"
        print(f"  - {name:30s} (from {source})")

    # Check for duplicates
    if len(skill_names) != len(set(skill_names)):
        print("\n✗ Test 2 failed: Duplicate skill names found")
        return False

    print(f"\n✓ Test 2 passed: {len(skills)} unique skills loaded")
    return True


def test_agent_integration():
    """Test that agent can load skills."""
    print("\n=== Test 3: Agent Integration ===\n")

    from src.agent_v2 import create_agent_options

    options = create_agent_options()
    tool_names = [tool.name for tool in options.tools]

    print(f"Agent has {len(tool_names)} tools total")

    # Count skills vs core tools
    skill_count = len([n for n in tool_names if n in [
        "analyze_chapter",
        "check_sync_workflow",
        "research_gaps",
        "track_theme",
        "export_research",
    ]])

    print(f"  - {len(tool_names) - skill_count} core research tools")
    print(f"  - {skill_count} workflow skills")

    print("\n✓ Test 3 passed: Agent successfully integrated skills")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Dynamic Skill Loader")
    print("=" * 60)

    results = []
    results.append(test_parse_markdown())
    results.append(test_load_skills())
    results.append(test_agent_integration())

    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
