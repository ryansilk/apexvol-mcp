"""
Options Chain Tools

Tools for querying options chain data, expirations, and delta-based lookups.
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
    """Register chain tools with the MCP server."""

    @mcp.tool(**read_only('Options Chain'))
    async def get_options_chain(
        ticker: str,
        expiration: Optional[str] = None,
        num_expirations: int = 1,
        strikes_around: int = 20
    ) -> dict:
        """
        Get the options chain for a ticker.

        Returns calls and puts with all Greeks, IV, volume, and open interest
        per strike. Defaults to the nearest expiration and the 20 strikes each
        side of the money — widen only when the analysis genuinely needs it.

        Use this tool when the user asks about:
        - Options prices for a stock
        - Call or put prices at specific strikes
        - Volume and open interest data
        - Full options chain information

        Args:
            ticker: Stock symbol (e.g., "AAPL", "SPY", "TSLA")
            expiration: Specific expiration date (YYYY-MM-DD); overrides num_expirations
            num_expirations: How many of the nearest expirations to include (1-10)
            strikes_around: Strikes per side of the money to keep (0 = full chain)

        Returns:
            Options chain data with calls, puts, and metadata
        """
        try:
            client = get_client()
            params = {}
            if expiration:
                params['expiration'] = expiration
            if num_expirations != 1:
                params['num_expirations'] = num_expirations
            if strikes_around != 20:
                params['strikes_around'] = strikes_around

            result = await client.get(f"/chain/{ticker.upper()}", params=params if params else None)

            return {
                "success": True,
                "data": result,
                "summary": _format_chain_summary(ticker, result),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_source": "ORATS"
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting options chain: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Expiration Dates'))
    async def get_expirations(ticker: str) -> dict:
        """
        Get available expiration dates for a ticker.

        Returns a list of all available options expiration dates,
        useful for planning trades or understanding the term structure.

        Use this tool when the user asks about:
        - When options expire
        - Available expiration dates
        - Weekly vs monthly expirations

        Args:
            ticker: Stock symbol

        Returns:
            List of expiration dates
        """
        try:
            client = get_client()
            result = await client.get(f"/expirations/{ticker.upper()}")

            # Result is the list of expirations directly
            expirations = result if isinstance(result, list) else result.get('expirations', [])

            return {
                "success": True,
                "data": {"expirations": expirations},
                "summary": f"## {ticker.upper()} Expirations\n\n"
                          f"**{len(expirations)} expiration dates available**\n\n"
                          f"Next 5: {', '.join(expirations[:5]) if expirations else 'None'}",
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting expirations: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Options by Delta'))
    async def get_options_by_delta(
        ticker: str,
        target_delta: float = 0.30,
        option_type: str = "call",
        expiration: Optional[str] = None
    ) -> dict:
        """
        Find options at a specific delta.

        Useful for finding options at standard delta levels (e.g., 0.30 delta calls
        for covered calls, 0.16 delta puts for credit spreads).

        Use this tool when the user asks about:
        - Options at a specific delta
        - 30 delta calls or 20 delta puts
        - Finding strikes by delta

        Args:
            ticker: Stock symbol
            target_delta: Target delta (0.0 to 1.0, default 0.30)
            option_type: "call" or "put"
            expiration: Specific expiration or None for nearest

        Returns:
            Strike and option details at the target delta
        """
        try:
            client = get_client()
            params = {
                'delta': target_delta,
                'option_type': option_type
            }
            if expiration:
                params['expiration'] = expiration

            result = await client.get(f"/options-by-delta/{ticker.upper()}", params=params)

            return {
                "success": True,
                "data": result,
                "summary": _format_delta_result(ticker, option_type, target_delta, result),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "stock_price": result.get('stock_price', 0)
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting options by delta: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Stock Price'))
    async def get_stock_price(ticker: str) -> dict:
        """
        Get current stock price and company information.

        Returns the current price, bid/ask, and basic company stats.

        Use this tool when the user asks about:
        - Current stock price
        - Bid/ask spread
        - Company information

        Args:
            ticker: Stock symbol

        Returns:
            Current price and company information
        """
        try:
            client = get_client()
            result = await client.get(f"/stock/{ticker.upper()}")

            return {
                "success": True,
                "data": result,
                "summary": f"## {ticker.upper()} - {result.get('company_name', ticker)}\n\n"
                          f"**Price**: ${result.get('price', 0):.2f}\n"
                          f"**Bid/Ask**: ${result.get('bid', 0):.2f} / ${result.get('ask', 0):.2f}\n"
                          f"**Sector**: {result.get('sector', 'N/A')}",
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting stock price: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool(**read_only('Expected Move'))
    async def calculate_expected_move(
        ticker: str,
        expiration: Optional[str] = None
    ) -> dict:
        """
        Calculate the expected move based on ATM straddle pricing.

        The expected move represents the market's implied price range
        through the expiration date, derived from options pricing.

        Use this tool when the user asks about:
        - Expected move or implied move
        - How much a stock might move
        - Options-implied price range
        - Event risk pricing

        Args:
            ticker: Stock symbol
            expiration: Specific expiration or None for nearest

        Returns:
            Expected move in dollars and percentage
        """
        try:
            client = get_client()
            params = {}
            if expiration:
                params['expiration'] = expiration

            result = await client.get(f"/expected-move/{ticker.upper()}", params=params if params else None)

            return {
                "success": True,
                "data": result,
                "summary": f"## {ticker.upper()} Expected Move\n\n"
                          f"**Expiration**: {result.get('expiration', 'N/A')}\n"
                          f"**Expected Move**: ${result.get('expected_move_dollars', 0):.2f} "
                          f"({result.get('expected_move_percent', 0)*100:.1f}%)\n\n"
                          f"**Range**: ${result.get('lower_bound', 0):.2f} - ${result.get('upper_bound', 0):.2f}",
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error calculating expected move: {e}")
            return {"success": False, "error": str(e)}


    @mcp.tool(**read_only('Historical Options Chain'))
    async def get_historical_chain(
        ticker: str,
        expiration: str,
        trade_date: str
    ) -> dict:
        """
        Get the options chain as it looked on a past trading day (EOD snapshot).

        Historical chains go back years — see how an option was priced before
        an earnings event, through a selloff, or at any point in its life.

        Use this tool when the user asks about:
        - What an option was trading at on a past date
        - How a chain looked before/after an event
        - Backtesting entries against real historical quotes

        Args:
            ticker: Stock symbol
            expiration: Expiration date YYYY-MM-DD
            trade_date: The historical date to snapshot YYYY-MM-DD

        Returns:
            End-of-day chain snapshot for that date
        """
        try:
            client = get_client()
            result = await client.get(
                f"/chain-at-time/{ticker.upper()}",
                params={'expiration': expiration, 'trade_date': trade_date},
            )

            return {
                "success": True,
                "data": result,
                "summary": (
                    f"## {ticker.upper()} chain on {trade_date} (exp {expiration})\n\n"
                    "End-of-day snapshot — see data for strikes and quotes."
                ),
                "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()}
            }
        except ApexVolAPIError as e:
            return {"success": False, "error": e.message}
        except Exception as e:
            logger.error(f"Error getting historical chain: {e}")
            return {"success": False, "error": str(e)}


def _format_chain_summary(ticker: str, data: dict) -> str:
    """Format chain data as markdown summary."""
    stock_price = data.get('stock_price', 0)
    chains = data.get('chains', {})

    lines = [
        f"## {ticker.upper()} Options Chain",
        f"",
        f"**Stock Price**: ${stock_price:.2f}",
        f"**Expirations**: {len(chains)}",
        f"",
    ]

    if chains:
        first_exp = list(chains.keys())[0]
        first_chain = chains.get(first_exp, [])
        lines.append(f"### Nearest Expiration: {first_exp}")
        lines.append(f"Contracts: {len(first_chain)}")

    return "\n".join(lines)


def _format_delta_result(ticker: str, option_type: str, target_delta: float, data: dict) -> str:
    """Format delta lookup result as markdown."""
    return f"""## {ticker.upper()} {target_delta:.2f} Delta {option_type.capitalize()}

**Expiration**: {data.get('expiration', 'N/A')}
**Strike**: ${data.get('strike', 0):.2f}
**Actual Delta**: {data.get('actual_delta', 0):.3f}

| Metric | Value |
|--------|-------|
| Bid | ${data.get('bid', 0):.2f} |
| Ask | ${data.get('ask', 0):.2f} |
| Mid | ${data.get('mid', 0):.2f} |
| IV | {data.get('iv', 0)*100:.1f}% |
| Volume | {data.get('volume', 0):,} |
| OI | {data.get('open_interest', 0):,} |
"""
