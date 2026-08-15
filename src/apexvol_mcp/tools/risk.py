"""
Risk Management Tools

Tools for portfolio Greeks, scenario analysis, stress testing, and hedging.
Uses REST API calls to ApexVol platform.

Positions are passed as a JSON array string. Each position supports:
  ticker (required), position_type ("STOCK"|"CALL"|"PUT", default STOCK),
  quantity (signed; negative = short), strike, expiration ("YYYY-MM-DD"),
  entry_price, current_price, stock_price, delta, gamma, theta, vega, iv.
For option positions, per-share Greeks (delta etc.) should come from the
options chain (get_options_chain / get_options_by_delta) — without them an
option contributes zero Greeks and results will understate risk.
A plain-text fallback ("AAPL 100 shares, SPY -50 shares") is accepted for
stock-only portfolios.
"""

import json
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError
from ._annotations import read_only

logger = logging.getLogger(__name__)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_positions(positions_str: str) -> tuple:
    """Parse the positions argument.

    Returns (positions, warning): positions is a list of dicts ready for the
    API; warning is a str when the lossy text fallback was used, else None.
    """
    text = (positions_str or '').strip()
    if not text:
        return [], None

    # Preferred path: JSON array (or single JSON object)
    if text[0] in '[{':
        parsed = json.loads(text)  # let a JSON syntax error surface to the user
        if isinstance(parsed, dict):
            parsed = [parsed]
        positions = []
        for p in parsed:
            pos = dict(p)
            pos['ticker'] = str(pos.get('ticker', '')).upper()
            pos['position_type'] = str(pos.get('position_type', pos.get('type', 'STOCK'))).upper()
            positions.append(pos)
        return positions, None

    # Fallback: legacy free text — stock-only, no Greeks beyond delta=1/share
    positions = []
    for chunk in text.split(','):
        parts = chunk.strip().split()
        if len(parts) >= 2:
            try:
                qty = int(parts[1])
            except ValueError:
                qty = 1
            positions.append({
                'ticker': parts[0].upper(),
                'quantity': qty,
                'position_type': 'STOCK',
            })
    warning = (
        'Positions were parsed from free text as stock-only. For option positions, '
        'pass a JSON array with strike/expiration/Greeks (see tool description) — '
        'otherwise options are ignored and risk is understated.'
    )
    return positions, warning


def register_tools(mcp: FastMCP):
    """Register risk management tools with the MCP server."""

    @mcp.tool(**read_only('Portfolio Greeks'))
    async def calculate_portfolio_greeks(positions: str) -> dict:
        """
        Calculate aggregate Greeks for a portfolio of positions.

        Takes a portfolio of options positions and calculates net delta,
        theta, and vega exposure plus a risk-level assessment.

        Use this tool when the user asks about:
        - Portfolio Greeks
        - Net delta/theta/vega
        - Position exposure

        Args:
            positions: JSON array of positions, e.g. '[{"ticker": "AAPL", "position_type": "STOCK", "quantity": 100, "current_price": 210}, {"ticker": "AAPL", "position_type": "CALL", "quantity": -2, "strike": 220, "expiration": "2026-08-21", "current_price": 4.10, "delta": 0.31, "theta": -8.2, "vega": 21.0}]'. Get option Greeks from get_options_chain first. Plain text ("AAPL 100 shares") works for stock-only portfolios.

        Returns:
            Aggregated portfolio Greeks with risk assessment
        """
        try:
            client = get_client()
            parsed_positions, warning = _parse_positions(positions)
            result = await client.post("/portfolio-greeks", data={'positions': parsed_positions})

            s = result.get('portfolio_summary', {})
            response = {
                "success": True,
                "data": result,
                "summary": f"""## Portfolio Greeks

| Metric | Value |
|--------|-------|
| Net Delta | {s.get('total_delta', 0):,.2f} |
| Net Theta | ${s.get('total_theta', 0):,.2f}/day |
| Net Vega | ${s.get('total_vega', 0):,.2f} |
| Portfolio Value | ${s.get('total_value', 0):,.2f} |
| P&L | ${s.get('total_pnl', 0):,.2f} ({s.get('total_pnl_pct', 0):+.1f}%) |
| Risk Level | {s.get('risk_level', 'N/A')} |

**Position Count**: {s.get('total_positions', len(parsed_positions))}
""",
                "metadata": {"timestamp": _now_iso()}
            }
            if warning:
                response["warning"] = warning
            return response
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error calculating portfolio Greeks: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Scenario Analysis'))
    async def run_scenario_analysis(
        positions: str,
        stock_move_pct: float = 0,
        iv_change_pct: float = 0,
        days_forward: int = 0
    ) -> dict:
        """
        Run what-if scenario analysis on a portfolio.

        Shows how portfolio value changes under different market conditions
        (linear delta/vega/theta approximation).

        Use this tool when the user asks about:
        - What-if scenarios
        - Portfolio P&L under different conditions
        - Price/vol sensitivity

        Args:
            positions: JSON array of positions, e.g. '[{"ticker": "AAPL", "position_type": "STOCK", "quantity": 100, "current_price": 210}, {"ticker": "AAPL", "position_type": "CALL", "quantity": -2, "strike": 220, "expiration": "2026-08-21", "current_price": 4.10, "delta": 0.31, "theta": -8.2, "vega": 21.0}]'. Get option Greeks from get_options_chain first. Plain text ("AAPL 100 shares") works for stock-only portfolios.
            stock_move_pct: Percent stock price change to simulate (e.g. -5)
            iv_change_pct: Percent IV change to simulate (e.g. 25)
            days_forward: Days of time decay to advance

        Returns:
            Estimated P&L under the scenario with per-Greek contributions
        """
        try:
            client = get_client()
            parsed_positions, warning = _parse_positions(positions)
            data = {
                'positions': parsed_positions,
                'scenarios': [{
                    'stock_move_pct': stock_move_pct,
                    'iv_change_pct': iv_change_pct,
                    'days_forward': days_forward
                }]
            }
            result = await client.post("/scenario-analysis", data=data)

            scenarios = result.get('scenarios', [])
            s = scenarios[0] if scenarios else {}
            response = {
                "success": True,
                "data": result,
                "summary": f"""## Scenario Analysis

**Scenario**: Stock {stock_move_pct:+.1f}%, IV {iv_change_pct:+.1f}%, +{days_forward} days

| Metric | Value |
|--------|-------|
| Estimated P&L | ${s.get('estimated_pnl', 0):,.2f} ({s.get('estimated_pnl_pct', 0):+.1f}%) |
| Delta contribution | ${s.get('delta_contribution', 0):,.2f} |
| Vega contribution | ${s.get('vega_contribution', 0):,.2f} |
| Theta contribution | ${s.get('theta_contribution', 0):,.2f} |
| New Portfolio Value | ${s.get('new_portfolio_value', 0):,.2f} |
""",
                "metadata": {"timestamp": _now_iso()}
            }
            if warning:
                response["warning"] = warning
            return response
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error running scenario: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Stress Tests'))
    async def generate_stress_tests(positions: str) -> dict:
        """
        Run stress test scenarios on a portfolio.

        Tests portfolio under extreme market conditions like crashes,
        vol spikes, and rallies.

        Use this tool when the user asks about:
        - Stress testing
        - Crash scenarios
        - Worst-case analysis

        Args:
            positions: JSON array of positions, e.g. '[{"ticker": "AAPL", "position_type": "STOCK", "quantity": 100, "current_price": 210}, {"ticker": "AAPL", "position_type": "CALL", "quantity": -2, "strike": 220, "expiration": "2026-08-21", "current_price": 4.10, "delta": 0.31, "theta": -8.2, "vega": 21.0}]'. Get option Greeks from get_options_chain first. Plain text ("AAPL 100 shares") works for stock-only portfolios.

        Returns:
            P&L under various stress scenarios
        """
        try:
            client = get_client()
            parsed_positions, warning = _parse_positions(positions)
            result = await client.post("/stress-tests", data={'positions': parsed_positions})

            scenarios = result.get('scenarios', [])
            summary_lines = ["## Stress Test Results", "", "| Scenario | Est. P&L | P&L % |", "|----------|----------|-------|"]
            for s in scenarios:
                summary_lines.append(
                    f"| {s.get('scenario_name', 'N/A')} | ${s.get('estimated_pnl', 0):,.2f} "
                    f"| {s.get('estimated_pnl_pct', 0):+.1f}% |"
                )

            response = {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {"timestamp": _now_iso()}
            }
            if warning:
                response["warning"] = warning
            return response
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error generating stress tests: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Hedge Recommendations'))
    async def get_hedge_recommendations(
        positions: str,
        hedge_ticker: str = "SPY",
        target_delta: float = 0
    ) -> dict:
        """
        Get delta-hedge recommendations for a portfolio.

        Computes net portfolio delta and suggests a stock hedge plus an
        option-based alternative on the hedge ticker to reach the target
        delta. Recommendations are share-equivalent, not beta-weighted.

        Use this tool when the user asks about:
        - How to hedge a position or portfolio
        - Getting delta-neutral
        - Protective puts / reducing directional risk

        Args:
            positions: JSON array of positions, e.g. '[{"ticker": "AAPL", "position_type": "STOCK", "quantity": 100, "current_price": 210}, {"ticker": "AAPL", "position_type": "CALL", "quantity": -2, "strike": 220, "expiration": "2026-08-21", "current_price": 4.10, "delta": 0.31, "theta": -8.2, "vega": 21.0}]'. Get option Greeks from get_options_chain first. Plain text ("AAPL 100 shares") works for stock-only portfolios.
            hedge_ticker: Instrument to hedge with (default SPY)
            target_delta: Desired net portfolio delta (default 0 = neutral)

        Returns:
            Current vs target delta and concrete hedge suggestions
        """
        try:
            client = get_client()
            parsed_positions, warning = _parse_positions(positions)
            data = {
                'positions': parsed_positions,
                'hedge_ticker': hedge_ticker,
                'target_delta': target_delta,
            }
            result = await client.post("/hedge-recommendations", data=data)

            response = {
                "success": True,
                "data": result,
                "summary": f"""## Hedge Recommendations

**Current Delta**: {result.get('current_delta', 0):,.2f}
**Target Delta**: {result.get('target_delta', 0):,.2f}
**Gap**: {result.get('delta_gap', 0):+,.2f}

{result.get('note', '')}

### Suggested Hedges
{_format_hedges(result.get('hedges', []))}
""",
                "metadata": {"timestamp": _now_iso()}
            }
            if warning:
                response["warning"] = warning
            return response
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting hedge recommendations: {e}")
            return {"success": False, "error": str(e)}


def _format_hedges(hedges: list) -> str:
    """Format hedge recommendations as markdown."""
    if not hedges:
        return "No hedges needed"

    lines = []
    for h in hedges:
        lines.append(f"- **{h.get('description', 'N/A')}** — {h.get('details', '')}")
    return "\n".join(lines)
