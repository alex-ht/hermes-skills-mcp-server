# Hermes Skills MCP Server

A standalone Python MCP server that exposes the core Hermes skill tools (`skills_list`, `skill_view`, `skill_manage`) over the Model Context Protocol.

This allows **any MCP-compatible agent** (OpenClaw, Hermes, Claude Desktop, Cursor, LM Studio, etc.) to discover, read, and manage skills that follow the standard `SKILL.md` format used by Hermes.

## Why This Exists

- Hermes has a powerful self-improving "skills" system (reusable procedures stored as `SKILL.md` files).
- Other agents (especially OpenClaw) benefit from accessing the same skill library.
- This server provides a clean, secure, MCP-native interface to that system without requiring a full Hermes installation.

## Features

- `skills_list` — Lightweight discovery (progressive disclosure)
- `skill_view(name, file_path?)` — Read full `SKILL.md` or any supporting file (`references/`, `templates/`, etc.)
- `skill_manage` — Create new skills (more actions planned)
- Strict path safety (no traversal outside the skills root)
- YAML frontmatter parsing
- Compatible with the official agentskills.io / Hermes skill format
- Easy to register in OpenClaw and Hermes

## Installation & Running

```bash
# Clone and enter the project
cd hermes-skills-mcp-server

# Install with uv (recommended)
uv sync

# Run directly
uv run python -m hermes_skills_mcp_server.server

# Or after installing the package
uv pip install -e .
hermes-skills-mcp
```

The server uses **stdio** transport by default (ideal for local agent integration).

### Configure Skills Location

```bash
export SKILLS_ROOT=/path/to/your/skills
# or pass via command line when supported by your MCP client
```

Default: `~/.hermes/skills`

## Registering with OpenClaw (Recommended for OpenClaw Users)

```bash
# Persistent registration (preferred)
openclaw mcp set hermes-skills '{
  "command": "uv",
  "args": [
    "--directory", "/absolute/path/to/hermes-skills-mcp-server",
    "run", "python", "-m", "hermes_skills_mcp_server.server"
  ]
}'

# Verify
openclaw mcp list
openclaw mcp show hermes-skills
```

For quick testing inside a chat you can also use the slash command, but `openclaw mcp set` is more reliable across sessions.

## Registering with Hermes

```bash
hermes mcp add hermes-skills --command 'uv --directory /path/to/hermes-skills-mcp-server run python -m hermes_skills_mcp_server.server'
```

## Tool Reference (What Agents See)

### skills_list
List available skills with metadata only.

### skill_view
The main "skill-info" tool. Load complete content:

```json
{
  "name": "hermes-agent",
  "file_path": "references/some-doc.md"   // optional
}
```

### skill_manage
Currently supports `create`. More management actions will be added.

## Example Skill Structure

```
~/.hermes/skills/
├── hermes-agent/
│   ├── SKILL.md
│   └── references/
│       └── prompt-builder-environment-hints.md
├── mlops/
│   └── axolotl/
│       ├── SKILL.md
│       └── templates/
│           └── training-script.py
```

## Development & Testing

```bash
# Run the server
uv run python -m hermes_skills_mcp_server.server

# In another terminal, you can test with the official MCP tools or by connecting from an agent.
```

A sample skill is included under `examples/sample-skill/` for quick testing.

## Requirements & Handoff

See `REQUIREMENTS.md` for the full software development requirements document. This document is written in a style optimized for handoff to autonomous coding agents (Grok Build, Claude, etc.).

## License

MIT (aligned with Hermes Agent)

## Related Projects

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- OpenClaw / ClawHub ecosystem
- agentskills.io format
