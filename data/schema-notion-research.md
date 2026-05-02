# Notion Research Database Schema v1

Snapshot date: 2026-05-03

This document defines the database schema needed to reconstruct the Notion research system without copying any data. It includes database names, property names, property types, select options, relation setup, and rollup setup only.

## Scope

- Databases covered:
  - Research Ideas
  - Research Runs
  - Trading Proposals
- Excluded:
  - Page IDs, database IDs, data source IDs, property IDs, URLs, commands, prompts, raw rows, and workspace-specific artifacts.

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

Purpose: structured, reviewable trade hypotheses derived from research outputs. Each row represents a proposal or watchlist candidate for further user review, not an execution instruction.

| Property | Type | Notes |
| --- | --- | --- |
| `Proposal` | title | Human-readable proposal title, typically combining ticker, trade type, and research context. |
| `Ticker` | rich_text | Tradable symbol or instrument identifier. |
| `Company Name` | rich_text | Company, ETF, asset, or instrument name. |
| `Asset Class` | select | Current options: `equity`, `etf`, `bond`, `future`, `option`, `crypto`, `other`. |
| `Market` | select | Market scope. Current options: `HK`, `JP`, `US`, `OTHER`. |
| `Exchange` | rich_text | Trading venue or exchange. |
| `Currency` | rich_text | Trading or quote currency. |
| `Relationship To Research` | rich_text | Free-text explanation of how the proposal links to the source thesis. |
| `Trade Type` | select | Current options: `long`, `short`, `other`. |
| `Other Trade Type` | rich_text | Optional clarification when `Trade Type` is `other`, such as watchlist, hedge, or no-trade. |
| `Time Horizon` | select | Current options: `near_term`, `medium_term`, `long_term`, `event_driven`, `unspecified`. |
| `Rationale` | rich_text | Concise research hypothesis and reasoning. |
| `Entry Criteria` | rich_text | Observable criteria that would justify further review. Not position sizing or trade execution instructions. |
| `Exit Criteria` | rich_text | Observable criteria for closing, downgrading, or abandoning the proposal. |
| `Key Invalidation Event` | rich_text | Main event or evidence that would break the thesis. |
| `Conviction Level` | select | Current options: `low`, `medium`, `high`. |
| `Conviction Score` | number | Optional 0-1 score when available. |
| `Conviction Note` | rich_text | Explanation of conviction and uncertainty. |
| `Risk Bucket` | select | Current options: `fundamental`, `event_driven`, `macro_sensitive`, `policy_sensitive`, `supply_chain`, `other`. |
| `Assumptions` | rich_text | Key assumptions behind the proposal. |
| `Open Questions` | rich_text | Follow-up questions for diligence. |
| `Monitoring Signals` | rich_text | Signals to monitor for thesis validation or deterioration. |
| `Status` | select | Review state. Current options: `Proposed`, `Reviewing`, `Accepted`, `Rejected`, `Archived`. |
| `Proposed At` | date | Timestamp when the proposal was created or imported. |
| `Run` | relation | Relation to Research Runs. Each proposal should link to the run that generated it. |
| `Idea` | relation | Relation to Research Ideas. Each proposal should link to the source idea. |
| `Schema Version` | rich_text | Optional schema version from the structured output payload. |
| `Previous Interaction ID` | rich_text | Prior provider interaction ID used for follow-up context, when applicable. |
| `Core Thesis` | rich_text | Source thesis summary. |
| `Key Drivers` | rich_text | Source thesis drivers. |
| `Key Risks` | rich_text | Source thesis risks. |
| `Thesis Kill Criteria` | rich_text | Source thesis invalidation criteria. |
| `Fact Assumption Boundary` | select | Current options: `clear`, `mixed`, `weak`. |
| `Missing Information` | rich_text | Material missing inputs or evidence gaps. |
| `Uncertainty Notes` | rich_text | Output-level uncertainty notes. |
| `Review Notes` | rich_text | User or workflow notes during review. |

### Trading Proposals Relations

- `Trading Proposals.Run`
  - Type: relation
  - Target: Research Runs
- `Trading Proposals.Idea`
  - Type: relation
  - Target: Research Ideas

## Reconstruction Order

1. Create a database named `Research Ideas`.
2. Add the `Research Ideas` properties listed above.
3. Configure `Research Ideas.Idea ID` as a unique ID with prefix `RI`.
4. Create a database named `Research Runs`.
5. Add the non-relation `Research Runs` properties listed above.
6. Add `Research Runs.Idea` as a relation to `Research Ideas`.
7. Add `Research Runs.Idea ID` as a rollup:
   - Relation property: `Idea`
   - Related property: `Idea ID`
   - Function: `show_original`
8. Create a database named `Trading Proposals`.
9. Add the non-relation `Trading Proposals` properties listed above.
10. Add `Trading Proposals.Run` as a relation to `Research Runs`.
11. Add `Trading Proposals.Idea` as a relation to `Research Ideas`.

