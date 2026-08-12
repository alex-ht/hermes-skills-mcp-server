# Agent Skills MCP Server

A **standalone** MCP server that gives agents the ability to list, inspect, and manage skills using the standard `SKILL.md` format (with YAML frontmatter).

**Key feature**: Works perfectly in **pure OpenClaw environments** with **zero Hermes Agent dependency**.

Skill tools (`skills_list`, `skill_view`, `skill_manage`) accept an optional `cwd` parameter so the calling agent can explicitly specify the workspace context on every call. The general-purpose `read_text` tool uses `cwd` to resolve relative file paths.

## Why This Exists

OpenClaw (and similar agents) have powerful built-in skills management via CLI (`openclaw skills list`, `skills info`, etc.). However, for the *agent itself* to programmatically discover and read skills during reasoning (progressive disclosure, on-demand loading of full `SKILL.md`), you need MCP tools.

This server exposes these tools that agents love to use:
- `skills_list` — lightweight discovery
- `skill_view` — the main "skill-info" tool (read full `SKILL.md` or supporting files)
- `skill_manage` — create new skills (more actions planned)
- `read_text` — read an arbitrary text file (absolute or relative path; rejects non-text)

The format is compatible with the agentskills.io / Hermes SKILL.md convention, so skills are portable.

## Pure OpenClaw Setup (No Hermes Needed)

This is the primary intended use case.

### Recommended Skill Locations for OpenClaw Users

1. **Workspace skills** (best for most people):
   - `~/.openclaw/workspace/skills/`

2. **Global / shared skills**:
   - `~/.openclaw/skills/`
   - `~/.agents/skills/`

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
2. Local folders next to the **provided `cwd`** (or the `WORKDIR` environment variable, or real process cwd if both are omitted): `skills/`, `.skills/`, `.agents/skills/`, `agent-skills/`
3. OpenClaw workspace skills (`<workspace>/skills`, `<workspace>/.agents/skills`) — read from `~/.openclaw/openclaw.json` (`agents.defaults.workspace`) or the common default `~/.openclaw/workspace`
4. `~/.openclaw/skills/`, then `~/.agents/skills/`
5. Fallback: `~/.agent-skills/` (neutral directory)

This means in a typical pure OpenClaw session, it will usually just find `~/.openclaw/workspace/skills/` automatically.

## Explicit Workspace Context via the `cwd` Parameter (Recommended for Agents)

To give the calling agent precise control (independent of the MCP server's process working directory), skill tools accept an optional `cwd` parameter. `read_text` also accepts `cwd` for relative path resolution:

```json
// List skills in a specific workspace
skills_list(cwd="/home/alex/.openclaw/workspace")

// View a skill using explicit context
skill_view(name="proactivity", cwd="/home/alex/.openclaw/workspace")

// Create a skill in a project-specific location
skill_manage(action="create", name="my-new-skill", frontmatter={...}, body="...", cwd="/path/to/current/project")

// Read a text file (absolute path, or relative to cwd)
read_text(path="notes.md", cwd="/path/to/project")
read_text(path="/absolute/path/to/file.txt")

// Large files: at most 50K bytes per call — continue with offset
read_text(path="/absolute/path/to/large.txt")
read_text(path="/absolute/path/to/large.txt", offset=51200)

// Optional line limit (default: entire file within the 50K cap)
read_text(path="/absolute/path/to/file.txt", lines=50)
read_text(path="/absolute/path/to/file.txt", offset=1234, lines=50)
```

- If `cwd` is provided, it becomes the base for the "local project skills" detection layer (#2 above).
- Passing the workspace root (e.g. `~/.openclaw/workspace`) will reliably pick up `<workspace>/skills`.
- If omitted, the server falls back to the `WORKDIR` environment variable, then full auto-detection (including the real process `cwd` and OpenClaw config).
- The tool response always includes the final resolved `"skills_root"` so you can see what was used.

This design is ideal for agents: the LLM can decide "for this task I want skills from this workspace" and pass the `cwd` explicitly on the tool call.

## Handling Dynamically Generated / Temporary Workspaces (pinchbench, benchmark runners, isolated tests, CI)

Frameworks like **pinchbench** (and similar test harnesses) often **automatically create brand new, isolated workspace directories** for every test or benchmark run (e.g. `/tmp/pinchbench_run_42/workspace`, `/tmp/test-xyz/workspace`).

In these situations:

- Global auto-detection or a fixed `SKILLS_ROOT` env var will **not** be sufficient — they are too static.
- You **must** pass the freshly created workspace path using the `cwd` parameter on **every** tool call.

Because the server is completely stateless (resolution happens fresh on each tool invocation), it will correctly and instantly switch to the skills living inside that temporary workspace.

**Verified behavior** (live simulation test with real temporary directory):
- Calling `skills_list()` / `skill_view()` **without** `cwd` → stays on the real persistent OpenClaw workspace (e.g. `~/.openclaw/workspace/skills`), count = 5 real skills, the temporary test skill is invisible.
- Calling with `cwd="/tmp/.../pinchbench_run_XX/workspace"` → immediately resolves to `<new_workspace>/skills`, lists only the skills that exist in that run (including a dynamically created "Test Skill for Pinchbench"), and `skill_view(name="test-skill", cwd=...)` successfully returns the frontmatter + body.

Recommended practice for such environments:
- Instruct your agent (in system prompt or via the test harness) to **always include the current test workspace** when calling skills tools:
  ```json
  skills_list(cwd="<current_pinchbench_or_test_workspace>")
  skill_view(name="xxx", cwd="<current_pinchbench_or_test_workspace>")
  ```
- The harness should expose the active workspace path to the agent for each isolated run.

This makes the MCP server fully compatible with isolated, auto-generated workspace workflows such as pinchbench.

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
- `read_text(path="README.md", cwd="/path/to/project")`
- `read_text(path="/absolute/path/to/notes.txt")`

### `read_text` notes

- Returns JSON with `success`, `path`, `encoding`, `size_bytes`, `offset`, `bytes_read`, `max_bytes`, `lines`, `lines_returned`, `truncated`, `next_offset`, and `content` on success.
- **50K byte limit (important)**: each call returns at most **50K bytes (51200)**. If more data remains, `truncated` is `true` and `next_offset` is set — call again with `offset=next_offset` until `truncated` is `false`. Do not assume a single call returns the whole file.
- **`lines` (optional)**: max number of lines to return. **Default (omit/`null`) = read the entire file** (still capped by 50K bytes). When set, returns at most that many lines; if more content remains, use `offset=next_offset` to continue.
- **Relative `path` base** (same order as skill tools): explicit `cwd` → `WORKDIR` env → process cwd.
- **Text files only**: if the target is binary/non-text (NUL bytes in the probe sample, or cannot decode with the given encoding), the tool returns `success: false` with an error like `"Cannot read file: not a text file"` and **does not include file content**.

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
