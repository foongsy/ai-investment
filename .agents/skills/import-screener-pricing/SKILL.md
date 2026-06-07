---
name: import-screener-pricing
description: Import Pine Screener CSV exports from a Fast.io Trading Proposals session into Notion Layer 2 price fields (Entry Price, Stop Price, Target Price, Reward Risk Ratio, Pricing Status). Writes to Notion by default. Use when screener results are uploaded to Fast.io, applying screener pricing, or completing Layer 2 for a research run. Updates rows where Pricing Status is not Ready. Use --dry-run to preview only.
disable-model-invocation: true
---

# Import Screener Pricing

Download Pine Screener CSV exports from a per-run Fast.io session and update Notion `Trading Proposals` Layer 2 price-plan fields.

This skill covers the **screener portion of Layer 2** per `data/notion/research.md`. It does **not** set `Last Price` or `Quote As Of` (use `refresh-proposal-quotes`) and does **not** change human review `Status`.

This is price-plan support only. Do not present imported prices as personalized investment advice.

## Fixed Defaults

- Scope: exactly **one** Parallel / Research `run_id` per invocation
- Default `run_id`: when `--run-id` is omitted, use the **most recently created** `Research Runs` row (Notion `created_time` descending) whose `Run ID` title is non-empty
- Fast.io session lookup: after `RUN_ID` is resolved, list `trading-proposals/sessions/` and match folders whose names end with `-<RUN_ID>` (format `<YYYY-MM-DD>-<RUN_ID>`)
- Multiple session folders for the same `RUN_ID`: use the folder with the **latest** `YYYY-MM-DD` date prefix (lexicographic compare); ignore all earlier dated folders
- Optional override: when `--date <YYYY-MM-DD>` is supplied, use the exact folder `<YYYY-MM-DD>-<RUN_ID>` instead of latest-date selection
- Selected session must contain at least one `pinescreener*.csv`; if not, **stop** and report the chosen session path. Do not fall back to earlier dated folders
- Screener file glob: all files in the selected session folder whose names match `pinescreener*.csv` (case-sensitive), including `pinescreener-*.csv` and `pinescreener_*.csv`
- Screener discovery: **folder list is authoritative**; `manifest.json` `files.screeners` is optional metadata only
- Import gate: update rows where `Pricing Status` is **not** `Ready` (includes `Not Started`, `Pending`, `Failed`, `Stale`)
- Screener row filter: include only rows where `Setup Active = 1` unless `--include-inactive`
- Notion fields written: `Entry Price`, `Stop Price`, `Target Price`, `Reward Risk Ratio`, `Pricing Notes`, `Pricing Status`
- Price rounding: round `Entry Price`, `Stop Price`, and `Target Price` to **3 decimal places** before validation, preview, and Notion write
- `Reward Risk Ratio`: always recompute from the **rounded** three prices and proposal `Trade Type`; ignore Pine CSV ratio except for optional divergence warnings
- Notion API version: `2025-09-03`
- TradingView symbol resolver: same rules as `export-tv-watchlist` (`symbol_search/v3`, 1 second between requests)
- Notion writes: **on by default** after a successful update plan; use `--dry-run` to preview only or `--confirm` to require explicit approval
- Duplicate symbols across screener files: **do not stop the run**; continue processing all files and rely on the `Pricing Status != Ready` gate

## Inputs

Provide at least one session selector:

- `--run-id <id>` — Parallel / Research run id (e.g. `trun_abc123`)
- When omitted, auto-select the latest created `Research Runs` row with a non-empty `Run ID`

Optional modifiers:

- `--date <YYYY-MM-DD>` — use the exact session folder `<YYYY-MM-DD>-<RUN_ID>` instead of latest-date selection among folders for the same `RUN_ID`
- `--screener-file <filename>` — process one named screener CSV in the session folder instead of all `pinescreener*.csv` files
- `--include-inactive` — include screener rows even when `Setup Active != 1`
- `--dry-run` — download, parse, join, validate, and preview only; never write Notion or Fast.io
- `--confirm` — show the preview and wait for explicit user confirmation before writing Notion (default is write without asking)

Deprecated (no longer required; default already writes):

- `--yes-update-pricing` — accepted as a no-op alias for backward compatibility

## Write Defaults

- **Default:** after a successful join, validation, and update plan, write Layer 2 fields to Notion without an extra confirmation gate.
- **`--dry-run`:** preview only; never write Notion or Fast.io manifest.
- **`--confirm`:** show the preview and wait for explicit user confirmation before writing.
- Stop instead of writing when:
  - `--dry-run` is set
  - `--confirm` is set and interactive confirmation is unavailable
  - required Notion properties are missing
  - no Fast.io session folder matches the resolved `RUN_ID`
  - the selected session has no screener CSV files
  - duplicate proposal matches require a user choice
  - every matched row fails validation (nothing valid to write)

## Steps

1. Load guidance:
   - Read `AGENTS.md`.
   - Read `.agents/skills/notion-api/SKILL.md`.
   - Read `.agents/skills/fastio-cli/SKILL.md`.
   - Read `.agents/skills/export-tv-watchlist/SKILL.md` (TradingView symbol resolution section).
   - Read `data/notion/research.md` (`Trading Proposals` Layer 2, Reward Risk Ratio, Pricing Status workflow).
   - Follow workspace safety and confirmation rules.

2. Validate auth and tools without exposing secrets:
   - Check `NOTION_API_TOKEN` from environment first, then `.env` if needed.
   - Check `FASTIO_API_KEY` and `FASTIO_WORKSPACE_NAME` from environment first, then `.env` if needed.
   - Confirm `fastio`, `curl`, and `jq` are available.
   - Do not print raw token values.

3. Resolve Notion data sources (read-only):
   - Search for `Research Runs` and `Trading Proposals` data sources (`Trade Proposals`, `Proposals` as fallbacks for proposals).
   - Retrieve each schema with `GET /v1/data_sources/{data_source_id}`.
   - Required `Research Runs` properties:
     - `Run ID` (title)
   - Required `Trading Proposals` properties:
     - `Proposal` (title)
     - `Ticker` (rich_text)
     - `Market` (select)
     - `Trade Type` (select)
     - `Run` (relation → `Research Runs`)
     - `Pricing Status` (select)
     - `Entry Price`, `Stop Price`, `Target Price`, `Reward Risk Ratio` (number)
     - `Pricing Notes` (rich_text)
   - Recommended for symbol resolution:
     - `Exchange` (rich_text)
     - `Asset Class` (select)
     - `Company Name` (rich_text)
   - Validate `Pricing Status` includes options `Not Started`, `Pending`, `Ready`, `Failed`, and `Stale`.
   - If required properties are missing, stop and report gaps. Do not alter schema automatically.

4. Resolve `run_id` and the matching `Research Runs` page:
   - Mirror `export-tv-watchlist` run resolution rules.
   - Capture matched `Research Runs` page ID as `RUN_PAGE_ID`.
   - Record whether `run_id` was supplied or auto-selected (`latest_created`).

5. Resolve and download Fast.io session files (read-only unless writing manifest in step 14):
   - Resolve workspace ID from `FASTIO_WORKSPACE_NAME`.
   - Resolve `trading-proposals/` and `sessions/` by folder name.
   - List all folders in `sessions/`.
   - Session selection:
     - If `--date` was supplied: require an exact folder named `${DATE}-${RUN_ID}`.
     - Otherwise: collect every folder whose name ends with `-${RUN_ID}` (equivalently matches `<YYYY-MM-DD>-<RUN_ID>`).
       - If zero matches: stop and report `run_id` and that no session folder was found.
       - If one match: use it.
       - If multiple matches: parse the `YYYY-MM-DD` prefix from each folder name, select the **latest** date lexicographically, and record all ignored earlier folders.
   - Set `SESSION_ID` to the selected folder name and `SESSION_DATE` to its parsed date prefix.
   - List the selected session folder contents.
   - Collect screener files:
     - default: every file with name matching `pinescreener*.csv`
     - with `--screener-file`: exactly that filename if present
   - If no screener files match in the **selected** session folder:
     - stop and report the selected `SESSION_ID`
     - report any ignored earlier session folders for the same `RUN_ID`
     - optionally note (informational only) if an ignored folder contains `pinescreener*.csv`; do **not** import from it
   - Sort screener filenames ascending for deterministic processing order.
   - Download each screener CSV to a temp/local path.
   - Optionally download `manifest.json` for reporting; do not require it for discovery.

6. Query linked `Trading Proposals`:
   - Query `Trading Proposals` with filter: `Run` relation **contains** `RUN_PAGE_ID`.
   - Paginate until all rows are collected.
   - For each row extract:
     - page ID
     - `Proposal` title
     - `Ticker`
     - `Market`
     - `Trade Type`
     - `Exchange`, `Asset Class`, `Company Name` when present
     - current `Pricing Status`
     - current Layer 2 prices and `Pricing Notes`
   - If no rows match, stop and report.

7. Resolve TradingView symbol for each proposal:
   - Reuse the resolver rules from `export-tv-watchlist` step 6.
   - Store `TV_ID` per proposal page ID.
   - Derive `CSV_SYMBOL` for join:
     - primary: symbol segment after `:` in `TV_ID`, case-insensitive (e.g. `NYSE:ANET` → `ANET`)
     - fallback when `TV_ID` has no `:`: use normalized proposal `Ticker`
   - Mark proposals with unresolved or ambiguous TV resolution as `join_failed`; they cannot receive screener pricing in this run.

8. Parse screener CSV files:
   - Read CSV with header row.
   - Resolve columns by **case-insensitive fuzzy match** on header names:
     - symbol column: exact `Symbol` preferred; otherwise first header equal to `Symbol` or ending with `:Symbol`
     - `Setup Active`
     - `Entry Price`
     - `Stop Price`
     - `Target Price`
     - `Reward Risk Ratio` (optional; importer recomputes)
   - Pine plot titles may appear verbatim (e.g. `Entry Price`) or with indicator prefixes; match when the header **contains** the canonical name.
   - For each data row:
     - trim symbol text
     - skip blank symbols
     - unless `--include-inactive`, skip rows where `Setup Active` is not active (`1`, `1.0`, `true`, case-insensitive)
     - parse the three price columns; all must be present and finite numbers > 0
   - Record source filename per parsed row.

   Reference shape from a real export:

   ```text
   Symbol,Description,Setup Active,New Setup,Entry Price,Stop Price,Target Price,Reward Risk Ratio,...
   ANET,"Arista Networks, Inc.",1,0,154.27,152.04,159.85,2.5,...
   ```

9. Join screener rows to proposals:
   - Process screener files in sorted filename order.
   - Maintain an in-memory update plan keyed by proposal page ID.
   - For each parsed screener row:
     - find candidate proposals where:
       - `Pricing Status` is not `Ready`
       - `CSV_SYMBOL` equals screener `Symbol` case-insensitively
       - TV resolution succeeded
     - if zero candidates: record `unmatched_screener_row`
     - if multiple candidates: stop **that row only** with `ambiguous_proposal_match` and continue; do not stop the run
     - if one candidate:
       - if the proposal is already in the update plan from an earlier screener file, **overwrite** the planned values (last file wins) and record `duplicate_symbol_overwritten`
       - otherwise add to the update plan
   - After building the plan, skip any proposal whose live `Pricing Status` is `Ready` (including rows that became `Ready` during execution in an earlier write pass).

10. Validate and compute derived fields:
    - Round parsed screener prices before validation and all downstream use:
      - `entry = round(entry, 3)`
      - `stop = round(stop, 3)`
      - `target = round(target, 3)`
    - For each planned update, using proposal `Trade Type` and the **rounded** prices:

| `Trade Type` | Risk | Reward | Valid price order |
| --- | --- | --- | --- |
| `long` | `entry - stop` | `target - entry` | `stop < entry < target` |
| `short` | `stop - entry` | `entry - target` | `target < entry < stop` |
| `other` | n/a | n/a | do not auto-set ratio |

    - If risk `<= 0`, price order is invalid, or `Trade Type = other`: mark row `validation_failed`, set planned `Pricing Status = Failed`, leave `Reward Risk Ratio` empty.
    - Otherwise set `Reward Risk Ratio = reward / risk` (round to 2 decimal places for the Notion write).
    - Optionally warn when CSV `Reward Risk Ratio` differs from recomputed value by more than `0.05`, but always write the recomputed value.
    - Build `Pricing Notes` by appending a short import note:
      - screener filename
      - import timestamp (UTC)
      - filter note (`Setup Active = 1` unless `--include-inactive`)
      - preserve existing `Pricing Notes` content when non-empty (append below a separator)

11. Build preview report before writes:
    - `run_id`, `run_id_source`, `SESSION_ID`, full session path, and any ignored earlier session folders
    - screener files processed
    - counts: proposals in run, importable proposals (`Pricing Status != Ready`), screener rows parsed, matched, unmatched screener rows, ambiguous matches, join failures, validation failures, duplicate overwrites, already-imported skips
    - per planned row table:
      - proposal title
      - ticker
      - market
      - `TV_ID`
      - screener symbol
      - screener filename
      - entry / stop / target (rounded to 3 dp)
      - recomputed RR
      - previous Layer 2 values
      - planned `Pricing Status`
      - page ID
      - action (`update`, `skip`, `failed`)

12. Notion write gate:
    - Show target data source name and ID.
    - Show exact rows and property values to update.
    - If `--dry-run`, stop here with the preview report.
    - If `--confirm`, ask for explicit confirmation before updating Notion.
    - Otherwise proceed to write Notion using the update plan (default).

13. Execute Notion updates:
    - Update each planned row sequentially with `PATCH /v1/pages/{page_id}`.
    - Write only (all prices rounded to 3 dp):
      - `Entry Price`
      - `Stop Price`
      - `Target Price`
      - `Reward Risk Ratio` when validation passed
      - `Pricing Notes`
      - `Pricing Status` (`Ready` on success, `Failed` on validation failure)
    - Re-check `Pricing Status != Ready` immediately before each patch; if `Ready`, skip and record `already_imported`.
    - Continue on per-row errors; collect failures.
    - Handle HTTP 429 with `Retry-After` backoff for Notion.

14. Fast.io manifest update (after successful Notion writes; skip when `--dry-run`):
    - Upload or update `manifest.json` in the session folder:
      - add processed screener filenames to `files.screeners`
      - set `status` to `imported`
      - add `imported_at` (UTC ISO timestamp)
      - add concise import summary counts
    - If manifest update fails, report it but do not roll back Notion writes.

15. Final report:
    - `run_id`, `run_id_source`, `SESSION_ID`, full session path, ignored earlier session folders, and matched `Research Runs` page ID
    - screener files processed
    - matched / updated / skipped / failed / unmatched counts
    - per-row outcomes
    - duplicate overwrite and already-imported skip details
    - whether writes used default auto-write, `--confirm`, or `--dry-run`
    - reminder: `Last Price` / `Quote As Of` come from `refresh-proposal-quotes`
    - reminder: re-import requires changing `Pricing Status` away from `Ready` manually in Notion (e.g. back to `Pending` or `Not Started`)

## Example Invocations

Import screener pricing for the latest run (writes to Notion by default):

```text
import-screener-pricing
```

Import for a specific run (session resolved by latest dated folder for that `run_id`):

```text
import-screener-pricing --run-id trun_abc123
```

Pin a specific session folder date instead of latest-date selection:

```text
import-screener-pricing --run-id trun_abc123 --date 2026-06-06
```

Preview without writes:

```text
import-screener-pricing --run-id trun_abc123 --dry-run
```

Require confirmation before writes:

```text
import-screener-pricing --run-id trun_abc123 --confirm
```

Import one screener file:

```text
import-screener-pricing --run-id trun_abc123 --screener-file pinescreener_Supertrend_EMA_ATR_Long_Plan_2026-06-06.csv
```

Include inactive screener rows (preview):

```text
import-screener-pricing --run-id trun_abc123 --include-inactive --dry-run
```

## Out of Scope

- Setting `Last Price`, `Quote As Of`, or `Instrument ID`
- Changing human review `Status`
- Creating or deleting `Trading Proposals` rows
- Overwriting rows whose `Pricing Status` is `Ready`
- Automated TradingView export or Pine Screener execution
- Portfolio sizing or trade execution
- Schema changes to Notion databases

## Related Skills

- `export-tv-watchlist` — creates the Fast.io session and watchlist for the same run
- `fastio-cli` — Fast.io folder resolution and file download
- `create-tv-pine-screener` — Pine plot contract that defines screener columns
- `refresh-proposal-quotes` — Alpha Vantage `Last Price` only
