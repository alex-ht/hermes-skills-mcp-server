# Agent Skills MCP Server — Software Development Requirements

## Project Goals

Provide a **completely standalone** MCP server (no Hermes Agent required) that implements the core skill management tools (`skills_list`, `skill_view`, `skill_manage`) using the standard `SKILL.md` + YAML frontmatter format.

The primary target is **pure OpenClaw environments**. OpenClaw users should be able to give their agent the ability to discover, read, and author skills programmatically via MCP, just like Hermes agents can.

## Core Principles

- **Standalone & Zero-Dependency on Hermes**: Must work in an environment that only has OpenClaw (or any other MCP client). No `~/.hermes` paths as hard defaults.
- **OpenClaw-First Experience**: Automatic detection of OpenClaw workspace skills (`~/.openclaw/workspace/skills`, `~/.openclaw/workspace/.agents/skills`, etc.).
- **Explicit Context Control**: Tools must accept an optional `cwd` parameter so the calling agent can specify the intended workspace/project root on a per-call basis (instead of relying only on process cwd or global defaults).
- **Progressive Disclosure**: `skills_list` returns only metadata. Full content is loaded on demand via `skill_view`.
- **Portable Skill Format**: Uses the widely understood `SKILL.md` format so skills can be shared between different agents.
- **Security**: Strict containment to the chosen skills root. No path traversal.
- **Agent-Usable**: Tools return clean, structured JSON that LLMs can reliably parse and act upon.

## Target Users

- OpenClaw users who want their agent to have first-class, on-demand access to skills (beyond CLI `openclaw skills` commands).
- Anyone who wants a neutral, MCP-based skill system that is not tied to a specific agent framework.
- People maintaining shared skill libraries across Hermes + OpenClaw setups.

## Functional Requirements

**FR-1: Smart Skills Root Detection (OpenClaw priority + cwd override)**

- Must honor `SKILLS_ROOT` env var as highest priority.
- Must auto-detect OpenClaw workspace from `~/.openclaw/openclaw.json` (`agents.defaults.workspace`).
- Must look for skills in common OpenClaw locations:
  - `<workspace>/skills`
  - `<workspace>/.agents/skills`
  - `~/.openclaw/skills`
- Must also support local project skills relative to a **provided `cwd`** (or real cwd if omitted): `./skills`, `./.agents/skills`, etc.
- Neutral fallback: `~/.agent-skills`
- **The `cwd` parameter on tools must override only the "local project" layer** while still allowing OpenClaw workspace detection to function.
- The resolved root must be returned in tool responses (e.g. `"skills_root"` field) for transparency.

**FR-2: skills_list tool**

- Returns lightweight metadata only (name, description, directory, version, platforms, category).
- Supports optional category filter.
- Must work even if the skills root is empty.
- **Must accept optional `cwd: str | None = None`** parameter (documented in the tool).
- Always include the resolved `skills_root` in the JSON response.

**FR-3: skill_view tool (the "skill-info" tool)**

- `skill_view(name, file_path?, cwd?)`
- `name` can be directory name or declared skill name (directory name preferred for reliability).
- Supports loading sub-files inside a skill (e.g. `references/xxx.md`).
- Returns parsed frontmatter + body for `SKILL.md`, raw content for other files.
- Clear error messages for missing skills or invalid paths.
- **Must accept optional `cwd: str | None = None`** parameter.
- Security: strict path validation relative to the resolved root.

**FR-4: skill_manage tool**

- At minimum supports `action="create"` with `frontmatter` + `body`.
- Future actions (patch, delete) should be planned but clearly marked as not-yet-implemented.
- All writes must be safe and contained.
- **Must accept optional `cwd: str | None = None`** parameter.
- Returns clear success/error JSON.

**FR-5: Format Compatibility**

- Must correctly parse standard SKILL.md frontmatter (name, description, version, platforms, metadata, etc.).
- Must preserve the full markdown body.

**FR-6: Error Handling & Structured Output**

- Every tool returns JSON with `success`, `error` (on failure), and relevant data.
- Path safety errors must be explicit.
- Every successful response should surface the `skills_root` that was actually used.

**FR-7: OpenClaw Registration**

- Documentation must lead with `openclaw mcp set ...` (not Hermes commands).
- Clear examples for both auto-detection (`SKILLS_ROOT` env) and per-call `cwd` usage.
- Explain that the workspace is dynamically detected rather than a single hardcoded default.

## Non-Functional Requirements

- No hard dependency on Hermes installation or `~/.hermes`.
- Minimal dependencies (`mcp[cli]`, `pyyaml`).
- Fast startup and tool responses.
- Works when run via `uv run` or after packaging.
- The `cwd` parameter must be optional (default `None` → full auto-detection) for convenience while still enabling explicit control.

## Out of Scope (Initial Version)

- Full replacement of OpenClaw's native `openclaw skills` CLI.
- Automatic syncing with ClawHub / remote skill registries.
- Advanced skill execution / templating.
- Multi-root / workspace vs global separation UI.
- Statefulness (e.g. a "set current workspace" tool) — per-call `cwd` is preferred.

## Success Criteria

- In a pure OpenClaw installation (no Hermes), registering the server via `openclaw mcp set` allows the agent to successfully call `skills_list` and `skill_view` on skills located in `~/.openclaw/workspace/skills`.
- Auto-detection correctly picks up the user's OpenClaw workspace without any manual `SKILLS_ROOT`.
- The agent can pass `cwd="/some/workspace"` (or a project dir) on individual tool calls and get skills resolved relative to that context.
- The server can be used to create new skills that the agent can immediately view.
- Responses always report the actual `skills_root` used.

---

This document focuses on desired external behavior and usage for handoff to coding agents. Implementation details (class structure, exact file layout) are intentionally omitted.
