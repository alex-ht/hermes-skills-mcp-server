#!/usr/bin/env python3
"""
Agent Skills MCP Server (SKILL.md format)

A standalone MCP server that exposes skills_list, skill_view, and skill_manage
tools using the standard SKILL.md + YAML frontmatter format.

This is designed to work in **pure OpenClaw environments** (no Hermes Agent
required at all), as well as mixed environments.

The server lets the agent programmatically:
- List available skills (lightweight metadata)
- View full skill content (equivalent to "skills info" / skill-info)
- Manage (create/update) skills

**Key feature for context control**: All tools accept an optional `cwd` parameter.
When provided, it is used as the base directory for discovering project-local
skills (e.g. <cwd>/skills or <cwd>/.agents/skills). This allows the calling
agent to explicitly specify the intended workspace on every tool call,
independent of the MCP server's process working directory.

Skills can live in OpenClaw workspace locations, a dedicated directory,
or anywhere you point via SKILLS_ROOT.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Configuration - OpenClaw friendly by default
# =============================================================================

def _get_openclaw_workspace() -> Optional[Path]:
    """Try to discover OpenClaw's active workspace from its config."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if not config_path.exists():
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        ws = cfg.get("agents", {}).get("defaults", {}).get("workspace")
        if ws:
            p = Path(ws).expanduser().resolve()
            if p.is_dir():
                return p
    except Exception:
        pass
    # Common default
    default = Path.home() / ".openclaw" / "workspace"
    if default.is_dir():
        return default.resolve()
    return None

def get_skills_root(cwd: Optional[str] = None) -> Path:
    """
    Resolve the skills directory with strong support for pure OpenClaw usage.

    Priority (highest first):
    1. SKILLS_ROOT environment variable (recommended for explicit control)
    2. Local skills folders relative to the provided (or real) `cwd` (project-specific)
    3. OpenClaw workspace skills: <workspace>/skills or <workspace>/.agents/skills
    4. Global OpenClaw-friendly locations (~/.openclaw/skills)
    5. Fallback: ~/.agent-skills (neutral, no Hermes required)

    Args:
        cwd: Optional base directory to use for layer #2 (local project skills).
             If omitted, falls back to the server's real process cwd.
             This parameter is exposed on every tool so the calling agent
             can explicitly control context per call.
    """
    # 1. Explicit override (always wins)
    if env_root := os.environ.get("SKILLS_ROOT"):
        root = Path(env_root).expanduser().resolve()
        ensure_root_exists(root)
        return root

    # Determine base for local project skills detection
    if cwd:
        base_cwd = Path(cwd).expanduser().resolve()
    else:
        base_cwd = Path.cwd().resolve()

    # 2. Local skills next to the (provided or real) base cwd (very useful in OpenClaw)
    for local in [
        base_cwd / "skills",
        base_cwd / ".skills",
        base_cwd / ".agents/skills",
        base_cwd / "agent-skills",
    ]:
        if local.is_dir():
            return local.resolve()

    # 3. OpenClaw workspace skills (primary for pure OpenClaw users)
    oc_ws = _get_openclaw_workspace()
    if oc_ws:
        for candidate in [
            oc_ws / "skills",
            oc_ws / ".agents/skills",
            oc_ws / "agent-skills",
        ]:
            if candidate.is_dir():
                return candidate.resolve()

    # 4. Dedicated global OpenClaw skills location (recommended convention)
    openclaw_global = Path.home() / ".openclaw" / "skills"
    if openclaw_global.is_dir():
        return openclaw_global.resolve()

    # 5. Neutral fallback (no Hermes dependency)
    neutral = Path.home() / ".agent-skills"
    ensure_root_exists(neutral)
    return neutral.resolve()

def ensure_root_exists(root: Path) -> None:
    """Create the skills root if it does not exist."""
    root.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Core Skill Utilities (format-compatible with Hermes / agentskills.io)
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
            dir_name = str(rel_dir) if str(rel_dir) != "." else skill_md.parent.name

            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            frontmatter: Dict[str, Any] = {}
            if content.startswith("---"):
                try:
                    _, fm, _ = content.split("---", 2)
                    frontmatter = yaml.safe_load(fm) or {}
                except Exception:
                    pass

            skills.append({
                "name": frontmatter.get("name", dir_name),
                "directory": dir_name,   # reliable lookup key
                "description": frontmatter.get("description", ""),
                "relative_path": dir_name,
                "version": frontmatter.get("version"),
                "platforms": frontmatter.get("platforms"),
                "category": str(rel_dir.parent) if len(rel_dir.parts) > 1 else None,
            })
        except Exception:
            continue

    skills.sort(key=lambda s: s["name"].lower())
    return skills

def _load_skill_document(root: Path, name: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Load a skill's main SKILL.md or a supporting file.
    
    'name' can be either the frontmatter name or (preferably) the directory name.
    """
    if not _is_safe_relative_path(name):
        return {"success": False, "error": "Invalid skill name (path traversal or absolute path detected)"}

    skill_dir = (root / name).resolve()
    root_resolved = root.resolve()
    if not skill_dir.is_relative_to(root_resolved):
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

mcp = FastMCP("Agent Skills")

@mcp.tool()
def skills_list(category: Optional[str] = None, cwd: Optional[str] = None) -> str:
    """
    List all available skills with lightweight metadata (progressive disclosure).

    This is the equivalent of "skills list". Use this first, then call skill_view
    to get full content.

    Returns JSON with the list of skills + the resolved skills_root.

    Args:
        category: Optional filter (matches name or description).
        cwd: Optional base directory for resolving project-local skills
             (e.g. pass your workspace or project root). If omitted, the server
             performs full auto-detection (OpenClaw config + real cwd).
    """
    root = get_skills_root(cwd)
    ensure_root_exists(root)

    skills = _find_all_skills(root)

    if category:
        skills = [s for s in skills if category.lower() in (s.get("name", "") + " " + s.get("description", "")).lower()]

    return json.dumps({
        "success": True,
        "skills_root": str(root),
        "count": len(skills),
        "skills": skills
    }, indent=2, ensure_ascii=False)

@mcp.tool()
def skill_view(name: str, file_path: Optional[str] = None, cwd: Optional[str] = None) -> str:
    """
    View the full content of a skill or a supporting file inside it.

    This is the primary "skill-info" tool (equivalent to skills info / reading SKILL.md).

    'name' can be the directory name (recommended) or the name declared in frontmatter.

    Args:
        name: Skill directory name (e.g. "skill-creator" or "self-improving")
        file_path: Optional sub-file, e.g. "references/example.md"
        cwd: Optional base directory for resolving project-local skills.
             Pass this to force a specific workspace context for this call.
    """
    root = get_skills_root(cwd)
    ensure_root_exists(root)

    result = _load_skill_document(root, name, file_path)
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
def skill_manage(
    action: str,
    name: str,
    frontmatter: Optional[Dict[str, Any]] = None,
    body: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    """
    Create or manage skills.

    Currently supported:
    - "create": Create a new skill (provide frontmatter dict and body string)

    This gives the agent the ability to author new skills directly.

    Args:
        action: "create" (more actions coming)
        name: Skill directory name
        frontmatter: dict for the YAML frontmatter section
        body: Markdown body content
        cwd: Optional base directory for resolving project-local skills.
             Pass this to force a specific workspace context for this call.
    """
    root = get_skills_root(cwd)
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

    return json.dumps({
        "success": False,
        "error": f"Action '{action}' not implemented yet. Only 'create' is supported in current version."
    })

# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    root = get_skills_root()
    print(f"Agent Skills MCP Server starting...", flush=True)
    print(f"Using skills root: {root}", flush=True)
    mcp.run()

if __name__ == "__main__":
    main()
