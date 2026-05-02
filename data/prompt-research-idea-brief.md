# Prompt: Research Idea Brief

## Purpose

Convert a raw investment `Original Idea` into a concise, deep-research-ready brief.

The brief should help a buy-side style research workflow test whether the idea is valid, mispriced, and worthy of further diligence.

## Inputs

- `original_idea`: Raw investment idea entered by the user.
- `analysis_window`: Time range for the research brief. Default: last 7 days.
- `focus_markets`: Target markets when specified. Default: Hong Kong, Japan, and US.
- `asset_focus`: Target asset classes when specified. Default: equities, derivatives, ETFs, and crypto assets.

## Task

Transform `original_idea` into a high-signal research brief for deep research.

Keep the brief specific, falsifiable, and evidence-seeking. Prioritize the questions and facts that would most efficiently validate, reject, or refine the thesis.

## Analysis Requirements

Focus strictly on these five sections:

1. Thesis clarity and variant view
2. Industry and macro regime
3. Management and governance
4. Catalysts and timing
5. Risk and downside

Apply these cross-cutting checks in every section:

- policy, regulation, and legal shifts
- sanctions, export controls, and cross-border constraints
- election and geopolitical tension scenarios
- rates, inflation, FX, liquidity, and volatility regime changes
- crowding, correlation, and positioning risks during stress

## Constraints

- Keep the final brief within 15,000 characters.
- Target 1,500-4,000 characters when possible.
- Prioritize high-signal content and remove low-value detail.
- Clearly separate facts, assumptions, and uncertainties.
- State what consensus likely believes versus the variant view.
- Include evidence that would invalidate the thesis.
- Prefer primary or authoritative sources to investigate first.
- Do not provide trade instructions, position sizing, portfolio allocation, or personalized investment advice.

## Output Format

Return a Markdown brief using exactly these sections:

1. `## Thesis Clarity And Variant View`
2. `## Industry And Macro Regime`
3. `## Management And Governance`
4. `## Catalysts And Timing`
5. `## Risk And Downside`
6. `## Source Priorities`
7. `## Missing Context`

For `## Thesis Clarity And Variant View`, include:

- the core claim in 1-2 lines
- why it may be mispriced now
- consensus view versus variant view
- decisive disconfirming evidence

For `## Industry And Macro Regime`, include:

- industry structure and cycle phase
- key macro drivers and transmission channels
- base regime versus adverse regime implications

For `## Management And Governance`, include:

- capital allocation and execution track record
- incentive alignment, ownership, governance quality, and disclosure credibility
- governance concerns that reduce conviction

For `## Catalysts And Timing`, include:

- concrete catalysts and impact mechanisms
- expected timing windows and dependency chain
- whether the thesis is near-term catalyst-driven or long-duration

For `## Risk And Downside`, include:

- downside paths and trigger conditions
- bear-case severity and major uncertainty nodes
- explicit kill criteria or thesis-break conditions

## Quality Bar

A good brief is concise, operational, and useful as direct input for deep research.

It should read like a checklist of what a research analyst needs to verify next, not like generic market commentary.

## Missing Context Handling

If crucial context is missing, state the gap in `## Missing Context` and list the minimum additional inputs needed to produce a sharper brief.
