# Agent Skills MCP Server — Software Development Requirements

## Project Goals

Provide a **completely standalone** MCP server (no Hermes Agent required) that implements the core skill management tools (`skills_list`, `skill_view`, `skill_manage`) plus a general-purpose `read_text` tool, using the standard `SKILL.md` + YAML frontmatter format.

The primary target is **pure OpenClaw environments**. OpenClaw users should be able to give their agent the ability to discover, read, and author skills programmatically via MCP, just like Hermes agents can.

## Core Principles

- **Standalone & Zero-Dependency on Hermes**: Must work in an environment that only has OpenClaw (or any other MCP client). No `~/.hermes` paths as hard defaults.
- **OpenClaw-First Experience**: Automatic detection of OpenClaw workspace skills (`~/.openclaw/workspace/skills`, `~/.openclaw/workspace/.agents/skills`, etc.).
- **Explicit Context Control**: Tools must accept an optional `cwd` parameter so the calling agent can specify the intended workspace/project root on a per-call basis (instead of relying only on process cwd or global defaults).
- **Support for Dynamic / Temporary Workspaces**: Must correctly handle environments where new workspaces are auto-generated on every run (e.g. pinchbench, benchmark runners, isolated test harnesses, CI). Per-call `cwd` is the primary mechanism for switching context in these cases.
- **Progressive Disclosure**: `skills_list` returns only metadata. Full content is loaded on demand via `skill_view`.
- **Portable Skill Format**: Uses the widely understood `SKILL.md` format so skills can be shared between different agents.
- **Security**: Strict containment to the chosen skills root. No path traversal.
- **Agent-Usable**: Tools return clean, structured **plain text** (not JSON) that LLMs can read and act upon without a parse step.

## Target Users

- OpenClaw users who want their agent to have first-class, on-demand access to skills (beyond CLI `openclaw skills` commands).
- Anyone who wants a neutral, MCP-based skill system that is not tied to a specific agent framework.
- People maintaining shared skill libraries across Hermes + OpenClaw setups.
- Teams using automated testing / benchmarking frameworks that spawn fresh workspaces (pinchbench etc.).

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
- Must support completely new, temporary workspaces created at runtime (pinchbench-style) when the correct `cwd` is supplied on the call.

**FR-2: skills_list tool**

- Returns lightweight metadata only (name, description, directory, version, platforms, category).
- Supports optional category filter.
- Must work even if the skills root is empty.
- **Must accept optional `cwd: str | None = None`** parameter (documented in the tool).
- Always include the resolved `skills_root` in the plain-text response.

**FR-3: skill_view tool (the "skill-info" tool)**

- `skill_view(name, file_path?, cwd?)`
- `name` can be directory name or declared skill name (directory name preferred for reliability).
- Supports loading sub-files inside a skill (e.g. `references/xxx.md`).
- Returns the raw file contents as plain text (SKILL.md includes its YAML frontmatter). A short header names `skills_root`, `skill_name`, and `file`.
- Clear error messages for missing skills or invalid paths.
- **Must accept optional `cwd: str | None = None`** parameter.
- Security: strict path validation relative to the resolved root.

**FR-4: skill_manage tool**

- At minimum supports `action="create"` with `frontmatter` + `body`.
- Future actions (patch, delete) should be planned but clearly marked as not-yet-implemented.
- All writes must be safe and contained.
- **Must accept optional `cwd: str | None = None`** parameter.
- Returns a clear plain-text success or error message.

**FR-5: Format Compatibility**

- Must correctly parse standard SKILL.md frontmatter (name, description, version, platforms, metadata, etc.).
- Must preserve the full markdown body.

**FR-6: Error Handling & Structured Output**

- Every tool returns **plain text**, not a JSON object. Failures start with `Error: ` plus a clear message.
- Path safety errors must be explicit.
- Every successful skill-tool response should surface the `skills_root` that was actually used.

**FR-7: OpenClaw Registration**

- Documentation must lead with `openclaw mcp set ...` (not Hermes commands).
- Clear examples for both auto-detection (`SKILLS_ROOT` env) and per-call `cwd` usage.
- Explain that the workspace is dynamically detected rather than a single hardcoded default.
- Explicitly document support for dynamically generated workspaces (pinchbench etc.) via the `cwd` parameter.

**FR-8: read_text tool**

- `read_text(path, offset?, lines?, cwd?, encoding?)` — general-purpose text file reader (not bound to the skills root).
- `path` may be absolute or relative; relative paths resolve against `cwd` when provided, else the `WORKDIR` environment variable, else the process cwd (same base order as skill tools / `get_skills_root` layer #2).
- **Hard limit of 50K bytes (51200) per call**: never return more than this much file data in one response. This is a critical agent-facing rule and must be documented in the tool description.
- `offset` is a non-negative **byte** offset (default `0`). When content is truncated, the response MUST include `truncated: true` and `next_offset` so the agent can continue with `offset=next_offset`. When the end of the file is reached, `truncated` is `false` and `next_offset` is `null`.
- **`lines` (optional)**: when omitted/`null`, read the entire file (within the 50K byte cap). When set to a positive integer N, return at most N lines (still subject to the 50K cap). Invalid values (non-positive, non-integer) must return a clear error.
- On success returns plain text: a metadata header (`path` as resolved absolute, `encoding`, `size_bytes`, `offset`, `bytes_read`, `max_bytes`, `lines`, `lines_returned`, `truncated`, `next_offset`), an optional continuation message when truncated (byte cap vs line limit), a `-----` separator, then the raw file text.
- Chunk boundaries must not split multi-byte characters for the chosen encoding (trim incomplete trailing sequences; for UTF-8, skip incomplete lead bytes when `offset > 0`).
- **Plain text only**: the tool description MUST state USE ONLY plain-text extensions and DO NOT use for PDF, images, Office, archives, or other binaries.
- Known non-text extensions (e.g. `.pdf`, `.png`, `.docx`, `.zip`) MUST be rejected early with a clear error that names the extension and tells the agent not to use `read_text` for that format; **must not include any file content**.
- Additional content checks: if the target is not a text file (e.g. contains NUL bytes, or cannot be decoded with the given encoding), return `success: false` with a clear error and **must not include any file content**.
- Clear errors for missing paths, directories, empty `path`, invalid/past-end `offset`, invalid `lines`, unknown encoding, and I/O failures.
- Optional `encoding` (default `utf-8`).

## Non-Functional Requirements

- No hard dependency on Hermes installation or `~/.hermes`.
- Minimal dependencies (`mcp[cli]`, `pyyaml`).
- Fast startup and tool responses.
- Works when run via `uv run` or after packaging.
- The `cwd` parameter must be optional (default `None` → full auto-detection) for convenience while still enabling explicit control.
- Tool calls must be stateless so that rapidly changing workspaces (new temp dir per test) can be handled without server restart.

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
- When a completely new temporary workspace is created (e.g. by pinchbench), passing the new path as `cwd` causes the tools to immediately see only the skills in that new workspace (verified by simulation).
- The server can be used to create new skills that the agent can immediately view.
- Responses always report the actual `skills_root` used.

---

This document focuses on desired external behavior and usage for handoff to coding agents. Implementation details (class structure, exact file layout) are intentionally omitted.
