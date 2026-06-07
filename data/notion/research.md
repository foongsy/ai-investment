# Notion Research Database Schema v2

Snapshot date: 2026-06-06

This document defines the database schema needed to reconstruct the Notion research system without copying any data. It includes database names, property names, property types, select options, relation setup, and rollup setup only.

## Scope

- Databases covered:
  - Research Ideas
  - Research Runs
  - Trading Proposals
- Excluded:
  - Page IDs, database IDs, data source IDs, property IDs, URLs, commands, prompts, raw rows, and workspace-specific artifacts.
- Trading Proposals follows a **two-layer model** (Layer 1 qualitative + Layer 2 price plan, 31 properties). Layer 1 import source: `data/parallel/output-tradable-tickers.json` (`ticker_opportunities[]` items).

## Research Ideas

Purpose: planning backlog and opportunity pipeline.

| Property | Type | Notes |
| --- | --- | --- |
| `Original Idea` | title | User-entered raw idea. Minimal input field. |
| `Idea ID` | unique_id | Stable generated identifier. Prefix: `RI`. |
| `Research Input` | rich_text | Expanded, research-ready prompt/input for execution. |
| `Status` | select | Lifecycle state. Current options: `New`, `Expanded`, `Queued`, `Running`, `Completed`. |
| `Active` | checkbox | Controls scheduler eligibility. |
| `Run Frequency` | select | Recurrence cadence. Current options: `Once`, `Daily`, `Weekly`, `Biweekly`, `Monthly`, `Quarterly`. |
| `Market Tags` | multi_select | Market scope labels. Current options: `HK`, `JP`, `US`, `CN`, `Global`. |
| `Asset Type Tags` | multi_select | Asset class labels. Current options: `Equity`, `ETF`, `Derivatives`, `Crypto`, `FX`. |
| `Strategy Tags` | multi_select | Strategy/theme labels. Current options: `Momentum`, `Contrarian`, `Macro`, `Flow`, `Event-driven`. |
| `Last Run ID` | rich_text | Most recent provider run ID linked to this idea. |
| `Last Run At` | date | Timestamp of latest completed run for this idea. |
| `Executive Summary` | rich_text | Latest summary synced back from the most recent completed run. |
| `Last Updated` | date | Workflow-maintained update timestamp, if used. |

## Research Runs

Purpose: execution log and audit trail for research runs. Each row represents one provider run event.

| Property | Type | Notes |
| --- | --- | --- |
| `Run ID` | title | Primary row identifier. Store the provider run ID, for example `trun_...`. |
| `Idea` | relation | Relation to Research Ideas. Each run should link to its source idea. |
| `Idea ID` | rollup | Rolls up Research Ideas `Idea ID` through the `Idea` relation. Function: `show_original`. |
| `Status` | select | Execution state. Current options: `Queued`, `Running`, `Completed`, `Failed`, `Cancelled`. |
| `Processor` | select | Provider processor tier. Current options: `lite`, `pro-fast`, `ultra-fast`, `ultra`. |
| `Started At` | date | Timestamp when run was submitted or started. |
| `Completed At` | date | Timestamp when run reached a terminal state. |
| `Result URL` | url | External result or monitoring URL for the provider run. |
| `Prompt Used` | rich_text | Exact prompt submitted for this run. |
| `Executive Summary` | rich_text | Run-level executive summary. |
| `Previous Interaction ID` | rich_text | Prior provider interaction ID supplied only for follow-up runs. Blank for first-pass runs. |
| `Error Message` | rich_text | Failure or cancellation details. |

### Research Runs Relation And Rollup

- `Research Runs.Idea`
  - Type: relation
  - Target: Research Ideas
- `Research Runs.Idea ID`
  - Type: rollup
  - Relation property: `Idea`
  - Related property: `Idea ID`
  - Function: `show_original`

## Trading Proposals

Purpose: reviewable, price-enriched ticker-level trade plans linked to a research run and source idea. Each row represents a proposal or watchlist candidate for further user review, not an execution instruction.

### Ground Rules

- **In scope:** Layer 1 qualitative fields and Layer 2 price plan fields on `Trading Proposals` only.
- **Design rule:** Proposal rows store ticker-specific review and price-plan fields. Run-level and thesis-level context is accessed through linked `Run` and `Idea` relations, not duplicated on each proposal row.
- **Import source:** One Notion row represents one `ticker_opportunities[]` item (Layer 1 only).
- **Framing:** Trade-plan framing for human review and monitoring. Not automated trade execution.

### Two-Layer Model

| Layer | Purpose | Where stored |
| --- | --- | --- |
| Layer 1 | Qualitative hypothesis from research import | `Trading Proposals` — identity, rationale, watchpoints, invalidation |
| Layer 2 | Price plan | `Trading Proposals` — last close, entry, stop, target |

Handoffs:

1. Research follow-up imports Layer 1 fields.
2. Alpha Vantage last close populates `Last Price` and `Quote As Of`.
3. Pine Screener CSV import via `import-screener-pricing` populates `Entry Price`, `Stop Price`, `Target Price`, and derived `Reward Risk Ratio`, then sets `Pricing Status = Ready` for rows where `Pricing Status` is not already `Ready`. Fast.io session files must be named `pinescreener*.csv`.

Layer 2 stores **single** entry, stop, target prices, and one reward/risk ratio. Portfolio sizing and execution history are defined separately.

### Migration from v1 (35-field table)

The prior v1 `Trading Proposals` schema (2026-05-03) defined 35 properties. The target schema removes run/thesis duplication, consolidates related review fields, and keeps high-value per-ticker fields.

#### Removed — Run / Thesis Context (Do Not Store On Proposals)

These fields existed on the v1 `Trading Proposals` table. They are removed from proposals. Access them through existing linked run/idea pages and external result URLs.

| Removed property | Original JSON / purpose | Where context lives instead |
| --- | --- | --- |
| `Schema Version` | `schema_version` | Linked `Research Runs` row and/or local result files |
| `Previous Interaction ID` | follow-up context | Linked `Research Runs.Previous Interaction ID` (unchanged) |
| `Core Thesis` | `thesis_snapshot.core_thesis` | Linked `Research Ideas` / run summary |
| `Key Drivers` | `thesis_snapshot.key_drivers[]` | Linked `Research Ideas` / run summary |
| `Key Risks` | `thesis_snapshot.key_risks[]` | Linked `Research Ideas` / run summary |
| `Thesis Kill Criteria` | `thesis_snapshot.thesis_kill_criteria[]` | Linked `Research Ideas` / run summary |
| `Fact Assumption Boundary` | `output_quality.fact_assumption_boundary` | Run summary / external result |
| `Missing Information` | `output_quality.missing_information[]` | Run summary / external result |
| `Uncertainty Notes` | `output_quality.uncertainty_notes[]` | Run summary / external result |

#### Removed — Consolidated Into Fewer Proposal Fields

| Removed property | Replaced by | Notes |
| --- | --- | --- |
| `Entry Criteria` | `Watchpoints` | Section 1 in sectioned bullet-join |
| `Monitoring Signals` | `Watchpoints` | Section 2 |
| `Open Questions` | `Watchpoints` | Section 3 |
| `Exit Criteria` | `Invalidation` | Bullet list after invalidation event |
| `Key Invalidation Event` | `Invalidation` | Leading text before exit bullets |
| `Conviction Level` | `Conviction` | Renamed; same select options |

#### Removed — Low-Value Per-Ticker Duplication

| Removed property | Notes |
| --- | --- |
| `Other Trade Type` | When `Trade Type` is `other`, fold clarification into `Rationale` |
| `Conviction Score` | Optional numeric score; not needed for proposal review queue |
| `Conviction Note` | Fold into `Rationale` or `Review Notes` at import time if needed |

#### Kept From v1

| Property | Reason |
| --- | --- |
| `Exchange` | Per-ticker venue; not recoverable from run-level fields |
| `Currency` | Per-ticker quote/trading currency |
| `Risk Bucket` | Per-ticker classification; useful for Notion filtering |

### Target Schema

**Property count:** 31 (21 Layer 1 + 1 workflow + 7 Layer 2 pricing + `Run` / `Idea` relations)

#### Layer 1 — Qualitative

| Property | Type | Notes |
| --- | --- | --- |
| `Proposal` | title | Human-readable label, typically `<ticker> <trade_type>`. |
| `Ticker` | rich_text | Tradable symbol or instrument identifier from research. |
| `Instrument ID` | rich_text | Broker-validated symbol; may be filled during review. |
| `Company Name` | rich_text | Company, ETF, asset, or instrument name. |
| `Market` | select | `HK`, `JP`, `US`, `OTHER`. |
| `Asset Class` | select | `equity`, `etf`, `bond`, `future`, `option`, `crypto`, `other`. |
| `Exchange` | rich_text | Trading venue or exchange. |
| `Currency` | rich_text | Trading or quote currency. |
| `Intent` | select | `Trade`, `Watchlist`, `Hedge`. |
| `Trade Type` | select | `long`, `short`, `other`. |
| `Time Horizon` | select | `near_term`, `medium_term`, `long_term`, `event_driven`, `unspecified`. |
| `Conviction` | select | `low`, `medium`, `high`. |
| `Risk Bucket` | select | `fundamental`, `event_driven`, `macro_sensitive`, `policy_sensitive`, `supply_chain`, `other`. |
| `Relationship To Research` | rich_text | Free-text causal link to the source thesis. |
| `Rationale` | rich_text | Core research hypothesis and reasoning. Include `other_trade_type` text when applicable. |
| `Invalidation` | rich_text | Main thesis-break event and exit or downgrade logic. |
| `Assumptions` | rich_text | Key assumptions behind the proposal. |
| `Watchpoints` | rich_text | Entry triggers, monitoring signals, and open questions. |
| `Status` | select | Human review state. `Proposed`, `Reviewing`, `Accepted`, `Rejected`, `Archived`. |
| `Proposed At` | date | Timestamp when imported or created. |
| `Run` | relation | Relation to Research Runs. |
| `Idea` | relation | Relation to Research Ideas. |
| `Review Notes` | rich_text | User notes during review. |

#### Workflow Status

| Property | Type | Notes |
| --- | --- | --- |
| `Pricing Status` | select | Layer 2 readiness. `Not Started`, `Pending`, `Ready`, `Failed`, `Stale`. |

#### Layer 2 — Price Plan

| Property | Type | Source | Notes |
| --- | --- | --- | --- |
| `Quote As Of` | date | Alpha Vantage | Last-close date. |
| `Last Price` | number | Alpha Vantage | Last close in quote currency. |
| `Entry Price` | number | External process | Single planned entry price. |
| `Stop Price` | number | External process | Hard invalidation price. |
| `Target Price` | number | External process | Single take-profit price. |
| `Reward Risk Ratio` | number | External process (derived) | Reward per unit divided by risk per unit. See **Reward Risk Ratio** below. |
| `Pricing Notes` | rich_text | External process | Entry style, liquidity, catalyst, or zone context. |

Per-unit risk and per-unit reward are **not stored** separately. Use `Reward Risk Ratio` for review, filtering, and sorting.

#### Reward Risk Ratio

Definition: **reward per unit ÷ risk per unit** (not risk:reward inverted). Example: ratio `2.5` means 2.5 units of reward for 1 unit of risk (often described as “1:2.5”).

Compute from `Trade Type`, `Entry Price`, `Stop Price`, and `Target Price`:

| `Trade Type` | Risk per unit | Reward per unit | `Reward Risk Ratio` |
| --- | --- | --- | --- |
| `long` | `Entry Price − Stop Price` | `Target Price − Entry Price` | `reward ÷ risk` |
| `short` | `Stop Price − Entry Price` | `Entry Price − Target Price` | `reward ÷ risk` |
| `other` | n/a | n/a | leave empty unless user overrides in `Pricing Notes` |

Validation (external process should enforce before `Pricing Status = Ready`):

- Denominator must be **> 0**; otherwise leave `Reward Risk Ratio` empty and prefer `Pricing Status = Failed`.
- For `long`, expect `Stop Price < Entry Price < Target Price`.
- For `short`, expect `Target Price < Entry Price < Stop Price`.
- Store as a plain number (Notion `number`); two decimal places is typical.

Population rule: the external process **must derive** `Reward Risk Ratio` from the three prices on every price-plan write. If Pine Script also outputs a ratio, the importer should recompute from prices and treat that as source of truth (optionally warn when Pine value diverges beyond a small tolerance).

Recompute when `Entry Price`, `Stop Price`, or `Target Price` changes. A large move against the plan may set `Pricing Status = Stale`; refresh prices and ratio together.

#### Trading Proposals Relations

- `Trading Proposals.Run`
  - Type: relation
  - Target: Research Runs
- `Trading Proposals.Idea`
  - Type: relation
  - Target: Research Ideas

### Status Workflow

Keep human decision workflow (`Status`) separate from Layer 2 readiness (`Pricing Status`).

| Stage | Status | Pricing Status |
| --- | --- | --- |
| Layer 1 import | `Proposed` | `Not Started` |
| Human review | `Reviewing` | unchanged |
| Accepted for pricing | `Accepted` | `Pending` |
| Alpha Vantage last close | unchanged | unchanged |
| External price plan complete | unchanged | `Ready` |
| Plan expired or large price move | unchanged | `Stale` |

### Layer 2 Data Sources

| Field group | Source | Tool / process |
| --- | --- | --- |
| `Last Price`, `Quote As Of` | Alpha Vantage last close | `alphavantage-curl` skill |
| `Entry Price`, `Stop Price`, `Target Price`, `Reward Risk Ratio`, `Pricing Notes` | Pine Screener CSV via Fast.io (`pinescreener*.csv` in run session) | `import-screener-pricing` skill; derives ratio from prices; sets `Pricing Status = Ready` when current status is not `Ready` |

Layer 2 is **not** imported from `data/parallel/output-tradable-tickers.json`.

### JSON Import Mapping (Layer 1 Only)

For each `ticker_opportunities[]` item:

| Notion property | JSON path | Transform |
| --- | --- | --- |
| `Proposal` | `ticker`, `trade_hypothesis.trade_type` | `"<ticker> <trade_type>"` |
| `Ticker` | `ticker` | direct |
| `Company Name` | `company_name` | direct |
| `Market` | `market` | direct |
| `Asset Class` | `asset_class` | direct |
| `Exchange` | `exchange` | direct |
| `Currency` | `currency` | direct |
| `Trade Type` | `trade_hypothesis.trade_type` | direct |
| `Time Horizon` | `trade_hypothesis.time_horizon` | direct |
| `Conviction` | `trade_hypothesis.conviction_level` | direct |
| `Risk Bucket` | `trade_hypothesis.risk_bucket` | direct |
| `Relationship To Research` | `relationship_to_research` | direct |
| `Rationale` | `trade_hypothesis.rationale`, `trade_hypothesis.other_trade_type` | rationale first; append other trade type when non-null |
| `Invalidation` | `trade_hypothesis.key_invalidation_event`, `trade_hypothesis.exit_criteria[]` | invalidation first, then bullet exits |
| `Assumptions` | `assumptions[]` | bullet-join |
| `Watchpoints` | `trade_hypothesis.entry_criteria[]`, `monitoring_signals[]`, `open_questions[]` | sectioned bullet-join |
| `Status` | n/a | `Proposed` |
| `Pricing Status` | n/a | `Not Started` |
| `Proposed At` | n/a | current UTC timestamp |
| `Run` | n/a | relation to follow-up run page |
| `Idea` | n/a | relation to source idea page |

Do **not** import these JSON sections onto proposal rows: `schema_version`, `analysis_context.*`, `thesis_snapshot.*`, `output_quality.*`.

If `ticker_opportunities` is empty, create no proposal rows. Record gaps through the linked run workflow using existing `Research Runs` fields and external result files.

## Reconstruction Order

### Research Ideas

1. Create a database named `Research Ideas`.
2. Add the `Research Ideas` properties listed above.
3. Configure `Research Ideas.Idea ID` as a unique ID with prefix `RI`.

### Research Runs

4. Create a database named `Research Runs`.
5. Add the non-relation `Research Runs` properties listed above.
6. Add `Research Runs.Idea` as a relation to `Research Ideas`.
7. Add `Research Runs.Idea ID` as a rollup:
   - Relation property: `Idea`
   - Related property: `Idea ID`
   - Function: `show_original`

### Trading Proposals

8. Ensure `Research Ideas` and `Research Runs` already exist (no changes required).
9. Open or create the `Trading Proposals` database.
10. Remove obsolete v1 properties listed in **Removed** sections above, if present.
11. Add or rename Layer 1 qualitative properties listed above.
12. Add workflow properties: `Instrument ID`, `Intent`, `Pricing Status`.
13. Add Layer 2 price-plan properties listed above, including `Reward Risk Ratio`.
14. Configure all select options exactly as listed.
15. Confirm `Trading Proposals.Run` relation to `Research Runs`.
16. Confirm `Trading Proposals.Idea` relation to `Research Ideas`.
