# Prompt: Follow-up Tradable Tickers

## Purpose

Identify tradable tickers related to a prior deep-research result and convert them into structured, research-ready opportunity hypotheses.

Use this prompt only as a follow-up task chained to an existing deep-research interaction.

## Inputs

- `previous_interaction_id`: Prior provider interaction ID used to supply deep-research context.
- `prior_research_context`: The thesis, evidence, risks, and conclusions from the previous research interaction.
- `focus_markets`: Target markets to consider. Default: `HK`, `JP`, and `US`.
- `analysis_timeframe`: Time horizon for the opportunity scan. Default: `mixed`.

## Task

Follow up on the prior deep-research context and identify related tradable tickers.

For each ticker:

1. Explain how it relates to the research thesis through causal, supply-chain, competitive, policy, liquidity, or macro linkages.
2. Provide a research hypothesis, including trade direction, event or observation-based entry criteria, exit criteria, conviction, and the key invalidation event.
3. Surface assumptions, open questions, and monitoring signals that would help validate or reject the hypothesis.

## Analysis Requirements

- Start from the prior research thesis, not a generic ticker screen.
- Include only tickers with a clear relationship to the thesis.
- Prefer direct beneficiaries, direct losers, key suppliers/customers, liquid proxies, ETFs, or instruments that express the thesis cleanly.
- Consider market, exchange, currency, asset class, liquidity, policy sensitivity, and macro sensitivity.
- Clearly separate evidence from assumptions and uncertainty.

## Constraints

- This is research framing only, not personalized investment advice.
- Do not provide trade instructions, position sizing, or portfolio allocation recommendations.
- Keep entry and exit criteria non-quantitative and based on observable events or evidence.
- `relationship_to_research` must be free text, not categorical labels.
- If evidence is limited, include fewer tickers and lower conviction accordingly.
- Do not invent ticker relationships when the prior research context is insufficient.

## Output Format

Return JSON only.

The output must conform to `data/schema-tradable-tickers-output.json`.

If no credible ticker opportunities are found, return:

- `ticker_opportunities`: an empty array
- `output_quality.missing_information`: the information needed to identify credible tickers
- `output_quality.uncertainty_notes`: why the available evidence is insufficient

## Quality Bar

A good output is specific, falsifiable, and explicit about why each ticker matters to the thesis.

Each opportunity should make clear:

- the market, exchange, currency, and asset class
- the causal link to the research thesis
- the core research hypothesis
- what would invalidate the view
- what signals should be monitored next

## Missing Context Handling

If the prior research context is missing or too thin, do not guess. Return an empty `ticker_opportunities` array, describe the missing context in `output_quality.missing_information`, and use the required schema fields to summarize the limitation.
