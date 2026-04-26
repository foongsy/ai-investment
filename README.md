# Personal Investment Assistant Workspace

This repository is a Cursor workspace for personal investment research, planning, and assistant workflows.

It is not a coding workspace. The assistant should avoid adding code, scripts, applications, notebooks, or software project scaffolding. If code is genuinely required by the user, the assistant must explain why, describe the files that would be created or changed, and ask for confirmation twice before proceeding.

## Purpose

This workspace is for:

- Investment research and analysis support
- Portfolio review support
- Market and product research
- Safe integration with external services through Cursor MCP
- Reusable assistant workflows through Agent Skills

This workspace is not for:

- Placing trades
- Moving money
- Storing credentials or account secrets
- Storing raw financial statements, tax files, or brokerage exports
- Producing financial, legal, or tax advice
- Building software projects or storing code by default

## Language And Scope

Default communication language is Hong Kong Traditional Chinese unless otherwise requested.

Covered product types:

- Equities
- Derivatives
- ETFs
- Crypto assets

Covered markets:

- Hong Kong
- Japan
- United States

## Workspace Structure

- `AGENTS.md`: Instructions for Cursor Agent behavior, safety boundaries, language preference, and workspace rules.
- `data/`: Sanitized examples, schemas, derived summaries, or pointers to approved external data sources.
- `.agents/skills/`: Project-level Agent Skills for repeatable assistant workflows.
- `.cursor/rules/`: Cursor project rules for safety and research workflows.
- `.cursor/mcp.json`: Project-level MCP configuration. It currently contains no live services or credentials.
- `.cursorignore`: Excludes sensitive or bulky files from Cursor context and indexing.

## Data Policy

Keep sensitive financial data outside this workspace by default.

Do not store credentials, API keys, access tokens, seed phrases, account numbers, tax identifiers, identity documents, full statements, raw exports, or tax forms.

Before saving any data into the workspace, the assistant should summarize what will be saved, where it will be saved, and whether it may contain sensitive financial or personal information.

## Safety

The assistant must not place trades, move money, submit forms, open accounts, close accounts, change beneficiaries, or take irreversible financial actions.

All outputs should be treated as research and analysis support, not financial advice.
