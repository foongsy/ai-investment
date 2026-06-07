---
name: create-tv-pine-screener
description: Create TradingView Pine Script indicators compatible with Pine Screener and Trading Proposals Layer 2 price fields. Use when the user asks for Pine Screener scripts, TV screener indicators, entry/stop/target plots, or external price-plan scripts for Trading Proposals.
disable-model-invocation: true
---

# Create TV Pine Screener

Create Pine Script v5 **indicators** (not strategies) that output Layer 2 price-plan values for `Trading Proposals` via Pine Screener.

Canonical schema: `data/notion/research.md` (Trading Proposals → Layer 2 — Price Plan).

## Scope

- **In scope:** Pine Script files under `data/tradingview/*.pine`, Pine Screener plot design, long/short price math, RR derivation rules, watchlist screening workflow.
- **Out of scope:** Notion writes (confirm separately), automated order placement, portfolio sizing.
- **Related skills:** `export-tv-watchlist` (watchlist export + per-run Fast.io session), `fastio-cli` (`pinescreener*.csv` upload to the same run session), `import-screener-pricing` (screener CSV → Notion Layer 2), `refresh-proposal-quotes` (Alpha Vantage `Last Price` only).

## Before Writing

1. Read `data/notion/research.md` (Layer 2 + Reward Risk Ratio).
2. Read existing examples in `data/tradingview/` when adapting a pattern:
   - `supertrend-ema-atr-long.pine` — long, Supertrend + EMA + ATR
   - `darvas-box-breakdown-short.pine` — short, box breakdown + volume + EMA
   - `ema-macd-rsi-short.pine` — short, EMA + MACD + RSI momentum
3. Confirm with the user when unclear:
   - `Trade Type`: `long` or `short`
   - Time horizon (default: medium-term, 1D chart, 1–3 months)
   - Strategy family (trend-following, breakdown, momentum)
   - Whether they want `Setup Active` (ongoing) or `New Setup` (fresh trigger) as the primary filter

## Pine Screener Constraints

From [TradingView Pine Screener requirements](https://www.tradingview.com/support/solutions/43000742436-tradingview-pine-screener-key-features-and-requirements/):

| Rule | Implication |
| --- | --- |
| Only `plot()` and `alertcondition()` feed screener columns/filters | All Notion-facing values must be `plot()` series |
| First **10** plots become default columns/filters | Put price-plan plots first; chart-only visuals after |
| Indicator must be in **Favorites** to appear in Pine Screener | Tell user to favorite after save |
| Default timeframe is **1D**; supported TFs include `1D`, `4H`, `1W`, `1M` | Design for daily unless user specifies otherwise |
| `request.*()` allowed; max 5 calls | Prefer single-timeframe logic when possible |
| Tables, labels, `alert()` JSON payloads | Chart-only; **ignored** by Pine Screener |

### Do Not Use for Screener Output

- `table.new()` / `table.cell()`
- `label.new()` as the primary data channel
- Dynamic `alert()` JSON (use `alertcondition()` only if alerts are needed)
- `strategy()` — use `indicator()` for screening

### Setup Active vs New Setup

| Plot | Meaning | Typical filter |
| --- | --- | --- |
| `Setup Active` | Symbol currently satisfies all entry/stop/target conditions | `Setup Active = 1` — ongoing candidates |
| `New Setup` | Setup became active on this bar | `New Setup = 1` — fresh signals only |

Price plots should populate whenever `Setup Active = 1`. If a user reports blank price columns with `Setup Active = 1`, check column selection and rescan before changing script logic.

## Required Plot Contract (Trading Proposals)

Use these **exact plot titles** for the first six plots so screener columns align with Notion field names:

```text
1. Setup Active
2. New Setup
3. Entry Price
4. Stop Price
5. Target Price
6. Reward Risk Ratio
```

Plots 7–10: strategy-specific diagnostics (e.g. `Close Below EMA`, `Box Breakdown`, `MACD Bearish`).

Plot price values only when `setupActive` is true; otherwise `na`.

## Price Math

### Long (`Trade Type = long`)

```text
risk   = entry - stop
reward = target - entry
reward_risk_ratio = reward / risk
```

Expect: `stop < entry < target`, `risk > 0`.

### Short (`Trade Type = short`)

```text
risk   = stop - entry
reward = entry - target
reward_risk_ratio = reward / risk
```

Expect: `target < entry < stop`, `risk > 0`.

Store RR as a plain number (e.g. `2.5`). Importer should recompute from three prices; Pine may output the configured RR target when using fixed-R multiple targets.

## Implementation Workflow

### 1. Design

- Pick entry trigger (trend flip, breakdown, momentum alignment).
- Pick stop anchor (indicator line, swing high/low, ATR fallback).
- Pick target rule (fixed RR multiple of risk).
- Enforce `risk > 0` before marking `setupActive`.

### 2. Write Script

- File path: `data/tradingview/<strategy-kebab>.pine`
- Header: `//@version=5`
- Declaration: `indicator("<Name> Screener", overlay=true)`
- Comment: Pine Screener-compatible; medium-term daily default.
- Use `input.*` for tunable parameters.
- Keep all `plot()` calls in **global scope** (conditional values via ternary/`na`, not `plot()` inside `if` blocks).

### 3. Validate Checklist

Before delivering:

- [ ] First plot is `Setup Active`; plots 3–6 are Entry/Stop/Target/RR
- [ ] No `table`, `label`, or JSON `alert()` required for screener use
- [ ] Long/short price ordering matches `Trade Type`
- [ ] `risk > 0` guard on `setupActive`
- [ ] Box/swing references use prior bars (`high[1]`, `low[1]`) when current bar can trigger
- [ ] Plot count ≤ 10 for default screener columns (extras are optional/hidden)
- [ ] User told to: save → favorite → Pine Screener → select watchlist → `Setup Active = 1` → Rescan

### 4. Trading Proposals Handoff

Layer 2 population uses `import-screener-pricing` after screener CSV upload, or manual review. From screener rows, map:

| Pine Screener column | Notion field |
| --- | --- |
| Entry Price | `Entry Price` |
| Stop Price | `Stop Price` |
| Target Price | `Target Price` |
| Reward Risk Ratio | `Reward Risk Ratio` (recompute on write) |
| — | `Pricing Notes` — add strategy name + filter context manually |
| — | `Pricing Status` → `Ready` after review |

`Last Price` / `Quote As Of` come from `refresh-proposal-quotes`, not Pine.

End-to-end watchlist flow:

1. `export-tv-watchlist` → local `YYYY-MM-DD-<run_id>.txt` + Fast.io `trading-proposals/sessions/<YYYY-MM-DD>-<run_id>/watchlist.txt`
2. Import watchlist into TradingView
3. Run Pine Screener with this indicator on `1D`
4. Upload any `pinescreener*.csv` to the same Fast.io run session folder (filename must start with `pinescreener`; script name not required)
5. Run `import-screener-pricing` for the same `run_id` (defaults to `Setup Active = 1`)

## Skeleton

See [references/skeleton.pine](references/skeleton.pine). Copy and replace `// TODO` sections.

## Response Format

When delivering a new script:

1. State `Trade Type`, timeframe, and strategy family.
2. List the first 10 plot names.
3. Explain `Setup Active` vs `New Setup` filter recommendation.
4. Note Pine Screener setup steps (favorite, rescan).
5. Remind that Notion writes require separate confirmation.
