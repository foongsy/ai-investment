---
name: export-tv-watchlist
description: Export Trading Proposals for one Research Run to a TradingView watchlist .txt file, provision a per-run Fast.io session folder, and upload watchlist.txt. Resolves tickers to EXCHANGE:SYMBOL via TradingView symbol_search/v3. Use when exporting proposals to TV watchlist or generating YYYY-MM-DD-runid.txt files.
disable-model-invocation: true
---

# Export TV Watchlist

Export all `Trading Proposals` linked to one `Research Runs` row into a TradingView watchlist `.txt` file.

This skill is **read-only for Notion**. It writes one local watchlist file and, by default, provisions a per-run Fast.io session folder with `watchlist.txt` and `manifest.json`. It always resolves TV symbols from proposal fields via TradingView `symbol_search/v3`; it does not read or trust any pre-existing TV symbol on proposal rows.

## Fixed Defaults

- Scope: exactly **one** Parallel / Research `run_id` per invocation
- Default `run_id`: when `--run-id` is omitted, use the **most recently created** `Research Runs` row (Notion `created_time` descending) whose `Run ID` title is non-empty
- Notion selector: `Trading Proposals` where `Run` relation points to the matching `Research Runs` page
- TV resolver: `GET https://symbol-search.tradingview.com/symbol_search/v3/`
- Resolver headers (required to avoid 403):
  - `Origin: https://www.tradingview.com`
  - `Referer: https://www.tradingview.com/`
  - browser-like `User-Agent`
- Rate limit: sleep **1 second** between TradingView symbol-search requests
- Notion API version: `2025-09-03`
- Output directory: `data/tradingview/`
- Output filename: `YYYY-MM-DD-<run_id>.txt` where `<run_id>` is the resolved run id verbatim (e.g. `trun_abc123`)
- Local watchlist files are **gitignored** (`data/tradingview/*.txt`); do not commit them. Fast.io `watchlist.txt` is the durable per-run copy when Fast.io upload is enabled.
- Watchlist sections: `###HK`, `###JP`, `###US`, `###OTHER` by proposal `Market`
- No scanner / validator step after resolve
- No Notion writes
- Fast.io session path: `trading-proposals/sessions/<EXPORT_DATE>-<RUN_ID>/`
- Fast.io watchlist filename: `watchlist.txt` (local file keeps `YYYY-MM-DD-<run_id>.txt`)
- Fast.io enabled by default; use `--no-fastio` to skip cloud provisioning

## Inputs

All inputs are optional.

- `--run-id <id>` — Parallel / Research run id (e.g. `trun_abc123`). Used to find the linked `Research Runs` row and to name the output file. When omitted, auto-select the latest created `Research Runs` row with a non-empty `Run ID`.
- `--date <YYYY-MM-DD>` — override export date used in the filename; default is the local calendar date when the skill runs
- `--output-dir <path>` — override output directory; default `data/tradingview/`
- `--dry-run` — resolve symbols and preview the watchlist and planned Fast.io session; do not write the local `.txt` file or call Fast.io
- `--no-fastio` — skip Fast.io session provisioning and upload; local file write only

## Steps

1. Load guidance:
   - Read `AGENTS.md`.
   - Read `.agents/skills/notion-api/SKILL.md`.
   - Read `data/notion/research.md` (`Trading Proposals` and `Research Runs` sections).
   - Follow workspace safety rules.

2. Validate auth and tools without exposing secrets:
   - Check `NOTION_API_TOKEN` from environment first, then `.env` if needed.
   - Unless `--no-fastio`, also check `FASTIO_API_KEY` and `FASTIO_WORKSPACE_NAME`; confirm `fastio` CLI is available.
   - Confirm `curl` and `jq` are available.
   - Do not print raw token values.

3. Resolve Notion data sources (read-only):
   - Search for `Research Runs` data source.
   - Search for `Trading Proposals` data source (fallback: `Trade Proposals`, `Proposals`).
   - Retrieve each schema with `GET /v1/data_sources/{data_source_id}`.
   - Required `Research Runs` properties:
     - `Run ID` (title)
   - Required `Trading Proposals` properties:
     - `Proposal` (title)
     - `Ticker` (rich_text)
     - `Market` (select)
     - `Run` (relation → `Research Runs`)
   - Recommended `Trading Proposals` properties for better resolve quality:
     - `Exchange` (rich_text)
     - `Asset Class` (select)
     - `Company Name` (rich_text)
   - If required properties are missing, stop and report gaps. Do not alter schema automatically.

4. Resolve `run_id` and the matching `Research Runs` page:
   - If `--run-id` was supplied:
     - Set `RUN_ID` to the supplied value.
     - Query `Research Runs` with filter: `Run ID` title equals `RUN_ID`.
     - If zero matches, stop and report `run_id not found`.
     - If multiple matches, stop and ask the user to disambiguate by page ID.
   - If `--run-id` was **not** supplied:
     - Query `Research Runs` with:
       - filter: `Run ID` title is not empty
       - sort: `created_time` descending
       - `page_size`: 1
     - If zero matches, stop and report no `Research Runs` rows with a `Run ID`.
     - Take the single returned row; set `RUN_ID` from its `Run ID` title.
     - Record `run_id_source = latest_created` for the final report.
   - Capture the matched `Research Runs` page ID as `RUN_PAGE_ID`.

5. Query linked `Trading Proposals`:
   - Query `Trading Proposals` with filter: `Run` relation **contains** `RUN_PAGE_ID`.
   - Paginate until all rows are collected.
   - For each row extract:
     - page ID
     - `Proposal` title
     - `Ticker`
     - `Market`
     - `Exchange` (if present)
     - `Asset Class` (if present)
     - `Company Name` (if present)
   - If no rows match, stop and report that the run has no linked proposals.

6. Resolve TradingView symbol for each proposal (always resolve):
   - Ignore any stored instrument / broker symbol fields; always call TradingView search.
   - Trim whitespace from `Ticker`.
   - Build search parameters from proposal fields:

| `Market` | `text` normalization | `exchange` param | extra params |
| --- | --- | --- | --- |
| `HK` | strip `.HK`; if all digits, remove leading zeros | `HKEX` | `search_type=stock` |
| `JP` | strip `.T` suffix | `TSE` | `search_type=stock`, `country=JP` |
| `US` | use ticker as-is | map from `Exchange` when it contains `NASDAQ`, `NYSE`, or `AMEX`; otherwise omit | `search_type` from asset class, `country=US`, `sort_by_country=US` |
| `OTHER` | use ticker as-is | map from `Exchange` when recognizable; otherwise omit | `search_type` from asset class |

   - `search_type` mapping from `Asset Class`:
     - `equity` → `stock`
     - `etf` → `etf`
     - `crypto` → `crypto`
     - default → `stock`
   - `Exchange` → TV `exchange` param (case-insensitive substring match):

| If `Exchange` contains | TV `exchange` param |
| --- | --- |
| `NASDAQ` | `NASDAQ` |
| `NYSE` | `NYSE` |
| `AMEX` | `AMEX` |
| `HKEX`, `HONG KONG` | `HKEX` |
| `TSE`, `TOKYO` | `TSE` |

   - Primary search call:

```bash
curl -sG "https://symbol-search.tradingview.com/symbol_search/v3/" \
  -H "Origin: https://www.tradingview.com" \
  -H "Referer: https://www.tradingview.com/" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  --data-urlencode "text=${SEARCH_TEXT}" \
  --data-urlencode "exchange=${TV_EXCHANGE}" \
  --data-urlencode "lang=en" \
  --data-urlencode "search_type=${SEARCH_TYPE}" \
  --data-urlencode "country=${COUNTRY}" \
  --data-urlencode "sort_by_country=${COUNTRY}" \
  --data-urlencode "domain=production"
```

   - Omit `exchange`, `country`, and `sort_by_country` query params when not applicable instead of sending empty values.
   - Parse response envelope: `.symbols[]` (ignore `.symbols_remaining` unless debugging).
   - Build TV id per hit:

```text
# per symbol hit s:
# if s.prefix is non-empty: TV_ID = "${s.prefix}:${s.symbol}"
# else: TV_ID = "$(first token of s.exchange, uppercased):${s.symbol}"
```

   - Rank hits and pick one `TV_ID`:
     - `+10` if hit `prefix` or exchange token matches expected exchange for the proposal market
     - `+10` if hit `symbol` equals normalized search text (case-insensitive)
     - `+5` if hit `type` aligns with `Asset Class` / `search_type`
     - `+3` if `description` loosely matches `Company Name` when company name is present
     - `+5` if `country` aligns with proposal `Market`
   - If the best score is below **10**, or the top two scores tie within **3**, mark row `ambiguous` and do not include it in the watchlist.
   - If `.symbols` is empty or the HTTP call fails, retry once using `Company Name` as `text` (same exchange/country params) when company name is non-empty.
   - If still unresolved, mark row `failed`.
   - Sleep 1 second before the next TradingView request.

7. Build watchlist content:
   - Group resolved `TV_ID` values by proposal `Market` in this order: `HK`, `JP`, `US`, `OTHER`.
   - Within each section, sort tickers alphabetically by `TV_ID` and deduplicate exact duplicates.
   - Format:

```text
###HK
HKEX:700
HKEX:9988

###US
NASDAQ:NVDA
```

   - Use the literal section headers `###HK`, `###JP`, `###US`, `###OTHER` even when a section has only one symbol.
   - Omit empty sections entirely.
   - Do not include unresolved or ambiguous rows in the `.txt` file.

8. Write output file:
   - Ensure output directory exists (default `data/tradingview/`).
   - Filename: `${EXPORT_DATE}-${RUN_ID}.txt`
     - `EXPORT_DATE` = `--date` or local `YYYY-MM-DD`
     - `RUN_ID` = resolved run id (supplied or auto-selected) verbatim
   - Example: `data/tradingview/2026-06-06-trun_abc123.txt`
   - If the target file already exists and this is not `--dry-run`, stop and ask whether to overwrite. Do not overwrite without explicit confirmation.
   - If `--dry-run`, show the full planned file contents and path; do not write.

9. Provision Fast.io session (skip when `--no-fastio` or `--dry-run`):
   - Read `.agents/skills/fastio-cli/SKILL.md`.
   - Load Fast.io env: `set -a && [ -f .env ] && . ./.env && set +a`
   - Resolve workspace ID from `FASTIO_WORKSPACE_NAME`.
   - Resolve or create `trading-proposals/` and `sessions/` by folder name.
   - Set `SESSION_ID` = `${EXPORT_DATE}-${RUN_ID}` (same date and run id as the local filename).
   - Set `SESSION_PATH` = `trading-proposals/sessions/${SESSION_ID}/`
   - List `sessions/` for an existing folder named `SESSION_ID`.
   - If the session folder exists and already contains `watchlist.txt`, stop and ask whether to overwrite. Do not overwrite without explicit confirmation.
   - Create the session folder when absent:

```bash
fastio files create-folder --workspace "$WS_ID" \
  --parent "$SESSIONS_ID" \
  "$SESSION_ID" \
  --format json
```

   - Upload the local watchlist content as `watchlist.txt`:

```bash
fastio upload file --workspace "$WS_ID" \
  --folder "$SESSION_FOLDER_ID" \
  "${LOCAL_WATCHLIST_PATH}" --format json
```

   - Upload or update `manifest.json` with minimum fields:

```json
{
  "session_id": "2026-06-06-trun_abc123",
  "run_id": "trun_abc123",
  "created_at": "2026-06-06",
  "status": "watchlist_exported",
  "files": {
    "watchlist": "watchlist.txt",
    "screeners": []
  },
  "local_source": "data/tradingview/2026-06-06-trun_abc123.txt"
}
```

   - When updating an existing manifest, preserve any existing `files.screeners` entries (filenames matching `pinescreener*.csv`).
   - If `--dry-run`, report planned `SESSION_PATH`, upload targets, and manifest payload only; do not call Fast.io.

10. Final report:
   - `run_id`, whether it was supplied or auto-selected (`latest_created`), and matched `Research Runs` page ID
   - local output path (or planned path for `--dry-run`)
   - Fast.io session path and upload status (or planned actions for `--dry-run` / skipped for `--no-fastio`)
   - manifest `status`
   - proposals matched / resolved / ambiguous / failed
   - per-row table:
     - proposal title
     - ticker
     - market
     - resolved `TV_ID` or failure reason
     - page ID
   - list of `TV_ID` values written (or that would be written)
   - reminder: import `watchlist.txt` in TradingView via watchlist → Upload list (use the local file or download from Fast.io)
   - reminder: after Pine Screener, upload any `pinescreener*.csv` to the same Fast.io session folder
   - reminder: unresolved rows need manual TV symbol review before re-export

## Example Invocations

```text
export-tv-watchlist
```

Auto-select the latest created `Research Runs` row and export its proposals.

```text
export-tv-watchlist --run-id trun_abc123
```

```text
export-tv-watchlist --run-id trun_abc123 --dry-run
```

```text
export-tv-watchlist --run-id trun_abc123 --date 2026-06-06
```

```text
export-tv-watchlist --run-id trun_abc123 --no-fastio
```

Local watchlist only; skip Fast.io provisioning.

## Out of Scope

- Notion writes (including `Instrument ID` TV cache)
- Scanner / post-resolve validation
- Using pre-existing TV symbols without lookup
- Multi-run batch export in one file
- Layer 2 pricing fields
- TradingView watchlist upload automation
- Per-script Fast.io subfolders (`<script-slug>` in session path)
- Inferring Pine script identity from screener filenames
