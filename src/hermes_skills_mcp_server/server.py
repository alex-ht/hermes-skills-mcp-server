#!/usr/bin/env python3
"""
Hermes Skills MCP Server

Exposes Hermes-compatible skill tools (skills_list, skill_view, skill_manage)
over the Model Context Protocol (MCP) using FastMCP.

This server allows other agent environments (OpenClaw, Hermes, Claude Desktop,
Cursor, etc.) to discover, inspect, and manage skills that follow the standard
SKILL.md + frontmatter format.

Designed for interoperability with the agentskills.io / Hermes skill ecosystem.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_SKILLS_ROOT = Path.home() / ".hermes" / "skills"

def get_skills_root() -> Path:
    """Resolve the configured skills root directory."""
    env_root = os.environ.get("SKILLS_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return DEFAULT_SKILLS_ROOT.resolve()

def ensure_root_exists(root: Path) -> None:
    """Create the skills root if it does not exist."""
    root.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Core Skill Utilities (safe, minimal reimplementation of Hermes semantics)
# =============================================================================

def _is_safe_relative_path(candidate: str) -> bool:
    """Prevent path traversal attacks."""
    p = Path(candidate)
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    return True

def _find_all_skills(root: Path) -> List[Dict[str, Any]]:
    """Discover all skills under the root (progressive disclosure - metadata only)."""
    skills: List[Dict[str, Any]] = []
    if not root.exists():
        return skills

    for skill_md in root.rglob("SKILL.md"):
        try:
            rel_dir = skill_md.parent.relative_to(root)
            skill_name = str(rel_dir) if str(rel_dir) != "." else skill_md.parent.name

            # Quick metadata extraction (do not load full body here)
            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            frontmatter: Dict[str, Any] = {}
            if content.startswith("---"):
                try:
                    _, fm, _ = content.split("---", 2)
                    frontmatter = yaml.safe_load(fm) or {}
                except Exception:
                    pass

            skills.append({
                "name": frontmatter.get("name", skill_name),
                "description": frontmatter.get("description", ""),
                "relative_path": str(rel_dir),
                "version": frontmatter.get("version"),
                "platforms": frontmatter.get("platforms"),
                "category": str(rel_dir.parent) if len(rel_dir.parts) > 1 else None,
            })
        except Exception:
            # Skip malformed skills gracefully
            continue

    # Sort for deterministic output
    skills.sort(key=lambda s: s["name"].lower())
    return skills

def _load_skill_document(root: Path, name: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a skill's main SKILL.md or a supporting file.
    Returns structured data suitable for agent consumption.
    """
    if not _is_safe_relative_path(name):
        return {"success": False, "error": "Invalid skill name (path traversal or absolute path detected)"}

    skill_dir = (root / name).resolve()
    if not skill_dir.is_relative_to(root.resolve()):
        return {"success": False, "error": "Skill path escapes the configured skills root"}

    if not skill_dir.exists():
        return {"success": False, "error": f"Skill not found: {name}"}

    target_file = skill_dir / "SKILL.md"
    if file_path:
        if not _is_safe_relative_path(file_path):
            return {"success": False, "error": "Invalid sub-path (path traversal detected)"}
        target_file = (skill_dir / file_path).resolve()
        if not target_file.is_relative_to(skill_dir):
            return {"success": False, "error": "Sub-path escapes the skill directory"}

    if not target_file.exists():
        return {"success": False, "error": f"File not found: {target_file.relative_to(root)}"}

    try:
        raw_content = target_file.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to read file: {str(e)}"}

    result: Dict[str, Any] = {
        "success": True,
        "skill_name": name,
        "file": str(target_file.relative_to(root)),
        "raw_content": raw_content,
    }

    # If this is the main SKILL.md, also provide parsed frontmatter + body
    if target_file.name == "SKILL.md":
        frontmatter: Dict[str, Any] = {}
        body = raw_content
        if raw_content.strip().startswith("---"):
            try:
                parts = raw_content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].lstrip("\n")
            except Exception:
                pass

        result["frontmatter"] = frontmatter
        result["body"] = body
        result["description"] = frontmatter.get("description", "")

    return result

def _create_skill(root: Path, name: str, frontmatter: Dict[str, Any], body: str) -> Dict[str, Any]:
    """Create a new skill directory + SKILL.md."""
    if not _is_safe_relative_path(name):
        return {"success": False, "error": "Invalid skill name"}

    skill_dir = root / name
    if skill_dir.exists():
        return {"success": False, "error": f"Skill already exists: {name}"}

    skill_dir.mkdir(parents=True, exist_ok=True)

    fm_text = "---\n" + yaml.safe_dump(frontmatter or {}, sort_keys=False, allow_unicode=True) + "---\n\n"
    content = fm_text + (body or "# New Skill\n\nDescribe your skill here.\n")

    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    return {
        "success": True,
        "action": "create",
        "skill_name": name,
        "path": str(skill_dir.relative_to(root)),
        "message": "Skill created successfully",
    }

# =============================================================================
# MCP Server Definition
# =============================================================================

mcp = FastMCP("Hermes Skills")

@mcp.tool()
def skills_list(category: Optional[str] = None) -> str:
    """
    List all available skills with lightweight metadata (progressive disclosure).

    Use this first to discover skills. Then call skill_view for full content.

    Returns a JSON string with the list of skills.
    """
    root = get_skills_root()
    ensure_root_exists(root)

    skills = _find_all_skills(root)

    if category:
        skills = [s for s in skills if s.get("category") == category or category in (s.get("name", "") + s.get("description", ""))]

    return json.dumps({
        "success": True,
        "skills_root": str(root),
        "count": len(skills),
        "skills": skills
    }, indent=2, ensure_ascii=False)

@mcp.tool()
def skill_view(name: str, file_path: Optional[str] = None) -> str:
    """
    View the full content of a skill (or a supporting file inside it).

    This is the primary "skill-info" tool.

    Args:
        name: Skill identifier (directory name, e.g. "hermes-agent" or "mlops/axolotl")
        file_path: Optional sub-path inside the skill (e.g. "references/api.md")

    Returns the parsed frontmatter + body (for SKILL.md) or raw content for other files.
    """
    root = get_skills_root()
    ensure_root_exists(root)

    result = _load_skill_document(root, name, file_path)
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
def skill_manage(
    action: str,
    name: str,
    frontmatter: Optional[Dict[str, Any]] = None,
    body: Optional[str] = None,
) -> str:
    """
    Create, update or manage skills.

    Supported actions (initial implementation):
      - "create": Create a new skill (requires frontmatter and body)
      - "patch": Placeholder for future updates (currently returns not implemented)

    This is the "skill management" tool for authoring and maintenance.
    """
    root = get_skills_root()
    ensure_root_exists(root)

    action = action.lower().strip()

    if action == "create":
        if not frontmatter or not body:
            return json.dumps({
                "success": False,
                "error": "create action requires both 'frontmatter' (dict) and 'body' (string)"
            })
        result = _create_skill(root, name, frontmatter, body)
        return json.dumps(result, indent=2, ensure_ascii=False)

    elif action in ("patch", "update", "delete", "archive"):
        return json.dumps({
            "success": False,
            "error": f"Action '{action}' is not yet implemented in this version. "
                     f"Only 'create' is supported in the initial release. "
                     f"See REQUIREMENTS.md for planned functionality."
        })

    else:
        return json.dumps({
            "success": False,
            "error": f"Unknown action: {action}. Supported: create"
        })

# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server (stdio transport by default)."""
    print("Starting Hermes Skills MCP Server...", flush=True)
    print(f"Skills root: {get_skills_root()}", flush=True)
    mcp.run()

if __name__ == "__main__":
    main()
