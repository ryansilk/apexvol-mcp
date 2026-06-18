"""
Risk Management Tools

Tools for portfolio Greeks, scenario analysis, stress testing, and hedging.
Uses REST API calls to ApexVol platform.
"""

import logging
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register risk management tools with the MCP server."""

    @mcp.tool()
    async def calculate_portfolio_greeks(positions: str) -> dict:
        """
        Calculate aggregate Greeks for a portfolio of positions.

        Takes a portfolio of options positions and calculates net delta,
        gamma, theta, and vega exposure.

        Use this tool when the user asks about:
        - Portfolio Greeks
        - Net delta/gamma/theta/vega
        - Position exposure

        Args:
            positions: Positions in format "AAPL 100 shares, AAPL 1 C 150 Jan"

        Returns:
            Aggregated portfolio Greeks
        """
        try:
            client = get_client()

            parsed_positions = _parse_positions(positions)
            data = {'positions': parsed_positions}

            result = await client.post("/portfolio-greeks", data=data)

            return {
                "success": True,
                "data": result,
                "summary": f"""## Portfolio Greeks

| Greek | Value |
|-------|-------|
| Net Delta | {result.get('total_delta', 0):.2f} |
| Net Gamma | {result.get('total_gamma', 0):.4f} |
| Net Theta | ${result.get('total_theta', 0):.2f}/day |
| Net Vega | ${result.get('total_vega', 0):.2f} |

**Position Count**: {len(parsed_positions)}
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error calculating portfolio Greeks: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def run_scenario_analysis(
        positions: str,
        price_change: float = 0,
        vol_change: float = 0,
        days_forward: int = 0
    ) -> dict:
        """
        Run what-if scenario analysis on a portfolio.

        Shows how portfolio value changes under different market conditions.

        Use this tool when the user asks about:
        - What-if scenarios
        - Portfolio P&L under different conditions
        - Price/vol sensitivity

        Args:
            positions: Portfolio positions
            price_change: Percent price change to simulate
            vol_change: Percent vol change to simulate
            days_forward: Days to advance time

        Returns:
            P&L under the scenario
        """
        try:
            client = get_client()

            parsed_positions = _parse_positions(positions)
            data = {
                'positions': parsed_positions,
                'scenarios': [{
                    'price_change': price_change,
                    'vol_change': vol_change,
                    'days_forward': days_forward
                }]
            }

            result = await client.post("/scenario-analysis", data=data)

            return {
                "success": True,
                "data": result,
                "summary": f"""## Scenario Analysis

**Scenario**: Price {price_change:+.1f}%, Vol {vol_change:+.1f}%, +{days_forward} days

| Metric | Value |
|--------|-------|
| P&L | ${result.get('pnl', 0):.2f} |
| New Delta | {result.get('new_delta', 0):.2f} |
| New Value | ${result.get('new_value', 0):.2f} |
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error running scenario: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
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
            positions: Portfolio positions

        Returns:
            P&L under various stress scenarios
        """
        try:
            client = get_client()

            parsed_positions = _parse_positions(positions)
            data = {'positions': parsed_positions}

            result = await client.post("/stress-tests", data=data)

            scenarios = result.get('scenarios', [])
            summary_lines = ["## Stress Test Results", "", "| Scenario | P&L |", "|----------|-----|"]
            for s in scenarios:
                summary_lines.append(f"| {s.get('name', 'N/A')} | ${s.get('pnl', 0):,.2f} |")

            return {
                "success": True,
                "data": result,
                "summary": "\n".join(summary_lines),
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error generating stress tests: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def get_hedge_recommendations(
        positions: str,
        hedge_ticker: str = "SPY"
    ) -> dict:
        """
        Get hedge recommendations for a portfolio.

        Suggests options positions to reduce risk exposure.

        Use this tool when the user asks about:
        - How to hedge a position
        - Reducing risk
        - Protective puts or collars

        Args:
            positions: Current portfolio positions
            hedge_ticker: Ticker to use for hedging (default SPY)

        Returns:
            Recommended hedges with details
        """
        try:
            client = get_client()

            parsed_positions = _parse_positions(positions)
            data = {'positions': parsed_positions}

            result = await client.post("/hedge-recommendations", data=data)

            return {
                "success": True,
                "data": result,
                "summary": f"""## Hedge Recommendations

**Current Delta**: {result.get('current_delta', 0):.2f}
**Target Delta**: {result.get('target_delta', 0):.2f}

### Recommended Hedges
{_format_hedges(result.get('hedges', []))}
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting hedge recommendations: {e}")
            return {"success": False, "error": str(e)}


def _parse_positions(positions_str: str) -> list:
    """Parse positions string into list of position dicts."""
    # Simple parser - returns basic structure
    positions = []
    for pos in positions_str.split(','):
        parts = pos.strip().split()
        if len(parts) >= 2:
            positions.append({
                'ticker': parts[0].upper(),
                'quantity': int(parts[1]) if parts[1].isdigit() else 1,
                'type': 'stock' if 'share' in pos.lower() else 'option'
            })
    return positions


def _format_hedges(hedges: list) -> str:
    """Format hedge recommendations as markdown."""
    if not hedges:
        return "No hedges recommended"

    lines = []
    for h in hedges:
        lines.append(f"- {h.get('description', 'N/A')}: {h.get('details', '')}")
    return "\n".join(lines)
