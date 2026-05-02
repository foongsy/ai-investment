---
name: alphavantage-curl
description: Query Alpha Vantage market data with curl. Use when the user asks for Alpha Vantage, Core Stock API, stock time series, quotes, symbol search, listing status, or Index Data API lookups using curl.
disable-model-invocation: true
---

# Alpha Vantage Curl

Use this skill to query Alpha Vantage with `curl`, focused on Core Stock API and Index Data API workflows.

This skill is for data retrieval and research support only. Do not present retrieved data as personalized investment advice.

## Scope

Supported initial scope:

- Core Stock API:
  - `TIME_SERIES_INTRADAY`
  - `TIME_SERIES_DAILY`
  - `TIME_SERIES_DAILY_ADJUSTED`
  - `TIME_SERIES_WEEKLY`
  - `TIME_SERIES_WEEKLY_ADJUSTED`
  - `TIME_SERIES_MONTHLY`
  - `TIME_SERIES_MONTHLY_ADJUSTED`
  - `GLOBAL_QUOTE`
  - `SYMBOL_SEARCH`
  - `LISTING_STATUS`
- Index Data API:
  - Use the official Alpha Vantage documentation as source of truth for current index endpoint names, symbols, required parameters, and premium entitlement requirements.
  - Treat premium or entitlement errors as expected possibilities, not tool failures.

Out of scope unless explicitly requested:

- Company fundamentals
- Technical indicators
- FX, crypto, economic indicators, news, options, commodities
- SDKs, Python wrappers, MCP integrations

## Authentication

Use `ALPHAVANTAGE_API_KEY` from the environment first. If missing, load `.env` locally without printing secret values.

```bash
if [ -z "${ALPHAVANTAGE_API_KEY:-}" ] && [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if [ -z "${ALPHAVANTAGE_API_KEY:-}" ]; then
  echo "Missing ALPHAVANTAGE_API_KEY"
  exit 1
fi
```

Never echo, log, commit, or hardcode the API key.

## Base Pattern

Use `curl -sG` with `--data-urlencode` so symbols and query parameters are safely encoded.

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=TIME_SERIES_DAILY" \
  --data-urlencode "symbol=IBM" \
  --data-urlencode "outputsize=compact" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

Prefer `datatype=json` for analysis. Use `datatype=csv` only when the user asks for CSV or a tabular export.

## Core Stock Examples

### Intraday OHLCV

Required: `function`, `symbol`, `interval`, `apikey`.

Common optional parameters: `adjusted`, `extended_hours`, `month`, `outputsize`, `datatype`.

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=TIME_SERIES_INTRADAY" \
  --data-urlencode "symbol=AAPL" \
  --data-urlencode "interval=5min" \
  --data-urlencode "adjusted=true" \
  --data-urlencode "extended_hours=true" \
  --data-urlencode "outputsize=compact" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

### Daily Time Series

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=TIME_SERIES_DAILY" \
  --data-urlencode "symbol=MSFT" \
  --data-urlencode "outputsize=compact" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

Use `TIME_SERIES_DAILY_ADJUSTED` when split and dividend adjusted fields matter.

### Weekly Or Monthly Time Series

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=TIME_SERIES_WEEKLY_ADJUSTED" \
  --data-urlencode "symbol=SPY" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

Replace `TIME_SERIES_WEEKLY_ADJUSTED` with `TIME_SERIES_MONTHLY_ADJUSTED` for monthly adjusted data.

### Global Quote

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=GLOBAL_QUOTE" \
  --data-urlencode "symbol=NVDA" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

### Symbol Search

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=SYMBOL_SEARCH" \
  --data-urlencode "keywords=Toyota" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

### Listing Status

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=LISTING_STATUS" \
  --data-urlencode "state=active" \
  --data-urlencode "datatype=csv" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

Use `state=delisted` for delisted securities when needed.

## Index Data Workflow

1. Check the official Alpha Vantage documentation for the current Index Data API function name, required parameters, symbol format, and entitlement notes.
2. Query through the same base endpoint:

```bash
curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=<INDEX_FUNCTION_FROM_DOCS>" \
  --data-urlencode "symbol=<INDEX_SYMBOL_FROM_DOCS>" \
  --data-urlencode "datatype=json" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}"
```

3. If the response indicates premium access, entitlement, invalid function, or invalid symbol, report that plainly and do not invent fallback data.
4. If index support is ambiguous, use `SYMBOL_SEARCH` or the official documentation to verify the symbol before retrying.

## Response Checks

After every request, inspect the JSON before using the result:

- `Error Message`: wrong function, symbol, or parameter.
- `Information`: rate limit, premium requirement, or usage notice.
- `Note`: API call frequency limit.
- Empty payload: unsupported symbol, no data for requested period, or entitlement issue.

Example with `jq`:

```bash
response="$(curl -sG "https://www.alphavantage.co/query" \
  --data-urlencode "function=GLOBAL_QUOTE" \
  --data-urlencode "symbol=IBM" \
  --data-urlencode "apikey=${ALPHAVANTAGE_API_KEY}")"

echo "$response" | jq .
```

If `jq` is unavailable, read the raw JSON and summarize only non-secret response fields.

## Output Guidance

When sharing results with the user:

- State market, symbol, currency if available, data function, and retrieval time.
- Separate returned facts from interpretation.
- Mention if data may be delayed, compact, rate-limited, premium-gated, or incomplete.
- Do not provide trade instructions, position sizing, or personalized recommendations.
