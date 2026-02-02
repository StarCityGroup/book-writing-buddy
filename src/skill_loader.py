"""Dynamic skill loader that reads workflow definitions from markdown files.

This module discovers skill definitions in config/skills/*.md and converts
them into Claude Agent SDK tools that can be used by the agent.
"""

import json
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool


def parse_skill_markdown(content: str) -> dict[str, Any]:
    """Parse a skill definition from markdown format.

    Expected format:
        # Skill Name

        **Name:** `skill_name`
        **Description:** Brief description
        **Parameters:**
        - param_name (type, required/optional): Description
        **Workflow Steps:**
        1. Step one
        2. Step two

    Args:
        content: Markdown content of skill file

    Returns:
        Dict with keys: name, description, parameters, workflow_steps, examples
    """
    lines = content.split("\n")

    result = {
        "name": "",
        "description": "",
        "parameters": {},
        "workflow_steps": [],
        "examples": [],
    }

    # Parse name (from **Name:** line)
    name_match = re.search(r"\*\*Name:\*\*\s*`([^`]+)`", content)
    if name_match:
        result["name"] = name_match.group(1)

    # Parse description (from **Description:** line)
    desc_match = re.search(r"\*\*Description:\*\*\s*(.+?)(?:\n\n|\*\*)", content, re.DOTALL)
    if desc_match:
        result["description"] = desc_match.group(1).strip()

    # Parse parameters
    param_section = re.search(
        r"\*\*Parameters:\*\*\s*\n(.*?)(?:\n\n|\*\*)", content, re.DOTALL
    )
    if param_section:
        param_text = param_section.group(1)
        # Parse each parameter line: - param_name (type, required): Description
        for line in param_text.split("\n"):
            param_match = re.match(
                r"^-\s+`?(\w+)`?\s*\(([^,]+)(?:,\s*(required|optional))?\):\s*(.+)$",
                line.strip(),
            )
            if param_match:
                param_name = param_match.group(1)
                param_type = param_match.group(2).strip()
                # param_required = param_match.group(3) == "required"
                # param_desc = param_match.group(4)

                # Convert type string to Python type
                type_map = {"int": int, "str": str, "bool": bool, "float": float}
                result["parameters"][param_name] = type_map.get(param_type, str)

    # Parse workflow steps
    workflow_match = re.search(
        r"\*\*Workflow Steps:\*\*\s*\n(.*?)(?:\n\n|\*\*Example|$)", content, re.DOTALL
    )
    if workflow_match:
        workflow_text = workflow_match.group(1)
        for line in workflow_text.split("\n"):
            # Match numbered steps: 1. Step description
            step_match = re.match(r"^\d+\.\s+(.+)$", line.strip())
            if step_match:
                result["workflow_steps"].append(step_match.group(1))

    # Parse examples
    example_match = re.search(r"\*\*Example Usage:\*\*\s*\n(.*?)$", content, re.DOTALL)
    if example_match:
        example_text = example_match.group(1)
        for line in example_text.split("\n"):
            # Match bullet points: - "Example query"
            if line.strip().startswith("-"):
                example = line.strip()[1:].strip().strip('"')
                if example:
                    result["examples"].append(example)

    return result


def create_skill_tool(skill_def: dict[str, Any]):
    """Create a Claude Agent SDK tool from a skill definition.

    Args:
        skill_def: Parsed skill definition dict

    Returns:
        Tool function decorated with @tool
    """
    name = skill_def["name"]
    description = skill_def["description"]
    parameters = skill_def["parameters"]
    workflow_steps = skill_def["workflow_steps"]

    @tool(name, description, parameters)
    async def skill_function(args: dict[str, Any]) -> dict[str, Any]:
        """Dynamically created skill function."""
        # Build guidance message
        guidance = {
            "workflow": name,
            "parameters": args,
            "next_steps": workflow_steps,
        }

        return {
            "content": [
                {"type": "text", "text": json.dumps(guidance, indent=2)}
            ]
        }

    return skill_function


def load_skills_from_directory(skills_dir: Path) -> list:
    """Load all skill definitions from markdown files in a directory.

    Args:
        skills_dir: Path to directory containing skill .md files

    Returns:
        List of tool functions
    """
    if not skills_dir.exists():
        return []

    skills = []

    for md_file in skills_dir.glob("*.md"):
        try:
            content = md_file.read_text()
            skill_def = parse_skill_markdown(content)

            if skill_def["name"]:
                skill_tool = create_skill_tool(skill_def)
                skills.append(skill_tool)
        except Exception as e:
            # Log but don't fail on individual skill errors
            print(f"Warning: Failed to load skill from {md_file}: {e}")

    return skills


def load_all_skills() -> list:
    """Load skills from config directory, with code fallback.

    Priority:
    1. Load markdown skills from config/skills/*.md
    2. If no markdown skills found, load from code (workflows.py)

    Returns:
        List of all skill tools
    """
    # Get config skills directory
    config_dir = Path(__file__).parent.parent / "config" / "skills"
    config_skills = load_skills_from_directory(config_dir)

    # If we found markdown skills, use those exclusively
    if config_skills:
        return config_skills

    # Otherwise, fall back to code-defined skills
    from .workflows import ALL_SKILLS as CODE_SKILLS

    return CODE_SKILLS
