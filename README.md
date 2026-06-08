# Agent Skills MCP Server

A **standalone** MCP server that gives agents the ability to list, inspect, and manage skills using the standard `SKILL.md` format (with YAML frontmatter).

**Key feature**: Works perfectly in **pure OpenClaw environments** with **zero Hermes Agent dependency**.

All tools (`skills_list`, `skill_view`, `skill_manage`) now accept an optional `cwd` parameter so the calling agent can explicitly specify the workspace context on every call.

## Why This Exists

OpenClaw (and similar agents) have powerful built-in skills management via CLI (`openclaw skills list`, `skills info`, etc.). However, for the *agent itself* to programmatically discover and read skills during reasoning (progressive disclosure, on-demand loading of full `SKILL.md`), you need MCP tools.

This server exposes exactly three tools that agents love to use:
- `skills_list` — lightweight discovery
- `skill_view` — the main "skill-info" tool (read full `SKILL.md` or supporting files)
- `skill_manage` — create new skills (more actions planned)

The format is compatible with the agentskills.io / Hermes SKILL.md convention, so skills are portable.

## Pure OpenClaw Setup (No Hermes Needed)

This is the primary intended use case.

### Recommended Skill Locations for OpenClaw Users

1. **Workspace skills** (best for most people):
   - `~/.openclaw/workspace/skills/`

2. **Global / shared skills**:
   - `~/.openclaw/skills/`

3. **Project-specific** (inside your current workspace):
   - `./skills/`
   - `./.agents/skills/`

The server will **automatically detect** these locations (see below).

### Registration (OpenClaw)

```bash
# Simplest - let it auto-detect your OpenClaw workspace/skills
openclaw mcp set agent-skills '{
  "command": "uv",
  "args": [
    "--directory", "/absolute/path/to/this-repo",
    "run", "python", "-m", "hermes_skills_mcp_server.server"
  ]
}'

# Verify
openclaw mcp list
openclaw mcp show agent-skills
```

**Explicit control** (recommended if you have a preferred location):

```bash
openclaw mcp set agent-skills '{
  "command": "uv",
  "args": ["--directory", "/path/to/repo", "run", "python", "-m", "hermes_skills_mcp_server.server"],
  "env": {
    "SKILLS_ROOT": "/home/alex/.openclaw/workspace/skills"
  }
}'
```

## How Auto-Detection Works (OpenClaw)

**Important**: The workspace directory is **not** a single fixed default value. It is dynamically resolved with the following priority (no Hermes paths involved):

1. `SKILLS_ROOT` environment variable (highest priority)
2. Local folders next to the **provided `cwd`** (or real process cwd if `cwd` omitted): `skills/`, `.skills/`, `.agents/skills/`, `agent-skills/`
3. OpenClaw workspace skills (`<workspace>/skills`, `<workspace>/.agents/skills`) — read from `~/.openclaw/openclaw.json` (`agents.defaults.workspace`) or the common default `~/.openclaw/workspace`
4. `~/.openclaw/skills/`
5. Fallback: `~/.agent-skills/` (neutral directory)

This means in a typical pure OpenClaw session, it will usually just find `~/.openclaw/workspace/skills/` automatically.

## Explicit Workspace Context via the `cwd` Parameter (Recommended for Agents)

To give the calling agent precise control (independent of the MCP server's process working directory), all three tools accept an optional `cwd` parameter:

```json
// List skills in a specific workspace
skills_list(cwd="/home/alex/.openclaw/workspace")

// View a skill using explicit context
skill_view(name="proactivity", cwd="/home/alex/.openclaw/workspace")

// Create a skill in a project-specific location
skill_manage(action="create", name="my-new-skill", frontmatter={...}, body="...", cwd="/path/to/current/project")
```

- If `cwd` is provided, it becomes the base for the "local project skills" detection layer (#2 above).
- Passing the workspace root (e.g. `~/.openclaw/workspace`) will reliably pick up `<workspace>/skills`.
- If omitted, the server falls back to full auto-detection (including the real process `cwd` and OpenClaw config).
- The tool response always includes the final resolved `"skills_root"` so you can see what was used.

This design is ideal for agents: the LLM can decide "for this task I want skills from this workspace" and pass the `cwd` explicitly on the tool call.

## Running & Testing

```bash
cd hermes-skills-mcp-server
uv sync

# Run it
uv run python -m hermes_skills_mcp_server.server
```

Once connected in OpenClaw, the agent can call:
- `skills_list()`
- `skills_list(cwd="/home/alex/.openclaw/workspace")`
- `skill_view(name="skill-creator")`
- `skill_view(name="self-improving", cwd="/home/alex/.openclaw/workspace", file_path="...")`
- `skill_manage(action="create", ...)`

## Creating New Skills

Skills are just directories containing a `SKILL.md` file.

Example structure:
```
~/.openclaw/workspace/skills/
├── my-custom-skill/
│   ├── SKILL.md
│   └── references/
│       └── usage-notes.md
```

The `SKILL.md` starts with YAML frontmatter:

```markdown
---
name: my-custom-skill
description: Does something useful for my workflow.
version: 1.0.0
---

# My Custom Skill

Detailed instructions here...
```

## Project Status

This is a working, minimal but functional implementation.

See `REQUIREMENTS.md` for the full specification (written for handoff to coding agents like Grok).

## Future Improvements

- Full CRUD in `skill_manage` (patch, delete, archive)
- Better integration with OpenClaw's native `skills install` flow
- Optional global vs workspace skill separation
- More sophisticated workspace inference from cwd (e.g. walking up to find .openclaw markers)

## License

MIT

Repo: https://github.com/alex-ht/hermes-skills-mcp-server
