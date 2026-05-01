# Refresh Workspace

Refresh your working understanding of this workspace in read-only mode.

## Steps

1. Read the main workspace guidance:
   - `AGENTS.md`
   - `README.md`

2. Refresh `data/` context:
   - List files under `data/`.
   - Read relevant non-sensitive text, Markdown, and schema files needed to understand current workspace data structures and references.
   - Do not read raw financial exports, statements, tax documents, account documents, or bulky/binary files unless the user explicitly asks.

3. Refresh available project skills:
   - List `.agents/skills/*/SKILL.md`.
   - Read each `SKILL.md` summary/frontmatter.
   - Note which skills are available and when they should be used.

4. Refresh Cursor, MCP, and tool configuration:
   - Read `.cursor/mcp.json`.
   - Read `.env` as part of the refresh.
   - Use `.env` only to understand local configuration needed for tools and services.
   - Never print secret values.
   - Summarize only variable names, whether they are present, and purpose when obvious.
   - If values are needed for diagnosis, describe them as present, missing, or invalid-looking without revealing raw values.
   - Do not call external MCP services unless the user explicitly asks.

5. Refresh repo state:
   - Run `git status --short`.
   - Summarize modified and untracked files.
   - Do not stage, commit, delete, move, edit, or generate files.

6. Final response:
   - Briefly summarize current workspace purpose.
   - List active rules and safety constraints that matter.
   - List available skills and tools.
   - List notable repo state.
   - Mention that `.env` was read for configuration only, without exposing values.
