# Hermes Skills MCP Server — Software Development Requirements

## Project Goals

Provide a standalone, reusable MCP (Model Context Protocol) server written in Python that exposes the core Hermes skill management capabilities to any MCP-compatible agent environment.

The server enables other agents (OpenClaw, Hermes via native-mcp, Claude Desktop, Cursor, LM Studio, etc.) to:
- Discover available skills
- Inspect full skill content (SKILL.md + supporting files)
- Create, update, and manage skills

This allows skill knowledge (reusable workflows, instructions, procedures) to be shared across different agent platforms without each agent re-implementing the skill system.

## Core Principles

- **Progressive Disclosure**: Agents first see lightweight metadata (`skills_list`), then request full content only when needed (`skill_view`). This keeps context usage efficient.
- **Format Compatibility**: Fully compatible with the Hermes/agentskills.io SKILL.md format (YAML frontmatter + Markdown body, optional `references/`, `templates/`, `assets/` directories).
- **Security and Safety First**: All file access is strictly contained to a configured skills root. Path traversal, absolute paths, and escaping the root are forbidden.
- **Cross-Platform Agent Interoperability**: The same server can be registered and used by OpenClaw (via `openclaw mcp set`), Hermes, and standard MCP clients.
- **Structured, Reliable Tool Outputs**: Tools return clear success/error information in a consistent, machine-readable format.
- **Minimal Dependencies and Easy Deployment**: Uses standard Python packaging (uv) and the official MCP Python SDK (FastMCP).
- **Self-Contained**: The server does not require a full Hermes installation to run. It can serve any directory that follows the SKILL.md convention.

## Target Users and Usage Scenarios

1. **OpenClaw users** who have migrated skills from Hermes or want to maintain a central skill library usable from OpenClaw.
2. **Multi-agent setups** where different agents (Hermes + OpenClaw + others) need to share the same skill definitions.
3. **Developers authoring skills** who want to test their SKILL.md files against a neutral MCP interface before loading into a full agent.
4. **Research / experimentation** with skill systems across agent frameworks.

## Functional Requirements

### FR-1: Configuration
- The server MUST support configuring the root skills directory via:
  - Environment variable `SKILLS_ROOT` (highest priority)
  - Command-line argument (when using `mcp run` or direct execution)
  - Sensible default: `~/.hermes/skills` (if present) or a user-specified path
- The server MUST validate on startup that the configured root exists or can be created.

### FR-2: Tool — skills_list
- Expose a tool named `skills_list`.
- Parameters: optional filter (e.g. category, enabled_only — initially simple).
- Returns: JSON list of skills with metadata only (name, description, category if detectable, path relative to root, version if present, platforms if declared).
- Must not load full skill content (progressive disclosure).
- Must handle empty skill directories gracefully.

### FR-3: Tool — skill_view
- Expose a tool named `skill_view`.
- Parameters:
  - `name`: string — the skill identifier (directory name or relative path under root, e.g. "hermes-agent" or "mlops/axolotl")
  - `file_path`: optional string — sub-path inside the skill directory (e.g. "references/api.md", "templates/prompt.md"). If omitted, returns the main SKILL.md.
- Behavior:
  - Resolve the skill directory safely under the configured root.
  - If `file_path` is provided, load that specific file.
  - For the main SKILL.md: parse YAML frontmatter + body.
  - Return structured result containing:
    - success status
    - parsed frontmatter (as dict)
    - full markdown body
    - raw content (when requested)
    - absolute/relative paths for debugging
    - readiness status (missing prerequisites, etc. — at minimum success/failure)
- Must support loading supporting files without requiring the main SKILL.md to be re-parsed every time.
- Must reject any path that would escape the skill directory or the root.

### FR-4: Tool — skill_manage
- Expose a tool named `skill_manage` (or a set of focused tools if clearer).
- Supported actions (at minimum):
  - `create`: Create a new skill directory + basic SKILL.md from provided frontmatter + body.
  - `patch` / `update`: Update an existing SKILL.md (frontmatter merge or full body replacement).
  - `delete` / `archive`: Remove or archive a skill (with safety checks).
- All write operations MUST:
  - Validate paths strictly.
  - Never overwrite without explicit confirmation where dangerous.
  - Return clear before/after state and success/failure.
- The tool must be usable for both interactive development and automated skill maintenance.

### FR-5: SKILL.md Format Support
- The server MUST correctly parse and preserve the standard frontmatter fields used by Hermes:
  - `name`, `description` (required)
  - `version`, `license`, `platforms`, `prerequisites`, `required_environment_variables`, `metadata` (including nested `hermes` section)
- Must support the full agentskills.io compatible structure including optional sub-directories (`references/`, `templates/`, `assets/`).
- When returning content, the original formatting of the Markdown body should be preserved as much as possible.

### FR-6: Error Handling and Feedback
- All tools must return structured output (never silent failure).
- Common error cases must be explicitly reported:
  - Skill not found
  - Path traversal attempt
  - Permission errors
  - Invalid frontmatter
  - Missing required fields
- Errors should be actionable for an agent (include hints where appropriate).

### FR-7: Transport and Execution
- Default transport: stdio (for local agent integration).
- Must also support being run as a module or via the MCP CLI (`mcp run server.py`).
- The package should provide a clean command-line entry point after installation.

### FR-8: Documentation and Integration
- Provide clear README instructions for:
  - Running the server directly
  - Registering with OpenClaw (`openclaw mcp set <name> '{"command": "..."}'`)
  - Registering with Hermes (`hermes mcp add`)
  - Testing with the MCP inspector or simple clients
- Include example skill directory structure in the repository.
- Document environment variables and configuration options.

## Non-Functional Requirements

- **Language & Packaging**: Python >= 3.11, managed with `uv`. Minimal dependencies (only `mcp[cli]` and `pyyaml` initially).
- **Security**: No execution of arbitrary code from skills. File operations only. All paths validated.
- **Performance**: Listing and viewing a single skill must be fast (< 500ms on typical hardware even with hundreds of skills).
- **Reliability**: Graceful handling of malformed SKILL.md files (report error but continue listing other skills).
- **Maintainability**: Code should be clean, well-commented, and easy for a coding agent to extend (e.g. adding more manage actions or advanced filtering).
- **Portability**: Should work on Linux, macOS, and Windows (with appropriate path handling).

## Interface Definitions (Tool Schemas — High Level)

The exact JSON schemas will be defined in code using FastMCP decorators, but the server must expose tools with the following logical contracts:

1. `skills_list` → returns list of skill metadata objects
2. `skill_view(name, file_path?)` → returns skill document (frontmatter + content) or sub-file content
3. `skill_manage(action, name, content?, ...)` → returns operation result with success and details

(Full Pydantic models / JSON schemas will be part of the implementation.)

## Usage Examples (User-Facing)

**Starting the server (development):**
```bash
uv run python -m hermes_skills_mcp_server.server
# or after packaging
hermes-skills-mcp
```

**Registering in OpenClaw (persistent):**
```bash
openclaw mcp set hermes-skills '{
  "command": "uv",
  "args": ["--directory", "/path/to/hermes-skills-mcp-server", "run", "python", "-m", "hermes_skills_mcp_server.server"]
}'
```

**Using from an agent:**
The agent can then call:
- `skills_list`
- `skill_view(name="hermes-agent")`
- `skill_view(name="hermes-agent", file_path="references/prompt-builder-environment-hints.md")`
- `skill_manage(...)` for authoring

## Out of Scope (for initial version)

- Full skill hub search / install from remote registries (can be added later)
- GUI or web interface
- Built-in secret collection / setup wizard (report missing requirements only)
- Complex conflict resolution during patch/create
- Running skills as executable workflows (only serving the documents)
- Authentication / multi-tenant support

## Assumptions and Constraints

- Skills follow the directory + SKILL.md layout established by Hermes.
- The primary consumer in the near term is OpenClaw (hence strong emphasis on correct `openclaw mcp set` instructions).
- The server will initially be used locally (stdio). Remote/HTTP transport can be added later.
- Users are comfortable with `uv` for Python project management.

## Success Criteria

- A coding agent (Grok, Claude, etc.) can take this document + the initial skeleton and produce a fully working, tested MCP server.
- The server can be registered in OpenClaw and an agent inside OpenClaw can successfully call `skills_list` and `skill_view` on real Hermes skills.
- The same server works when registered back into a Hermes session via native-mcp.
- All path safety rules are enforced (verified by tests or manual attack cases).

---

**This document is intentionally free of implementation details, class names, specific algorithms, or file layouts.** It describes only the required external behavior, user experience, and tool contracts so that implementation can be handed off cleanly to an autonomous coding agent. 

**Next step after approval**: Hand this REQUIREMENTS.md to Grok Build (or equivalent) together with the current project skeleton for full implementation.