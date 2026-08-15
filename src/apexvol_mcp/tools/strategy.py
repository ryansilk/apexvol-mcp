"""
Strategy Building Tools

Tools for building, analyzing, and optimizing options strategies.
Uses REST API calls to ApexVol platform.
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from ..api_client import get_client, ApexVolAPIError
from ._annotations import read_only

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP):
    """Register strategy tools with the MCP server."""

    @mcp.tool(**read_only('Strategy Builder'))
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
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error building strategy: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Strategy Analyzer'))
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
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error analyzing strategy: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Strike Optimizer'))
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
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error optimizing strategy: {e}")
            return {"success": False, "error": str(e)}


    @mcp.tool(**read_only('Chain Simulator'))
    async def simulate_option_chain(
        ticker: str,
        sim_price: float,
        sim_dte: float,
        iv_adjustment: float = 0,
        expiration: str = ""
    ) -> dict:
        """
        Re-price an options chain at a hypothetical stock price, DTE, and IV shift.

        Black-Scholes "what-if" for the whole chain: what would these options
        be worth if the stock were at X, with Y days left, and IV up/down Z%?

        Use this tool when the user asks about:
        - What an option would be worth if the stock moves
        - How theta decay reshapes the chain over time
        - IV crush / IV spike what-ifs

        Args:
            ticker: Stock symbol (server fetches the current chain)
            sim_price: Hypothetical stock price
            sim_dte: Days to expiration to simulate (0 = at expiry)
            iv_adjustment: IV shift in percent, -50 to +50 (e.g. -30 for IV crush)
            expiration: Expiration date YYYY-MM-DD (default: nearest)

        Returns:
            The re-priced chain with Greeks at the simulated conditions
        """
        try:
            client = get_client()
            payload = {
                'ticker': ticker.upper(),
                'sim_price': sim_price,
                'sim_dte': sim_dte,
                'iv_adjustment': iv_adjustment,
            }
            if expiration:
                payload['expiration'] = expiration

            result = await client.post("/simulate-chain", data=payload)

            return {
                "success": True,
                "data": result,
                "summary": (
                    f"## {ticker.upper()} simulated chain\n\n"
                    f"Stock at ${sim_price:g}, {sim_dte:g} DTE, IV {iv_adjustment:+g}% — "
                    f"{len(result.get('chain', []))} strikes re-priced (see data)."
                ),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error simulating chain: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Probability of Profit'))
    async def calculate_probability_of_profit(
        legs: str,
        stock_price: float,
        days_to_exp: int
    ) -> dict:
        """
        Calculate the probability of profit for a set of option legs.

        Uses N(d2)-based probabilities on the combined position payoff.

        Use this tool when the user asks about:
        - Probability of profit / PoP for a trade
        - Odds a spread or condor expires profitable

        Args:
            legs: JSON array of legs, e.g.
                '[{"option_type": "put", "action": "sell", "strike": 95, "iv": 32.5, "premium": 1.20, "quantity": 1}]'
                (iv accepts percent or decimal; premium is per share)
            stock_price: Current stock price
            days_to_exp: Days to expiration

        Returns:
            Probability of profit percentage
        """
        try:
            import json as _json
            client = get_client()
            parsed_legs = _json.loads(legs)
            if isinstance(parsed_legs, dict):
                parsed_legs = [parsed_legs]

            result = await client.post("/pop", data={
                'legs': parsed_legs,
                'stock_price': stock_price,
                'days_to_exp': days_to_exp,
            })

            pop = result.get('probability_of_profit', 0)
            return {
                "success": True,
                "data": result,
                "summary": f"**Probability of profit**: {pop:.1f}% ({result.get('legs_count', 0)} legs, {days_to_exp} DTE)",
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error calculating PoP: {e}")
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
