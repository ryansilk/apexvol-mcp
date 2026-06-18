"""
Strategy Building Tools

Tools for building, analyzing, and optimizing options strategies.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register strategy tools with the MCP server."""

    @mcp.tool()
    async def build_strategy(
        ticker: str,
        strategy_type: str,
        expiration: Optional[str] = None,
        width: float = 5,
        target_delta: float = 0.30
    ) -> dict:
        """
        Build an options strategy with optimal parameters.

        Supports various strategy types and automatically selects strikes
        based on target delta or other criteria.

        Strategy types: iron_condor, credit_spread, debit_spread, straddle,
        strangle, butterfly, calendar

        Use this tool when the user asks about:
        - Building a specific strategy
        - Iron condor, credit spread, etc.
        - Strategy construction

        Args:
            ticker: Stock symbol
            strategy_type: Type of strategy (iron_condor, credit_spread, etc.)
            expiration: Target expiration or None for nearest monthly
            width: Strike width for spreads in dollars; fractional widths
                like 2.5 are valid (default 5)
            target_delta: Target delta for strike selection (default 0.30)

        Returns:
            Strategy details with legs, Greeks, and expected P&L
        """
        try:
            client = get_client()
            data = {
                'ticker': ticker.upper(),
                'strategy_type': strategy_type,
                'expiration': expiration,
                'width': width,
                'target_delta': target_delta
            }

            result = await client.post("/build-strategy", data=data)

            # P&L metrics live under 'analysis'; legs carry the expiration
            analysis = result.get('analysis') or {}
            legs = result.get('legs', [])
            leg_expiration = legs[0].get('expiration', 'N/A') if legs else 'N/A'

            return {
                "success": True,
                "data": result,
                "summary": f"""## {ticker.upper()} {strategy_type.replace('_', ' ').title()}

**Expiration**: {leg_expiration}
**Max Profit**: ${analysis.get('max_profit', 0):.2f}
**Max Loss**: ${analysis.get('max_loss', 0):.2f}
**P.O.P.**: {analysis.get('probability_of_profit', 0):.1f}%
**Breakevens**: {[round(b, 2) for b in analysis.get('breakevens', [])]}

### Legs
{_format_legs(legs)}
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error building strategy: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def analyze_strategy(
        ticker: str,
        legs: str
    ) -> dict:
        """
        Analyze a custom options strategy.

        Calculates full P&L profile, Greeks, probability of profit,
        and risk metrics for a custom strategy.

        Use this tool when the user asks about:
        - Analyzing a specific trade
        - Strategy P&L profile
        - Greeks for a position

        Args:
            ticker: Stock symbol
            legs: Strategy legs in format "BUY 1 C 150, SELL 1 C 155"

        Returns:
            Full analysis with P&L, Greeks, and probabilities
        """
        try:
            client = get_client()

            # Parse legs string into structure
            parsed_legs = _parse_legs(legs)

            data = {
                'ticker': ticker.upper(),
                'legs': parsed_legs
            }

            result = await client.post("/analyze-strategy", data=data)

            return {
                "success": True,
                "data": result,
                "summary": f"""## Strategy Analysis

**Net Delta**: {result.get('net_delta', 0):.3f}
**Net Theta**: ${result.get('net_theta', 0):.2f}/day
**Net Vega**: ${result.get('net_vega', 0):.2f}
**Max Profit**: ${result.get('max_profit', 0):.2f}
**Max Loss**: ${result.get('max_loss', 0):.2f}
**P.O.P.**: {result.get('probability_of_profit', 0):.1f}%
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error analyzing strategy: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def optimize_strategy(
        ticker: str,
        strategy_type: str,
        target: str = "credit"
    ) -> dict:
        """
        Find optimal strikes for a strategy type.

        Optimizes strike selection based on target criteria like max credit,
        best risk/reward, or target probability.

        Use this tool when the user asks about:
        - Best strikes for a strategy
        - Optimal iron condor strikes
        - Maximizing credit or probability

        Args:
            ticker: Stock symbol
            strategy_type: Type of strategy
            target: Optimization target (credit, risk_reward, probability)

        Returns:
            Optimized strategy parameters
        """
        try:
            client = get_client()
            data = {
                'ticker': ticker.upper(),
                'strategy_type': strategy_type,
                'target': target
            }

            result = await client.post("/optimize-strategy", data=data)

            # P&L metrics live under 'analysis'
            analysis = result.get('analysis') or {}
            net_credit = -analysis.get('net_premium', 0)  # net_premium < 0 = credit received

            return {
                "success": True,
                "data": result,
                "summary": f"""## Optimized {strategy_type.replace('_', ' ').title()}

**Ticker**: {ticker.upper()}
**Optimization**: Maximize {target}

{_format_legs(result.get('legs', []))}

**Net Credit**: ${net_credit:.2f}
**Max Profit**: ${analysis.get('max_profit', 0):.2f}
**Max Loss**: ${analysis.get('max_loss', 0):.2f}
**Risk/Reward**: {analysis.get('risk_reward_ratio', 0):.2f}
""",
                "metadata": {"timestamp": datetime.utcnow().isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error optimizing strategy: {e}")
            return {"success": False, "error": str(e)}


def _format_legs(legs: list) -> str:
    """Format strategy legs as markdown table."""
    if not legs:
        return "No legs defined"

    lines = ["| Action | Qty | Type | Strike | Price |", "|--------|-----|------|--------|-------|"]
    for leg in legs:
        lines.append(
            f"| {leg.get('action', 'N/A')} | {leg.get('quantity', 0)} | "
            f"{leg.get('type', 'N/A')} | ${leg.get('strike', 0):.2f} | "
            f"${leg.get('premium', leg.get('price', 0)) or 0:.2f} |"
        )
    return "\n".join(lines)


def _parse_legs(legs_str: str) -> list:
    """Parse legs string into list of leg dicts."""
    # Simple parser for "BUY 1 C 150, SELL 1 C 155" format
    legs = []
    for leg in legs_str.split(','):
        parts = leg.strip().split()
        if len(parts) >= 4:
            legs.append({
                'action': parts[0].upper(),
                'quantity': int(parts[1]),
                'type': 'call' if parts[2].upper() == 'C' else 'put',
                'strike': float(parts[3])
            })
    return legs
