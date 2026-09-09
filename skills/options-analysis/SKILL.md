---
name: options-analysis
description: Analyze options and volatility with live ApexVol data — IV rank, volatility risk premium, GEX, expected moves, earnings setups, strategy building, and market screens. Use when the user asks whether options are cheap or expensive, where dealer gamma sits, how to trade an earnings event, which stocks suit premium selling, or wants any options strategy built and stress-tested. Requires the ApexVol MCP server (remote connector or apexvol-mcp package).
---

# Options Analysis with ApexVol

You have access to 44 ApexVol tools for live options analytics. This skill
tells you which tools to combine for common analyses and how to interpret
the numbers.

## Ground rules

1. **Fetch before claiming.** Never state an IV rank, GEX level, or expected
   move from memory — call the tool. Quote the timestamp that comes back with
   the data.
2. **Volatility numbers are percentage points.** IV 12.3 means 12.3% — never
   rescale. VRP is quoted as IV minus realized vol, in points.
3. **Tier gating:** each tool follows the user's ApexVol plan. A 403 means
   that tool sits above their tier — say which tool was gated and continue
   with what you can access; don't retry.
4. **Rate limits:** 60 requests/min, 1,000/hr. Batch your thinking: plan
   which 3-6 calls answer the question rather than fetching everything.
5. **Flow tools** (`get_options_flow`, `get_smart_money_flow`) may report
   themselves unavailable; relay that honestly instead of substituting
   guesses.
6. This is analysis, not financial advice — present numbers, comparisons,
   and trade-offs, and note key risks (assignment, earnings gaps, liquidity).

## Workflow: Is volatility rich or cheap on X?

1. `get_iv_rank(ticker)` — where current IV sits in its 52-week range.
2. `get_volatility_risk_premium(ticker)` — IV minus realized vol.
3. `get_term_structure(ticker)` — front-month vs back-month shape.
4. Optional: `get_volatility_cone(ticker)` for IV vs realized across windows.

Interpretation:
- IV rank > 50 and positive VRP → premium historically rich; selling
  structures have a tailwind. IV rank > 80 usually means a known catalyst —
  check earnings before calling it "expensive."
- IV rank < 30 and VRP near zero or negative → options cheap relative to
  movement; favors long-vol/debit structures.
- Negative VRP (realized exceeding implied) is a warning for premium
  sellers regardless of IV rank.
- Term structure in backwardation (front above back) signals event risk or
  stress; contango is the normal state.

## Workflow: Earnings event setup

1. `get_earnings_calendar` or `get_orats_cores(ticker)` — confirm the date.
2. `calculate_expected_move(ticker)` — straddle-implied move for the
   relevant expiration.
3. `get_earnings_move_analysis(ticker, view="expected_vs_actual")` — how
   implied compared to realized on past events; `view="verdict"` for the
   summary; `view="iv_crush"` for post-event vol behavior.

Interpretation:
- Compare the implied move to the average realized move. Implied
  persistently above realized → the straddle is a rich sale, but size for
  the tail: one outsized quarter erases many small wins.
- Realized moves are measured close-to-close; the overnight gap can differ.
  Note this when precision matters.
- The pre-earnings straddle price is a **cost**, not an expected return —
  never present it as profit potential.

## Workflow: Premium-selling candidates (CSP / covered call)

1. `screen_market(scan_type="high_iv_rank")` — raw candidates.
2. Filter judgment: prefer liquid large caps the user would own; treat
   extreme IV (rank > 85 or absolute IV > 100%) as a red flag for binary
   risk, not an opportunity.
3. Per candidate: `get_expirations(ticker)`, then
   `get_options_by_delta(ticker, delta=0.20-0.30)` at 30-45 DTE.
4. `calculate_probability_of_profit` on the chosen strike.
5. Check the earnings date falls outside the DTE window (step 1 data or
   `get_orats_cores`).

Present each candidate as: strike, premium, annualized yield on collateral,
breakeven, PoP, and the main risk.

## Workflow: GEX / dealer positioning read

1. `get_gex(ticker)` — net gamma by strike, flip point, call/put walls.
2. `get_zero_dte(ticker)` for SPY/QQQ/SPX intraday context.
3. `get_cross_index_gex()` to compare regimes across indices.

Interpretation:
- Spot above the flip point (positive net gamma): dealer hedging dampens
  moves; ranges and mean-reversion are favored.
- Spot below the flip (negative gamma): hedging amplifies moves; expect
  wider ranges and faster trends.
- Large call/put walls act as magnets/resistance into expiration —
  strongest near OPEX, weakest right after.

## Workflow: Build and stress a strategy

1. `build_strategy(ticker, strategy_type=...)` — legs from live quotes.
2. `analyze_strategy` — P&L profile, breakevens, Greeks.
3. `run_scenario_analysis` or `generate_stress_tests` — shock price and IV
   (at minimum: ±expected move, and an IV crush for post-earnings).
4. `optimize_strategy` when the user wants strike selection done for them.
5. For portfolios: `calculate_portfolio_greeks`, then
   `get_hedge_recommendations` if they ask how to flatten risk.

## Quick reference: which tool answers what

| Question shape | Tool |
|---|---|
| "Is IV high on X?" | `get_iv_rank` |
| "Are options overpriced vs how it moves?" | `get_volatility_risk_premium` |
| "What move is priced in?" | `calculate_expected_move` |
| "Where are the gamma walls / flip?" | `get_gex`, `get_zero_dte` |
| "How does X behave into earnings?" | `get_earnings_move_analysis` |
| "Find me candidates for strategy Y" | `screen_market`, then per-ticker checks |
| "Skew / dividends / borrow / HV regime?" | `get_ticker_analytics(view=...)` |
| "Raw vendor fields" | `get_orats_cores` |
| "Whole-market picture" | `get_market_overview`, `get_vix_snapshot` |

## Error handling

- **401/403:** token invalid or tool above the user's plan tier — name the
  tool, suggest checking Account → API Access, continue with accessible tools.
- **429:** rate limit — pause and reduce call count; don't hammer.
- **Ticker not found:** try `search_tickers` before concluding no coverage.
