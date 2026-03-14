"""Dynamic skill loader that reads workflow definitions from markdown files.

This module discovers skill definitions in config/skills/*.md and converts
them into Claude Agent SDK tools that can be used by the agent.
"""

import json
import re
from pathlib import Path
from typing import Any

import structlog
from claude_agent_sdk import tool

logger = structlog.get_logger()


def parse_skill_markdown(content: str) -> dict[str, Any] | None:
    """Parse a skill definition from markdown format.

    Expected format:
        # Skill Name

        **Name:** `skill_name`
        **Description:** Brief description
        **Parameters:**
        - param_name (type, required/optional): Description. Default: value
        **Workflow Steps:**
        1. Step one
        2. Step two

    Args:
        content: Markdown content of skill file

    Returns:
        Dict with keys: name, description, parameters, workflow_steps, examples
        Returns None if the content is not a valid skill definition.
    """
    result = {
        "name": "",
        "description": "",
        "parameters": {},
        "optional_parameters": {},
        "workflow_steps": [],
        "examples": [],
        "conditions": [],
    }

    # Parse name (from **Name:** line)
    name_match = re.search(r"\*\*Name:\*\*\s*`([^`]+)`", content)
    if not name_match:
        return None
    result["name"] = name_match.group(1)

    # Parse description (from **Description:** line)
    desc_match = re.search(
        r"\*\*Description:\*\*\s*(.+?)(?:\n\n|\*\*)", content, re.DOTALL
    )
    if desc_match:
        result["description"] = desc_match.group(1).strip()

    # Parse parameters (handles "None" keyword)
    param_section = re.search(
        r"\*\*Parameters:\*\*\s*\n(.*?)(?:\n\n|\*\*)", content, re.DOTALL
    )
    if param_section:
        param_text = param_section.group(1).strip()
        if param_text.lower() != "none":
            for line in param_text.split("\n"):
                param_match = re.match(
                    r"^-\s+`?(\w+)`?\s*\(([^,]+)(?:,\s*(required|optional))?\):\s*(.+)$",
                    line.strip(),
                )
                if param_match:
                    param_name = param_match.group(1)
                    param_type = param_match.group(2).strip()
                    param_required = param_match.group(3) != "optional"
                    param_desc = param_match.group(4).strip()

                    type_map = {
                        "int": int,
                        "str": str,
                        "bool": bool,
                        "float": float,
                    }
                    py_type = type_map.get(param_type, str)

                    if param_required:
                        result["parameters"][param_name] = py_type
                    else:
                        default_match = re.search(
                            r"Default:\s*(.+?)\.?$", param_desc
                        )
                        result["optional_parameters"][param_name] = {
                            "type": py_type,
                            "default": (
                                default_match.group(1).strip()
                                if default_match
                                else None
                            ),
                        }

    # Parse workflow steps (supports conditional sub-steps)
    workflow_match = re.search(
        r"\*\*Workflow Steps:\*\*\s*\n(.*?)(?:\n\*\*Example|$)", content, re.DOTALL
    )
    if workflow_match:
        workflow_text = workflow_match.group(1)
        for line in workflow_text.split("\n"):
            step_match = re.match(r"^\d+\.\s+(.+)$", line.strip())
            if step_match:
                result["workflow_steps"].append(step_match.group(1))
            cond_match = re.match(r"^\s+-\s+If\s+(.+)$", line.strip())
            if cond_match:
                result["conditions"].append(cond_match.group(1))

    # Parse examples
    example_match = re.search(
        r"\*\*Example Usage:\*\*\s*\n(.*?)$", content, re.DOTALL
    )
    if example_match:
        example_text = example_match.group(1)
        for line in example_text.split("\n"):
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
    # Combine required and optional parameters for the tool schema
    all_params = dict(skill_def["parameters"])
    for param_name, param_info in skill_def.get("optional_parameters", {}).items():
        all_params[param_name] = param_info["type"]
    workflow_steps = skill_def["workflow_steps"]
    conditions = skill_def.get("conditions", [])

    @tool(name, description, all_params)
    async def skill_function(args: dict[str, Any]) -> dict[str, Any]:
        """Dynamically created skill function."""
        # Apply defaults for missing optional parameters
        for pname, pinfo in skill_def.get("optional_parameters", {}).items():
            if pname not in args and pinfo.get("default") is not None:
                args[pname] = pinfo["default"]

        guidance = {
            "workflow": name,
            "parameters": args,
            "next_steps": workflow_steps,
        }
        if conditions:
            guidance["conditions"] = conditions

        return {
            "content": [
                {"type": "text", "text": json.dumps(guidance, indent=2)}
            ]
        }

    return skill_function


def load_skills_from_directory(skills_dir: Path) -> list:
    """Load all skill definitions from markdown files in a directory.

    Skips README.md and any files that don't parse as valid skill definitions.

    Args:
        skills_dir: Path to directory containing skill .md files

    Returns:
        List of tool functions
    """
    if not skills_dir.exists():
        return []

    skills = []

    for md_file in sorted(skills_dir.glob("*.md")):
        if md_file.name.lower() == "readme.md":
            continue

        try:
            content = md_file.read_text()
            skill_def = parse_skill_markdown(content)

            if skill_def is None:
                logger.debug("Skipping non-skill file", file=md_file.name)
                continue

            skill_tool = create_skill_tool(skill_def)
            skills.append(skill_tool)
            logger.debug("Loaded skill", name=skill_def["name"], file=md_file.name)
        except Exception as e:
            logger.warning(
                "Failed to load skill", file=md_file.name, error=str(e)
            )

    return skills


def load_all_skills() -> list:
    """Load skills from markdown definitions in config/skills/.

    Returns:
        List of all skill tools
    """
    config_dir = Path(__file__).parent.parent / "config" / "skills"
    config_skills = load_skills_from_directory(config_dir)

    if not config_skills:
        logger.warning("No workflow skills found in config/skills/")

    return config_skills
