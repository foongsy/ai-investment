---
name: followup-tradable-tickers
description: Run a Parallel follow-up from a provided run_id/interaction_id, validate ticker JSON with ajv-cli, create a linked Research Runs row, and import validated opportunities into Trade Proposals after confirmation.
disable-model-invocation: true
---

# Follow-up Tradable Tickers

Run a follow-up research task against an existing Parallel `interaction_id` or `run_id`, generate structured tradable ticker proposals, save local result files, validate output with `ajv-cli`, populate Notion `Research Runs`, and import validated rows into Notion `Trade Proposals`.

This workflow has fixed defaults so it can run without design questions:

- Treat a supplied `trun_...` as both a possible run ID and interaction ID. Verify with `parallel-cli research status <id> --json`; if the returned `interaction_id` exists, use it, otherwise use the supplied ID.
- Use Parallel processor `lite` for the follow-up because previous research context is supplied through `--previous-interaction-id`.
- Use `npx --yes ajv-cli validate --spec=draft2020 --all-errors --errors=text` for schema validation.
- Remember that the Parallel poll `.json` file is metadata. The ticker payload is normally in the poll `.md` content file referenced by `output.content_file`; extract the JSON object from that `.md` and validate the extracted JSON.
- Import validated `ticker_opportunities[]` into `Trade Proposals` after the Research Runs row is created and after a separate confirmation gate.
- Never infer confirmation from Cloud Agent, background execution, or non-interactive execution alone. Only skip a confirmation gate when the original user request includes the matching explicit flag below.

## Inputs

- `interaction_id` or `run_id`: Required. The user may provide a `trun_...`; resolve it with `parallel-cli research status`.
- Optional auto-confirm flags:
  - `--yes-start-research`: Treat as explicit confirmation for starting the external Parallel follow-up run.
  - `--yes-create-research-run`: Treat as explicit confirmation for creating the linked Notion `Research Runs` row.
  - `--yes-create-trade-proposals`: Treat as explicit confirmation for creating Notion `Trade Proposals` rows from validated output.
- Optional source context if needed:
  - source `Research Runs` page ID
  - source `Research Ideas` page ID
  - idea title or enough information to identify the related idea

## Auto-Confirm Rules

- Auto-confirm flags must be present in the user's original skill invocation or latest explicit instruction for this run. Do not assume them from context, Cloud Agent mode, background execution, or prior unrelated approvals.
- Each flag only applies to its matching gate:
  - `--yes-start-research` applies only to external Parallel research kickoff.
  - `--yes-create-research-run` applies only to creating the Notion `Research Runs` row.
  - `--yes-create-trade-proposals` applies only to creating Notion `Trade Proposals` rows.
- If a flag is absent and interactive confirmation is unavailable, stop at that gate and report the prepared preview.
- Even with flags, stop instead of writing if validation fails, required Notion schema fields are missing, select values are unavailable, the related idea cannot be resolved, or duplicate proposal rows require a user choice.
- Do not use a blanket `--yes`; this skill intentionally requires scoped approvals.

## Steps

1. Load guidance and prompt sources:
   - Read `AGENTS.md`.
   - Read `.agents/skills/parallel-deep-research/SKILL.md`.
   - Read `.agents/skills/notion-api/SKILL.md`.
   - Read `data/prompt-followup-tradable-tickers.md`.
   - Read `data/schema-tradable-tickers-output.json`.
   - Follow workspace safety and confirmation rules.

2. Validate auth and tools without exposing secrets:
   - Check `PARALLEL_API_KEY` from environment first, then `.env` if needed.
   - Check `NOTION_API_TOKEN` from environment first, then `.env` if needed.
   - Confirm `parallel-cli` is available.
   - Confirm `jq` is available for shell JSON parsing.
   - Use `npx --yes ajv-cli ...` for validation; no project dependency is required.
   - Do not print raw token values.

3. Resolve the supplied Parallel ID:
   - Run:

```bash
parallel-cli research status "$INPUT_ID" --json
```

   - Extract:
     - `run_id`
     - `interaction_id`
     - `status`
     - result or monitoring URL if present
   - If `interaction_id` is present, use it as `INTERACTION_ID`.
   - If `interaction_id` is absent but the input is a `trun_...`, use the input as `INTERACTION_ID`.
   - If status lookup fails, continue only if the supplied ID is clearly intended as a prior Parallel interaction ID and Notion can resolve a matching source run.

4. Resolve the related Notion idea before writing:
   - Locate `Research Runs` and `Research Ideas` data sources.
   - Resolve schemas and property IDs.
   - Required `Research Runs` fields:
     - `Run ID` title
     - `Idea` relation to `Research Ideas`
     - `Status`
     - `Previous Interaction ID`
     - `Started At`
     - `Prompt Used`
   - Strongly recommended `Research Runs` fields:
     - `Completed At`
     - `Result URL`
     - `Executive Summary`
     - `Error Message`
     - `Result MD Path`
     - `Result JSON Path`
   - If a source run or idea is supplied, use it to resolve the `Idea` relation.
   - If only the Parallel ID is supplied, search `Research Runs` in this order:
     1. `Run ID` title equals the supplied ID.
     2. `Previous Interaction ID` equals the supplied ID.
     3. Any known stored interaction reference field, if present.
   - If the related idea cannot be resolved, stop and ask the user for the source `Research Runs` page or `Research Ideas` page. Do not create an unlinked run row.

5. Resolve `Trade Proposals` before running external research:
   - Locate the `Trade Proposals` data source.
   - Resolve property IDs by exact name.
   - Required `Trade Proposals` fields:
     - `Proposal` title
     - `Ticker` rich_text
     - `Company Name` rich_text
     - `Asset Class` select
     - `Market` select
     - `Exchange` rich_text
     - `Currency` rich_text
     - `Relationship To Research` rich_text
     - `Trade Type` select
     - `Time Horizon` select
     - `Rationale` rich_text
     - `Entry Criteria` rich_text
     - `Exit Criteria` rich_text
     - `Key Invalidation Event` rich_text
     - `Conviction Level` select
     - `Risk Bucket` select
     - `Assumptions` rich_text
     - `Open Questions` rich_text
     - `Monitoring Signals` rich_text
     - `Status` select
     - `Proposed At` date
     - `Run` relation
     - `Idea` relation
   - Optional but preferred `Trade Proposals` fields:
     - `Schema Version`
     - `Previous Interaction ID`
     - `Core Thesis`
     - `Key Drivers`
     - `Key Risks`
     - `Thesis Kill Criteria`
     - `Fact Assumption Boundary`
     - `Missing Information`
     - `Uncertainty Notes`
     - `Conviction Score`
     - `Conviction Note`
     - `Other Trade Type`
     - `Review Notes`
   - Do not alter the Notion schema inside this skill unless separately confirmed.

6. Build the follow-up prompt:
   - Use `data/prompt-followup-tradable-tickers.md` as the instruction source.
   - Include the resolved `INTERACTION_ID`.
   - Default `focus_markets` to `HK`, `JP`, and `US`.
   - Default `analysis_timeframe` to `mixed`.
   - Keep the prompt focused on producing JSON conforming to `data/schema-tradable-tickers-output.json`.
   - Do not provide personalized investment advice, position sizing, or trade execution instructions.

7. Confirmation gate before external research:
   - Summarize:
     - input ID and resolved `INTERACTION_ID`
     - resolved source idea/page
     - processor choice, default `lite`
     - that `--previous-interaction-id` will be used
     - intended output filenames
     - that `ajv-cli` will validate the extracted JSON before Notion proposal imports
   - If `--yes-start-research` was supplied, record that the gate was auto-confirmed by flag and continue.
   - Otherwise, ask for explicit confirmation before starting the Parallel follow-up run.

8. Start the follow-up research:
   - Use `lite` by default because the previous interaction supplies context.
   - Run:

```bash
parallel-cli research run "$FOLLOWUP_PROMPT" --processor lite --no-wait --json --previous-interaction-id "$INTERACTION_ID"
```

   - Capture:
     - new `run_id`
     - new `interaction_id` if returned
     - monitoring URL
     - started timestamp
   - Immediately report kickoff metadata to the user.

9. Poll and save result files:
   - Choose a lowercase kebab-case filename, for example:

```bash
followup-tradable-tickers-<short-interaction-id>
```

   - Poll:

```bash
parallel-cli research poll "$RUN_ID" -o "$FILENAME" --timeout 540
```

   - Expected outputs:
     - `$FILENAME.md`
     - `$FILENAME.json`
   - If the run is still in progress at timeout, report that it is still running and do not write terminal Notion status.

10. Extract and validate ticker JSON:
   - Treat `$FILENAME.json` as metadata, not the ticker payload.
   - Read `output.content_file` from `$FILENAME.json`; normally this is `$FILENAME.md`.
   - Extract the top-level JSON object from the content file and write it to a temp file:

```bash
/tmp/<filename>.extracted.json
```

   - Validate with `ajv-cli`:

```bash
npx --yes ajv-cli validate \
  --spec=draft2020 \
  --all-errors \
  --errors=text \
  -s data/schema-tradable-tickers-output.json \
  -d "/tmp/<filename>.extracted.json"
```

   - If validation fails, stop. Do not write `Trade Proposals`.
   - If validation passes, summarize:
     - schema version
     - ticker count
     - ticker list
     - markets
     - asset classes
     - `output_quality.fact_assumption_boundary`
     - missing information count
     - uncertainty notes count

11. Summarize output for Notion:
   - Create a concise `Executive Summary` for Notion:
     - number of ticker opportunities
     - markets and asset classes covered
     - highest-level uncertainty notes
     - location of local result files
   - Do not paste raw JSON payloads into Notion.

12. Prepare `Research Runs` write plan:
   - Create a new `Research Runs` row linked to the resolved `Research Ideas` page.
   - Populate fields when present:
     - `Run ID` = new follow-up `run_id`
     - `Idea` = resolved idea relation
     - `Status` = `Completed`, `Failed`, or `Running`
     - `Processor` = `lite` if the field exists
     - `Started At` = kickoff timestamp
     - `Completed At` = completion timestamp if terminal
     - `Result URL` = monitoring/result URL when available
     - `Prompt Used` = follow-up prompt submitted
     - `Executive Summary` = concise summary only
     - `Previous Interaction ID` = input `interaction_id`
     - `Error Message` = concise failure reason if failed
     - `Result MD Path` = local `.md` path if field exists
     - `Result JSON Path` = local `.json` path if field exists
   - Do not update the original source run row unless the user explicitly asks.
   - Do not alter Notion schema inside this skill unless separately confirmed.

13. Confirmation gate before `Research Runs` write:
   - Show target data source name and ID.
   - Show target idea page and ID.
   - Show the exact new row fields that will be created.
   - If `--yes-create-research-run` was supplied, record that the gate was auto-confirmed by flag and continue.
   - Otherwise, ask for explicit confirmation before creating the `Research Runs` row.

14. Execute `Research Runs` write after confirmation:
   - Use Notion REST API via `curl`.
   - Use property IDs for writes when available.
   - Handle errors gracefully and do not expose secrets.
   - Capture the created follow-up `Research Runs` page ID. This page ID is required for `Trade Proposals.Run` relations.

15. Prepare `Trade Proposals` import plan:
   - Query `Trade Proposals` for rows where `Run` relation contains the newly created follow-up `Research Runs` page ID.
   - If existing rows are found for this run, do not blindly duplicate them. Report existing count/tickers and ask whether to skip, append only missing tickers, or stop.
   - Default import mapping for each `ticker_opportunities[]` item:
     - `Proposal` title: `<ticker> <trade_type> - AI capex follow-up`
     - `Ticker`: `ticker`
     - `Company Name`: `company_name`
     - `Asset Class`: `asset_class`
     - `Market`: `market`
     - `Exchange`: `exchange`
     - `Currency`: `currency`
     - `Relationship To Research`: `relationship_to_research`
     - `Trade Type`: `trade_hypothesis.trade_type`
     - `Other Trade Type`: `trade_hypothesis.other_trade_type`
     - `Time Horizon`: `trade_hypothesis.time_horizon`
     - `Rationale`: `trade_hypothesis.rationale`
     - `Entry Criteria`: bullet-joined `trade_hypothesis.entry_criteria`
     - `Exit Criteria`: bullet-joined `trade_hypothesis.exit_criteria`
     - `Key Invalidation Event`: `trade_hypothesis.key_invalidation_event`
     - `Conviction Level`: `trade_hypothesis.conviction_level`
     - `Conviction Score`: `trade_hypothesis.conviction_score`
     - `Conviction Note`: `trade_hypothesis.conviction_note`
     - `Risk Bucket`: `trade_hypothesis.risk_bucket`
     - `Assumptions`: bullet-joined `assumptions`
     - `Open Questions`: bullet-joined `open_questions`
     - `Monitoring Signals`: bullet-joined `monitoring_signals`
     - `Schema Version`: `schema_version`
     - `Previous Interaction ID`: input/resolved previous `INTERACTION_ID`
     - `Core Thesis`: `thesis_snapshot.core_thesis`
     - `Key Drivers`: bullet-joined `thesis_snapshot.key_drivers`
     - `Key Risks`: bullet-joined `thesis_snapshot.key_risks`
     - `Thesis Kill Criteria`: bullet-joined `thesis_snapshot.thesis_kill_criteria`
     - `Fact Assumption Boundary`: `output_quality.fact_assumption_boundary`
     - `Missing Information`: bullet-joined `output_quality.missing_information`
     - `Uncertainty Notes`: bullet-joined `output_quality.uncertainty_notes`
     - `Status`: `Proposed`
     - `Proposed At`: current UTC timestamp
     - `Run`: relation to the newly created follow-up `Research Runs` page
     - `Idea`: relation to the resolved `Research Ideas` page
     - `Review Notes`: `Imported from ajv-cli-validated follow-up output. Research framing only, not personalized investment advice.`
   - Use Notion rich_text chunks below 2000 characters.
   - Validate that select values exist in the target schema before writing. If a select value is missing, stop and ask before changing schema or writing partial data.

16. Confirmation gate before `Trade Proposals` writes:
   - Show:
     - target `Trade Proposals` data source name and ID
     - follow-up `Research Runs` page ID
     - linked `Research Ideas` page ID
     - number of rows to create
     - ticker list
     - status value (`Proposed`)
     - exact high-level field mapping
   - If `--yes-create-trade-proposals` was supplied, record that the gate was auto-confirmed by flag and continue.
   - Otherwise, ask for explicit confirmation before creating `Trade Proposals` rows.

17. Execute `Trade Proposals` writes after confirmation:
   - Create one Notion page per ticker opportunity.
   - Process sequentially.
   - Continue on per-row errors and collect failures.
   - Do not update, archive, or delete existing proposal rows unless the user explicitly confirms that separate action.
   - After writes, query `Trade Proposals` by `Run` relation to verify created count and ticker list.

18. Final report:
   - Input ID and resolved previous `INTERACTION_ID`
   - New follow-up `run_id`
   - New follow-up `interaction_id` if returned
   - `ajv-cli` validation result
   - `Research Runs` row created/skipped/failed
   - `Trade Proposals` rows created/skipped/failed and ticker list
   - Which confirmation gates were interactive versus auto-confirmed by flags
   - Local result file paths
   - Concise error details for any failures
