# Personal Investment Assistant Workspace

This repository is a Cursor workspace for personal investment research, planning, and assistant workflows.

It is not a coding workspace. The assistant should avoid adding code, scripts, applications, notebooks, or software project scaffolding unless a workflow explicitly requires it (for example Pine Screener scripts under `data/tradingview/`). If other code is genuinely required, the assistant must explain why, describe the files that would be created or changed, and ask for confirmation twice before proceeding.

## Purpose

This workspace is for:

- Investment research and analysis support
- Research idea intake, scheduling, and execution tracking
- Structured tradable ticker proposal research
- TradingView watchlist export and Pine Screener price-plan workflows
- Portfolio review support (daily snapshots and proposal impact analysis)
- Notion portfolio planning schema
- Market and product research
- Safe integration with external services through CLI tools and direct API calls
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

Weekend/weekday rhythm:

- **Weekend (Research Mode):** generate ideas, run research, identify opportunities, and formulate plans.
- **Weekday (Execution Mode):** prioritize execution, adjustments, and risk/trigger monitoring based on existing plans.

Covered product types:

- Equities
- Derivatives
- ETFs
- Crypto assets

Covered markets:

- Hong Kong
- Japan
- United States

## High-Level Data Flow

The workspace separates research workflow data from portfolio planning data. Research outputs may support human review and monitoring, but they do not directly execute trades, log fills, or move money.

```mermaid
flowchart TD
  subgraph IR[Idea Research Data Track]
    A[Original Idea]
    B[Research Ideas<br/>idea backlog and schedule]
    C[Research Brief<br/>expanded research input]
    D[Deep Research Run]
    E[Research Runs<br/>execution log]
    F[Research Results<br/>summary and result files]
    G[Updated Research Idea<br/>latest run, summary, recency]
  end

  subgraph TP[Tradable Proposal Track]
    H[Completed Research Context]
    I[Follow-up Opportunity Scan]
    J[Structured Ticker Opportunities]
    K[Trading Proposals<br/>Layer 1 qualitative + Layer 2 price plan]
    TV[TradingView Assets<br/>watchlist .txt + Pine Screener .pine]
  end

  subgraph PF[Portfolio Data Track]
    L[Approved Sanitized Portfolio Inputs]
    APS[Approved Portfolio Snapshot<br/>+ Portfolio Holdings]
    Policy[Portfolio Policy]
    PA[Portfolio Analysis]
    TPH[Target Portfolio Holdings]
    RA[Rebalance Actions]
  end

  A --> B --> C --> D --> E --> F --> G

  G --> H --> I --> J --> K --> TV

  TV --> R[Human Review / Decision Support]
  R --> S[Watchlist / Monitoring / Possible Trade Framing]
  S -. only approved sanitized records .-> L

  L --> APS
  K --> PA
  APS --> PA
  Policy --> PA
  PA --> TPH
  PA --> RA

  Z[Safety Boundary<br/>Research only<br/>No trade execution or money movement<br/>No raw sensitive exports stored<br/>External writes require confirmation]
  Z --- R
  Z --- L
```

## Tradable Proposal Layers

Trading proposals follow a two-layer model documented in [`data/notion/research.md`](data/notion/research.md) (Trading Proposals section):

| Layer | What | Where |
| --- | --- | --- |
| Layer 1 | Qualitative hypothesis from research import | `Trading Proposals` |
| Layer 2 | Alpha Vantage last close + external entry/stop/target prices and derived reward/risk | `Trading Proposals` price-plan fields |

Handoffs:

1. Research follow-up imports Layer 1 fields (`followup-tradable-tickers`).
2. Alpha Vantage last close populates `Last Price` and `Quote As Of` (`refresh-proposal-quotes`).
3. Pine Screener CSV exports from Fast.io populate `Entry Price`, `Stop Price`, `Target Price`, and derived `Reward Risk Ratio`, then set `Pricing Status = Ready` (`import-screener-pricing`; rows where `Pricing Status` is not `Ready`).

Layer 2 uses Alpha Vantage for `Last Price` only.

| Layer | What | Where |
| --- | --- | --- |
| Layer 3 | Target portfolio + rebalance actions under guardrails | **Portfolio Analysis** → **Target Portfolio Holdings** + **Rebalance Actions** (see [`data/notion/portfolio.md`](data/notion/portfolio.md)) |

Layer 3 inputs: latest **Approved Portfolio Snapshot**, eligible proposals, and active **Portfolio Policy**. Workflow ends at analysis outputs. No trade logging or rebalance execution tracking in this workspace.

## Workspace Structure

- `AGENTS.md`: Instructions for Cursor Agent behavior, safety boundaries, language preference, and workspace rules.
- `data/`: Sanitized examples, schemas, derived summaries, or pointers to approved external data sources.
  - `data/notion/`: Notion database specs (`research.md`, `portfolio.md`)
  - `data/parallel/`: Parallel Task API output contracts and paired prompts
  - `data/prompts/`: Reusable prompt assets
  - `data/tradingview/`: TradingView watchlist exports and Pine Screener scripts
- `.agents/skills/`: Project-level Agent Skills for repeatable assistant workflows.
- `.cursor/rules/`: Cursor project rules for safety and research workflows.
- `.cursor/mcp.json`: Project-level MCP configuration. It currently contains no live services or credentials.
- `.cursorignore`: Excludes sensitive or bulky files from Cursor context and indexing.
- `env.sample`: Non-secret template for local API keys and service names. Copy to `.env` locally.

## Agent Skills

Project skills live under `.agents/skills/`. Prefer skills and CLI tools over MCP unless explicitly requested.

| Skill | Purpose |
| --- | --- |
| `alphavantage-curl` | Alpha Vantage quotes and time series via `curl` |
| `notion-api` | Notion REST API operations |
| `parallel-deep-research` | Parallel deep research runs |
| `expand-new-ideas` | Expand `Research Ideas` from `Original Idea` to `Research Input` |
| `run-expanded-ideas-deep-research` | Start deep research for eligible expanded ideas |
| `poll-deep-research-runs` | Poll in-flight runs and sync summaries to Notion |
| `followup-tradable-tickers` | Parallel Task follow-up, validate ticker JSON, import `Trading Proposals` |
| `export-tv-watchlist` | Export watchlist locally and provision per-run Fast.io session with `watchlist.txt` |
| `create-tv-pine-screener` | Author Pine Screener scripts for Layer 2 price fields |
| `import-screener-pricing` | Import screener CSV Layer 2 fields from Fast.io into Notion |
| `fastio-cli` | Fast.io file ops; per-run sessions store `watchlist.txt` and `pinescreener*.csv` |
| `refresh-proposal-quotes` | Refresh `Last Price` and `Quote As Of` on `Trading Proposals` |
| `refresh-workspace` | Read-only workspace context refresh |

Tooling priority: **CLI > direct API via `curl` > MCP** (fallback).

## Authentication

Copy `env.sample` to `.env` locally. Supported variables:

- `ALPHAVANTAGE_API_KEY`, `NOTION_API_TOKEN`, `PARALLEL_API_KEY`
- `FASTIO_API_KEY`, `FASTIO_WORKSPACE_NAME`

Never commit `.env` or store secrets in tracked files.

## Data Policy

Keep sensitive financial data outside this workspace by default.

Do not store credentials, API keys, access tokens, seed phrases, account numbers, tax identifiers, identity documents, full statements, raw exports, or tax forms.

Before saving any data into the workspace, the assistant should summarize what will be saved, where it will be saved, and whether it may contain sensitive financial or personal information.

## Notion Portfolio Schema Plan

Portfolio planning lives in Notion. The schema targets a **single portfolio** with daily snapshot capture and **Portfolio Analysis**. Layer 3 schemas: [`data/notion/portfolio.md`](data/notion/portfolio.md).

The snapshot schema is at [`data/notion/portfolio.md`](data/notion/portfolio.md). The canonical `Trading Proposals` schema is in [`data/notion/research.md`](data/notion/research.md).

Databases (current):

- `Portfolio Snapshot`: one row per as-of date; **`Status = approved`** → **Approved Portfolio Snapshot**.
- `Portfolio Holdings`: holdings and cash for each snapshot — `Ticker`, quantity, market price/value, planned prices, optional `Average Cost`, optional `Source Proposal`.
- `Portfolio Policy`: guardrails — [`data/portfolio/guardrails.md`](data/portfolio/guardrails.md).

- `Portfolio Analysis`, `Target Portfolio Holdings`, `Rebalance Actions`: Layer 3 outputs — [`data/notion/portfolio.md`](data/notion/portfolio.md).

Out of scope:

- Multiple accounts, trade ledgers, cash movement ledgers, P&L trails, rebalance execution tracking.

Implementation notes:

- Use Notion `number` for quantities and money values.
- Use Notion `date` for snapshot as-of dates.
- Do not store credentials, account numbers, raw exports, tax documents, or full statements.
- Make Notion portfolio database structure changes only after explicit confirmation.

## Safety

The assistant must not place trades, move money, submit forms, open accounts, close accounts, change beneficiaries, or take irreversible financial actions.

All outputs should be treated as research and analysis support, not financial advice.