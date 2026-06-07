# Personal Investment Assistant Instructions

This workspace is for personal investment research, planning, and assistant workflows. It is not a coding workspace. Treat all work here as analysis support, not financial, legal, or tax advice.

## Operating Preferences

These defaults control how the assistant should reason, prioritize, and communicate in this workspace.

- Default user-facing language: Hong Kong Traditional Chinese (unless user asks otherwise).
- Default market coverage: Hong Kong, Japan, and US.
- Default asset focus: equities, derivatives, ETFs, and crypto assets.
- When market conventions differ by region, always state market, currency, trading venue, timezone, and regulatory context.
- Apply weekend/weekday operating rhythm:
  - Weekend (Research Mode): generate ideas, run research, identify opportunities, and formulate plans.
  - Weekday (Execution Mode): prioritize execution, adjustments, and risk/trigger monitoring based on existing plans.

## System Configuration

These are technical/runtime defaults for tools, integrations, and workspace references. They are not authorization to perform external writes without confirmation.

| Key | Value | Notes |
| --- | --- | --- |
| Portfolio schema | `data/notion/portfolio.md` | `Portfolio Snapshot`, `Portfolio Holdings`; Layer 3: `Portfolio Analysis`, `Target Portfolio Holdings`, `Rebalance Actions` |
| Research schema | `data/notion/research.md` | Canonical research system schema including two-layer Trading Proposals (Layer 1 + Layer 2 price plan, 31 properties) |
| TradingView assets | `data/tradingview/` | Watchlist `.txt` exports and Pine Screener `.pine` scripts for Layer 2 pricing |
| Environment template | `env.sample` | Non-secret template for API keys and service names; copy to `.env` locally |
| Notion portfolio databases | `Portfolio Snapshot`, `Portfolio Holdings`, `Portfolio Policy`, `Portfolio Analysis`, `Target Portfolio Holdings`, `Rebalance Actions` | Approved snapshot + holdings; guardrails in `data/portfolio/guardrails.md`; Layer 3 schema in `data/notion/portfolio.md` |
| Notion ideas database | `Research Ideas` | Idea lifecycle and scheduling control |
| Notion runs database | `Research Runs` | Run-level execution log and audit trail |
| Tooling priority | CLI > `curl` API > MCP | MCP is fallback unless explicitly requested |
| Auth method | Environment variables, then `.env` | Prefer non-interactive auth for local/cloud agents |

## Workflow Standards

### Design Intent

- Separate idea lifecycle from execution history.
- `Research Ideas` is the planning backlog and opportunity pipeline.
- `Research Runs` is the execution log and audit trail.
- Keep cross-database linking stable with relation + generated IDs.

### Low-Friction Idea Input

- User input should be minimal: enter only `Original Idea`.
- System derives a single research-ready field (`Research Input`) and classification tags.
- Avoid duplicate semantic fields that serve the same purpose.

### Scheduling Model

For recurring opportunity scans, `Research Ideas` should use:

- `Active` (checkbox) to control scheduler inclusion.
- `Run Frequency` (select): `Once`, `Daily`, `Weekly`, `Biweekly`, `Monthly`, `Quarterly`.
- `Last Run At`, `Last Run ID`, and latest `Executive Summary` for recency and continuity.

### Output Standardization Policy (v1)

- Treat `Executive Summary` as the only guaranteed common output across research runs.
- Store `Result URL` in Notion as the pointer to full run outputs in Parallel.
- Do not store raw JSON payloads in Notion.
- Add new structured fields only after repeated stable output patterns are observed.

### Notion Linking Convention

- In `Research Ideas`, keep `Idea ID` as an auto-generated stable identifier.
- In `Research Runs`, link via `Idea` relation and use rollup for `Idea ID`.
- Do not maintain duplicate manual ID fields when rollup can provide the same value.

### Tradable Proposal Layers

- **Layer 1:** Research follow-up imports qualitative fields into `Trading Proposals`.
- **Layer 2:** Alpha Vantage last close populates `Last Price`; Pine Screener scripts, manual review, or other external processes set `Entry Price`, `Stop Price`, `Target Price`, derived `Reward Risk Ratio`, and `Pricing Status`.
- **Layer 3:** **Portfolio Analysis** → **Target Portfolio Holdings** + **Rebalance Actions** (workflow ends at these outputs). See `data/portfolio/guardrails.md`. No trade ledger, rebalance execution tracking, or P&L in this workspace.
- **Execution:** Manual only. No automated order placement.
- Confirm before Notion structure changes on `Trading Proposals` or portfolio databases.
- Canonical research schema (including Trading Proposals): `data/notion/research.md`.

## Tooling & Authentication

- Prefer relevant project skills first when available.
- Default execution priority: CLI tools -> direct API calls via `curl` -> MCP tools (fallback, or when explicitly requested).
- For Notion operations, prefer Notion REST API via `curl`.
- For Alpha Vantage market data lookups, prefer the `alphavantage-curl` skill and direct `curl` requests, especially for global indices plus Japan and US market data.
- For deep research operations, prefer `parallel-cli`.
- Skills: `alphavantage-curl`, `notion-api`, `parallel-deep-research`, `expand-new-ideas`, `run-expanded-ideas-deep-research`, `poll-deep-research-runs`, `followup-tradable-tickers`, `export-tv-watchlist`, `create-tv-pine-screener`, `import-screener-pricing`, `fastio-cli`, `refresh-proposal-quotes`, `evaluate-portfolio-guardrails`, `run-portfolio-analysis`, `refresh-workspace`
- CLI: `parallel-cli`, `fastio`, `git`, `npx skills`
- Direct API via `curl`: Notion API, Alpha Vantage API, Parallel Task API, TradingView symbol search
- MCP tools are secondary by default in this workspace.
- This workspace may run in local or cloud agents; prefer non-interactive authentication.
- Always check environment variables first, then `.env` (without exposing secret values) when a tool supports API key/token auth.
- Prefer API key/token authentication over manual login flows.
- If a tool only supports manual interactive login and has no non-interactive alternative, treat it as unavailable for cloud-agent execution unless the user provides another approved path.

## Safety & Change Control

- Do not place trades, move money, submit forms, open accounts, close accounts, change beneficiaries, or take any irreversible financial action.
- Do not provide personalized financial advice as a final recommendation. Present research, tradeoffs, risks, assumptions, and options for the user to evaluate.
- Ask for explicit confirmation before reading, summarizing, or using sensitive financial documents.
- Prefer read-only workflows by default.
- Before any write to Notion, databases, files, or external services:
  - summarize target objects (page/database/data source IDs where applicable),
  - summarize exact intended change and impact (create/update/archive/trash/delete),
  - and wait for explicit confirmation.
- Never blindly clear all parent page blocks when embedded databases may exist.
- Prefer non-destructive updates (append/replace text sections without removing database blocks).
- Do not hardcode secrets in `.cursor/mcp.json`, scripts, data files, or skill files.

## Research & Data Standards

- Cite sources for market data, company facts, filings, news, and third-party claims.
- Separate facts, assumptions, estimates, and opinions.
- Highlight uncertainty, conflicts between sources, stale data, and missing context.
- Prefer primary sources such as company filings, investor relations material, regulatory data, and official economic data when available.
- Do not overstate precision. Use ranges or scenarios when exact figures are not reliable.

## Portfolio Data Schema Guidance

- Keep workspace contents simple and centralized under `data/` unless explicitly approved otherwise.
- Use `data/` only for sanitized examples, schemas, derived summaries, or pointers to approved external sources.
- Never store credentials, API keys, access tokens, account numbers, SSNs, raw brokerage exports, statements, or tax files in this workspace or Notion.
- Initial portfolio storage target is Notion.
- Treat `data/notion/portfolio.md` as the canonical portfolio schema reference (single portfolio; snapshot-based).
- Do not apply Notion portfolio database structure changes without first summarizing intended changes and receiving explicit confirmation.

## Skills Policy

- Keep project-level skills under `.agents/skills/`.
- Skills can be managed in project scope with:
  - `npx skills list`
  - `npx skills add <source>`
  - `npx skills remove <skill-name>`
  - `npx skills add <source> --list`
- Before using a newly added skill that may access external services or private data, explain scope and ask for explicit confirmation.

### Skill Purpose In This Workspace (High Level)

- `alphavantage-curl`: use for Alpha Vantage Core Stock API and Index Data API lookups with `curl`, especially for global indices, Japan market data, and US market data, including stock time series, latest quotes, symbol search, and listing status.
- `notion-api`: use for building and maintaining the Notion research operating system (database structure, operational fields, and workflow documentation pages).
- `parallel-deep-research`: use for deep thematic research runs (primarily weekend research mode), including run tracking and summary capture.
- `expand-new-ideas`: use to transform eligible Notion `Research Ideas` from raw `Original Idea` entries into research-ready `Research Input` before execution.
- `run-expanded-ideas-deep-research`: use to kick off Parallel deep research for eligible expanded ideas and prepare run metadata logging.
- `poll-deep-research-runs`: use to poll in-flight Parallel research runs and update Notion with completion status, summaries, and result pointers.
- `followup-tradable-tickers`: use to run a Parallel Task API follow-up from a prior interaction, validate tradable ticker JSON with `ajv-cli`, and prepare/import linked `Trading Proposals` after confirmation per `data/notion/research.md`.
- `export-tv-watchlist`: use to export `Trading Proposals` for one `run_id` to a TradingView watchlist `.txt` file (`YYYY-MM-DD-<run_id>.txt`) with TV symbol resolution via `symbol_search/v3`, and provision the per-run Fast.io session `trading-proposals/sessions/<YYYY-MM-DD>-<run_id>/` with `watchlist.txt` (read-only Notion; use `--no-fastio` for local file only).
- `create-tv-pine-screener`: use to author Pine Script v5 indicators compatible with Pine Screener and `Trading Proposals` Layer 2 (`Entry Price`, `Stop Price`, `Target Price`, `Reward Risk Ratio`); saves to `data/tradingview/*.pine`.
- `import-screener-pricing`: use to download Pine Screener `screener*.csv` files from a per-run Fast.io session and import Layer 2 price fields into Notion `Trading Proposals` for rows where `Pricing Status` is not `Ready` (writes by default; use `--dry-run` to preview only).
- `fastio-cli`: use for basic Fast.io cloud file operations (list, create folders, upload, download, search) and per-run Trading Proposals session storage (`trading-proposals/sessions/<YYYY-MM-DD>-<run_id>/` with `watchlist.txt` and `screener*.csv`); resolves workspace and folders by name (`FASTIO_WORKSPACE_NAME`).
- `refresh-proposal-quotes`: use to fetch Alpha Vantage last daily close for `Trading Proposals` and update Notion `Last Price` and `Quote As Of` via curl (writes by default; use `--dry-run` to preview only).
- `evaluate-portfolio-guardrails`: use to compute portfolio heat, concentration, cash, and exposure metrics from the latest Approved Portfolio Snapshot in Notion and check against the active Notion `Portfolio Policy` (read-only; optional `--policy` YAML override).
- `run-portfolio-analysis`: use to run Layer 3 portfolio planning (unified rank + swap optimizer) from Notion snapshot, policy, and eligible Trading Proposals; JSON dry-run by default, `--write` for Notion Layer 3 outputs.
- `refresh-workspace`: use to refresh workspace rules, data context, skill inventory, local configuration, and git state in read-only mode.
- Use this section for workspace intent only; follow each skill's own documentation for execution details and API/CLI specifics.

## Cursor Cloud specific instructions

This workspace is an **agent-orchestrated integration layer**, not a deployable application. There is no `npm run dev`, Docker stack, project-wide linter, or always-on server. "Running the app" means invoking Agent Skills via Cursor (or their `run.sh` / `curl` steps) against configured external APIs.

### Runtime and dependencies

- **Required system tools:** `curl`, `jq`, `python3` (3.9+), `git`, `npx` (for `npx skills list` and `ajv-cli` in follow-up workflows).
- **Python venv:** Portfolio skills auto-create skill-local `.venv/` on first `run.sh` invocation. If venv creation fails with `ensurepip` errors, install `python3-venv` once on the VM (`apt install python3-venv`).
- **Auth:** Cloud Agents receive API keys via environment variables (`NOTION_API_TOKEN`, `ALPHAVANTAGE_API_KEY`, `PARALLEL_API_KEY`, etc.). A local `.env` is optional; scripts fall back to repo-root `.env` when env vars are unset.
- **Optional CLIs:** `parallel-cli` (Parallel research polling) and `fastio` (`npm install -g @vividengine/fastio-cli`). Skills work without them via direct `curl`.

### Smoke tests (no Notion writes)

```bash
# Portfolio planner unit tests (no API keys)
PYTHONPATH=".agents/skills/evaluate-portfolio-guardrails/scripts:.agents/skills/run-portfolio-analysis/scripts" \
  python3 .agents/skills/run-portfolio-analysis/tests/test_planner.py -v

# Bootstrap portfolio skill venvs (idempotent)
.agents/skills/evaluate-portfolio-guardrails/scripts/run.sh --help >/dev/null
.agents/skills/run-portfolio-analysis/scripts/run.sh --help >/dev/null
```

### Notion integration scope

The Notion bot must be **shared with each database** the skill needs. Portfolio skills (`evaluate-portfolio-guardrails`, `run-portfolio-analysis`) search for `Portfolio Snapshot`, `Portfolio Holdings`, and `Portfolio Policy`. If those data sources are not shared with the integration, those skills exit with `Could not find Notion data source` even when `NOTION_API_TOKEN` is valid. Research-track databases (`Research Ideas`, `Research Runs`, `Trading Proposals`) are the usual minimum for research and Layer 2 quote workflows.

### Portfolio skills (read-only by default)

```bash
.agents/skills/evaluate-portfolio-guardrails/scripts/run.sh --out /tmp/metrics.json
.agents/skills/run-portfolio-analysis/scripts/run.sh --out /tmp/plan.json   # JSON dry-run; --write for Notion
```

No local services need to be started. Layer 2 Pine Screener CSV import requires manual TradingView desktop export unless the user uploads `screener*.csv` to Fast.io.
